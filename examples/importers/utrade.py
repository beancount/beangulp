"""Example importer for example broker UTrade.
"""
__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import csv
import datetime
import re
import logging

from os import path
from dateutil.parser import parse

from beancount.core import account
from beancount.core import amount
from beancount.core import data
from beancount.core import flags
from beancount.core import position
from beancount.core.number import D
from beancount.core.number import ZERO

import beangulp
from beangulp.testing import main


class Importer(beangulp.Importer):
    """An importer for UTrade CSV files (an example investment bank)."""

    def __init__(self, currency: str,
                 account_root: data.Account,
                 account_cash: data.Account,
                 account_dividends: data.Account,
                 account_gains: data.Account,
                 account_fees: data.Account,
                 account_external: data.Account) -> None:
        self.currency = currency
        self.account_root = account_root
        self.account_cash = account_cash
        self.account_dividends = account_dividends
        self.account_gains = account_gains
        self.account_fees = account_fees
        self.account_external = account_external

    def identify(self, filepath: str) -> bool:
        # Match if the filename is as downloaded and the header has the unique
        # fields combination we're looking for.
        if not re.match(r"UTrade\d\d\d\d\d\d\d\d\.csv", path.basename(filepath)):
            return False
        with open(filepath, 'r') as fd:
            head = fd.read(13)
        if head != "DATE,TYPE,REF":
            return False
        return True

    def filename(self, filepath: str) -> str:
        return 'utrade.{}'.format(path.basename(filepath))

    def account(self, filepath: str) -> data.Account:
        return self.account_root

    def date(self, filepath: str) -> datetime.date:
        # Extract the statement date from the filename.
        return datetime.datetime.strptime(path.basename(filepath),
                                          'UTrade%Y%m%d.csv').date()

    def extract(self, filepath: str, existing: data.Entries) -> data.Entries:
        # Open the CSV file and create directives.
        entries: data.Entries = []
        index = 0
        with open(filepath) as infile:
            for index, row in enumerate(csv.DictReader(infile)):
                meta = data.new_metadata(filepath, index)
                date = parse(row['DATE']).date()
                rtype = row['TYPE']
                link = f"ut{row['REF #']}"
                links = frozenset([link])
                desc = f"({row['TYPE']}) {row['DESCRIPTION']}"
                units = amount.Amount(D(row['AMOUNT']), self.currency)
                fees = amount.Amount(D(row['FEES']), self.currency)
                other = amount.add(units, fees)

                if rtype == 'XFER':
                    assert fees.number == ZERO
                    txn = data.Transaction(
                        meta, date, flags.FLAG_OKAY, None, desc, data.EMPTY_SET, links, [
                            data.Posting(self.account_cash, units, None, None, None,
                                         None),
                            data.Posting(self.account_external, -other, None, None, None,
                                         None),
                        ])

                elif rtype == 'DIV':
                    assert fees.number == ZERO

                    # Extract the instrument name from its description.
                    match = re.search(r'~([A-Z]+)$', row['DESCRIPTION'])
                    if not match:
                        logging.error("Missing instrument name in '%s'", row['DESCRIPTION'])
                        continue
                    instrument = match.group(1)
                    account_dividends = self.account_dividends.format(instrument)

                    txn = data.Transaction(
                        meta, date, flags.FLAG_OKAY, None, desc, data.EMPTY_SET, links, [
                            data.Posting(self.account_cash, units, None, None, None, None),
                            data.Posting(account_dividends, -other, None, None, None, None),
                        ])

                elif rtype in ('BUY', 'SELL'):

                    # Extract the instrument name, number of units, and price from
                    # the description. That's just what we're provided with (this is
                    # actually realistic of some data from some institutions, you
                    # have to figure out a way in your parser).
                    match = re.search(r'\+([A-Z]+)\b +([0-9.]+)\b +@([0-9.]+)',
                                      row['DESCRIPTION'])
                    if not match:
                        logging.error("Missing purchase infos in '%s'", row['DESCRIPTION'])
                        continue
                    instrument = match.group(1)
                    account_inst = account.join(self.account_root, instrument)
                    units_inst = amount.Amount(D(match.group(2)), instrument)
                    rate = D(match.group(3))

                    if rtype == 'BUY':
                        cost = position.CostSpec(rate, None, self.currency, None, None, None)
                        txn = data.Transaction(
                            meta, date, flags.FLAG_OKAY, None, desc, data.EMPTY_SET, links, [
                                data.Posting(self.account_cash, units, None, None, None,
                                             None),
                                data.Posting(self.account_fees, fees, None, None, None,
                                             None),
                                data.Posting(account_inst, units_inst, cost, None, None,
                                             None),
                            ])

                    elif rtype == 'SELL':
                        # Extract the lot. In practice this information not be there
                        # and you will have to identify the lots manually by editing
                        # the resulting output. You can leave the cost.number slot
                        # set to None if you like.
                        match = re.search(r'\(LOT ([0-9.]+)\)', row['DESCRIPTION'])
                        if not match:
                            logging.error("Missing cost basis in '%s'", row['DESCRIPTION'])
                            continue
                        cost_number = D(match.group(1))
                        cost = position.CostSpec(cost_number, None, self.currency, None, None, None)
                        price = amount.Amount(rate, self.currency)
                        account_gains = self.account_gains.format(instrument)
                        txn = data.Transaction(
                            meta, date, flags.FLAG_OKAY, None, desc, data.EMPTY_SET, links, [
                                data.Posting(self.account_cash, units, None, None, None,
                                             None),
                                data.Posting(self.account_fees, fees, None, None, None,
                                             None),
                                data.Posting(account_inst, units_inst, cost, price, None,
                                             None),
                                data.Posting(account_gains, None, None, None, None,
                                             None),
                            ])

                else:
                    logging.error("Unknown row type: %s; skipping", rtype)
                    continue

                entries.append(txn)

        # Insert a final balance check.
        if index:
            entries.append(
                data.Balance(meta, date + datetime.timedelta(days=1),
                             self.account_cash,
                             amount.Amount(D(row['BALANCE']), self.currency),
                             None, None))

        return entries

    @staticmethod
    def cmp(a, b):
        # This importer attaches an unique ID to all transactions in
        # the form of a link. The link can be used to implement
        # transaction duplicates detection based on transactions IDs.

        if not isinstance(a, data.Transaction):
            return False
        if not isinstance(b, data.Transaction):
            return False

        # Get all the links with the expected ut$ID format.
        aids = [link for link in a.links if re.match(r'ut\d{8}', link)]
        if not aids:
            # If there are no matching links, stop here.
            return False

        # Get all the links with the expected ut$ID format.
        bids = [link for link in b.links if re.match(r'ut\d{8}', link)]
        if not bids:
            # If there are no matching links, stop here.
            return False

        if len(aids) != len(bids):
            return False

        # Compare all collected IDs.
        if all(aid == bid for aid, bid in zip(sorted(aids), sorted(bids))):
            return True

        return False


if __name__ == '__main__':
    importer = Importer(
        "USD",
        "Assets:US:UTrade",
        "Assets:US:UTrade:Cash",
        "Income:US:UTrade:{}:Dividend",
        "Income:US:UTrade:{}:Gains",
        "Expenses:Financial:Fees",
        "Assets:US:BofA:Checking")
    main(importer)
