"""Utilities using petl.
"""

import datetime
import re

import petl
petl.config.look_style = 'minimal'
petl.config.failonerror = True

from beancount.core import data
from beancount.core import amount
from beancount.core import flags


def table_to_directives(table: petl.Table, currency: str = 'USD') -> data.Entries:
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
    """
    # Ensure the table is sorted in order to produce the final balance.
    assert table.issorted('date')
    assert set(table.fieldnames()) >= {'date', 'account', 'amount'}

    columns = table.fieldnames()
    metas = []
    for column in columns:
        match = re.match("meta:(.*)", column)
        if match:
            metas.append((column, match.group(1)))

    # Create transactions.
    entries = []
    for index, rec in enumerate(table.records()):
        meta = data.new_metadata(f"<{__file__}>".format, index)
        units = amount.Amount(rec.amount, currency)
        tags, links = set(), set()
        txn = data.Transaction(meta, rec.date, flags.FLAG_OKAY,
                               getattr(rec, 'payee', None),
                               getattr(rec, 'narration', ""),
                               tags, links, [
            data.Posting(rec.account, units, None, None, None, None)
        ])

        link = getattr(rec, 'link', None)
        if link:
            links.add(link)
        tag = getattr(rec, 'tag', None)
        if tag:
            tags.add(tag)

        for column, key in metas:
            value = getattr(rec, column, None)
            if value:
                meta[key] = value
        entries.append(txn)

    if 'balance' in columns:
        # Insert a balance with the final value.
        meta = data.new_metadata(f"<{__file__}>", index + 1)
        balance_date = rec.date + datetime.timedelta(days=1)
        entries.append(data.Balance(
            meta, balance_date, rec.account, amount.Amount(rec.balance, currency),
            None, None))

    return entries
