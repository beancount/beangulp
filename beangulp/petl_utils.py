"""Utilities using petl.
"""

from typing import Optional, Set
import datetime
import re

import petl  # type: ignore

from beancount.core import data
from beancount.core import amount
from beancount.core import flags


petl.config.look_style = "minimal"
petl.config.failonerror = True


def table_to_directives(
    table: petl.Table, currency: str = "USD", filename: Optional[str] = None
) -> data.Entries:
    """Convert a petl table to Beancount directives.

    This is intended as a convenience for many simple CSV importers. Your CSV
    code uses petl to normalize the contents of an imported file to a table, and
    this routine is called to actually translate that into directives.

    Required columns of the input 'table' are:
      date: A datetime.date instance, for the transaction.
      account: An account string, for the posting.
      amount: A Decimal instance, the number you want on the posting.
    Optional columns are:
      payee: A string, for the transaction's payee.
      narration: A string, for the transaction's narration.
      balance: A Decimal, the balance in the account *after* the given transaction.
      other_account: An account string, for the remainder of the transaction.
    """
    # Ensure the table is sorted in order to produce the final balance.
    assert table.issorted("date")
    assert set(table.fieldnames()) >= {"date", "account", "amount"}

    columns = table.fieldnames()
    metas = []
    for column in columns:
        match = re.match("meta:(.*)", column)
        if match:
            metas.append((column, match.group(1)))

    # Create transactions.
    entries: data.Entries = []
    filename = filename or f"<{__file__}>"
    for index, rec in enumerate(table.records()):
        meta = data.new_metadata(filename, index)
        units = amount.Amount(rec.amount, currency)
        tags: Set[str] = set()
        links: Set[str] = set()
        link = getattr(rec, "link", None)
        if link:
            links.add(link)
        tag = getattr(rec, "tag", None)
        if tag:
            tags.add(tag)
        txn = data.Transaction(
            meta,
            rec.date,
            flags.FLAG_OKAY,
            getattr(rec, "payee", None),
            getattr(rec, "narration", ""),
            frozenset(tags),
            frozenset(links),
            [data.Posting(rec.account, units, None, None, None, None)],
        )
        if hasattr(rec, "other_account") and rec.other_account:
            txn.postings.append(
                data.Posting(rec.other_account, None, None, None, None, None)
            )

        for column, key in metas:
            value = getattr(rec, column, None)
            if value:
                meta[key] = value
        entries.append(txn)

    if "balance" in columns:
        # Insert a balance with the final value.
        meta = data.new_metadata(filename, index + 1)
        balance_date = rec.date + datetime.timedelta(days=1)
        entries.append(
            data.Balance(
                meta,
                balance_date,
                rec.account,
                amount.Amount(rec.balance, currency),
                None,
                None,
            )
        )

    return entries


def absorb_extra(table: petl.Table, column: str) -> petl.Table:
    """Absorb extra columns in a specific column.

    Sadly, some programmers in banks will forego the usage of libraries
    performing proper escaping of commas. This produces invalid CSV files, where
    some rows have an extra column or two. This function fixes up those mistakes
    by specifying a column to absort extra columns.

    The behavior is as follows: if the header has 7 columns, we assume the rest
    of the rows in the file should also have 7 columns. If this function is
    given the column name 'description' and it lives in the 5th column, a row
    with an abnormal 8 columns will be modified to merge the 5th nd 6th columns.
    If a row shows up with 9 columns, the 5th column would absort columns 5, 6
    and 7.  Rows with the normal 7 columns are unaffected.
    """
    header = table.fieldnames()
    num_expected_cols = len(header)
    absorbent_col = header.index(column)

    def absorb(row):
        row = list(row)
        if len(row) > num_expected_cols:
            for _ in range(len(row) - num_expected_cols):
                row[absorbent_col] = "{}, {}".format(
                    row[absorbent_col], row[absorbent_col + 1]
                )
                del row[absorbent_col + 1]
        return tuple(row)

    return table.rowmap(absorb, header=header)
