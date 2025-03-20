import datetime
import decimal
import unittest
import petl  # type: ignore

from beancount.parser import cmptest
from beangulp import petl_utils


class TestPetlUtils(cmptest.TestCase, unittest.TestCase):

    def test_table_to_directives_minimal(self):
        table = (
            petl.wrap([('date', 'account', 'amount'),
                       ('2021-02-15', 'Assets:Checking', '4.56'),
                       ('2021-02-16', 'Assets:Savings', '107.89')])
            .convert('date', lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date())
            .convert('amount', decimal.Decimal))
        transactions = petl_utils.table_to_directives(table)
        self.assertEqualEntries("""

          2021-02-15 *
            Assets:Checking  4.56 USD

          2021-02-16 *
            Assets:Savings  107.89 USD

        """, transactions)

    def test_table_to_directives_all(self):
        table = (
            petl.wrap([
                ('date', 'payee', 'narration', 'account', 'amount', 'balance'),
                ('2021-02-15', 'TheStore', 'BuyingSomething', 'Liabilities:Credit',
                 '-4.56', '-73330.00'),
            ])
            .convert('date', lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date())
            .convert(['amount', 'balance'], decimal.Decimal))
        transactions = petl_utils.table_to_directives(table)
        self.assertEqualEntries("""

          2021-02-15 * "TheStore" "BuyingSomething"
            Liabilities:Credit  -4.56 USD

          2021-02-16 balance Liabilities:Credit   -73330.00 USD

        """, transactions)
