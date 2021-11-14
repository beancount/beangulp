__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import tempfile
import textwrap
import unittest
import warnings

from pprint import pformat
from beancount.core import data
from beancount.parser import cmptest
from beancount.utils import test_utils
from beangulp.importers import csv


Col = csv.Col


class TestCSVFunctions(unittest.TestCase):

    def test_normalize_config__with_header(self):
        head = textwrap.dedent("""\
          Details,Posting Date,"Description",Amount,Type,Balance,Check or Slip #,
          DEBIT,3/18/2016,"Payment to Chafe card ending in 1234 03/18",-2680.89,ACCT_XFER,3409.86,,
          CREDIT,3/15/2016,"EMPLOYER INC    DIRECT DEP                 PPD ID: 1111111111",2590.73,ACH_CREDIT,6090.75,,
          DEBIT,3/14/2016,"INVESTMENT SEC   TRANSFER   A5144608        WEB ID: 1234456789",-150.00,ACH_DEBIT,3500.02,,
        """)
        iconfig, has_header = csv.normalize_config({Col.DATE: 'Posting Date'}, head)
        self.assertEqual({Col.DATE: 1}, iconfig)
        self.assertTrue(has_header)

        iconfig, _ = csv.normalize_config({Col.NARRATION: 'Description'}, head)
        self.assertEqual({Col.NARRATION: 2}, iconfig)

        iconfig, _ = csv.normalize_config({Col.DATE: 1,
                                           Col.NARRATION: 'Check or Slip #'},
                                          head)
        self.assertEqual({Col.DATE: 1, Col.NARRATION: 6}, iconfig)

        iconfig, _ = csv.normalize_config({Col.DATE: 1}, head)
        self.assertEqual({Col.DATE: 1}, iconfig)

    def test_normalize_config__with_skip_and_header(self):
        head = textwrap.dedent("""\
          Lorem ipsum dolor sit amet, consectetur adipiscing elit.
          Aliquam lorem erat, bibendum sed arcu at, tempor commodo tortor.
          Phasellus consectetur, nisl quis vestibulum ornare, mi velit imperdiet arcu, eu mattis nulla augue nec ex.

          Details,Posting Date,"Description",Amount,Type,Balance,Check or Slip #,
          DEBIT,3/18/2016,"Payment to Chafe card ending in 1234 03/18",-2680.89,ACCT_XFER,3409.86,,
          CREDIT,3/15/2016,"EMPLOYER INC    DIRECT DEP                 PPD ID: 1111111111",2590.73,ACH_CREDIT,6090.75,,
          DEBIT,3/14/2016,"INVESTMENT SEC   TRANSFER   A5144608        WEB ID: 1234456789",-150.00,ACH_DEBIT,3500.02,,
        """)
        iconfig, has_header = csv.normalize_config({Col.DATE: 'Posting Date'}, head,
                                                   skip_lines=4)
        self.assertEqual({Col.DATE: 1}, iconfig)
        self.assertTrue(has_header)

        iconfig, _ = csv.normalize_config({Col.NARRATION: 'Description'}, head,
                                          skip_lines=4)
        self.assertEqual({Col.NARRATION: 2}, iconfig)

        iconfig, _ = csv.normalize_config({Col.DATE: 1,
                                           Col.NARRATION: 'Check or Slip #'},
                                          head, skip_lines=4)
        self.assertEqual({Col.DATE: 1, Col.NARRATION: 6}, iconfig)

        iconfig, _ = csv.normalize_config({Col.DATE: 1}, head, skip_lines=4)
        self.assertEqual({Col.DATE: 1}, iconfig)

    def test_normalize_config__without_header(self):
        head = textwrap.dedent("""\
          DEBIT,3/18/2016,"Payment to Chafe card ending in 1234 03/18",-2680.89,ACCT_XFER,3409.86,,
          CREDIT,3/15/2016,"EMPLOYER INC    DIRECT DEP                 PPD ID: 1111111111",2590.73,ACH_CREDIT,6090.75,,
          DEBIT,3/14/2016,"INVESTMENT SEC   TRANSFER   A5144608        WEB ID: 1234456789",-150.00,ACH_DEBIT,3500.02,,
        """)
        iconfig, has_header = csv.normalize_config({Col.DATE: 1}, head)
        self.assertEqual({Col.DATE: 1}, iconfig)
        self.assertFalse(has_header)
        with self.assertRaises(ValueError):
            csv.normalize_config({Col.DATE: 'Posting Date'}, head)

    def test_normalize_config__with_skip_and_without_header(self):
        head = textwrap.dedent("""\
          Lorem ipsum dolor sit amet, consectetur adipiscing elit.
          Aliquam lorem erat, bibendum sed arcu at, tempor commodo tortor.
          Phasellus consectetur, nisl quis vestibulum ornare, mi velit imperdiet arcu, eu mattis nulla augue nec ex.

          DEBIT,3/18/2016,"Payment to Chafe card ending in 1234 03/18",-2680.89,ACCT_XFER,3409.86,,
          CREDIT,3/15/2016,"EMPLOYER INC    DIRECT DEP                 PPD ID: 1111111111",2590.73,ACH_CREDIT,6090.75,,
          DEBIT,3/14/2016,"INVESTMENT SEC   TRANSFER   A5144608        WEB ID: 1234456789",-150.00,ACH_DEBIT,3500.02,,
        """)
        iconfig, has_header = csv.normalize_config({Col.DATE: 1}, head, skip_lines=4)
        self.assertEqual({Col.DATE: 1}, iconfig)
        self.assertFalse(has_header)
        with self.assertRaises(ValueError):
            csv.normalize_config({Col.DATE: 'Posting Date'}, head, skip_lines=4)


class TestCSVImporter(cmptest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', category=DeprecationWarning)

    @test_utils.docfile
    def test_column_types(self, filename):
        # pylint: disable=line-too-long
        """\
          Details,Posting Date,"Description",Amount,Type,Balance,Check or Slip #,
          DEBIT,3/18/2016,"Payment to Chafe card ending in 1234 03/18",-2680.89,ACCT_XFER,3409.86,,
          CREDIT,3/15/2016,"EMPLOYER INC    DIRECT DEP                 PPD ID: 1111111111",2590.73,ACH_CREDIT,6090.75,,
          DEBIT,3/14/2016,"INVESTMENT SEC   TRANSFER   A5144608        WEB ID: 1234456789",-150.00,ACH_DEBIT,3500.02,,
          DEBIT,3/6/2016,"ATM WITHDRAWAL                       001234  03/8888 DELANC",-60.00,ATM,3650.02,,
          CREDIT,3/5/2016,"CA STATE         NYSTTAXRFD                 PPD ID: 1111111111",110.00,ACH_CREDIT,3710.02,,
          DEBIT,3/4/2016,"BOOGLE           WALLET     US000NEI9T      WEB ID: C234567890",-1300.00,ACH_DEBIT,3600.02,,
        """

        importer = csv.CSVImporter({Col.DATE: 'Posting Date',
                                    Col.NARRATION1: 'Description',
                                    Col.NARRATION2: 'Check or Slip #',
                                    Col.AMOUNT: 'Amount',
                                    Col.BALANCE: 'Balance',
                                    Col.DRCR: 'Details'},
                                   'Assets:Bank',
                                   'USD',
                                   ('Details,Posting Date,"Description",Amount,'
                                    'Type,Balance,Check or Slip #,'),
                                   institution='chafe')
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

          2016-03-18 * "Payment to Chafe card ending in 1234 03/18"
            Assets:Bank  -2680.89 USD

          2016-03-15 * "EMPLOYER INC    DIRECT DEP                 PPD ID: 1111111111"
            Assets:Bank  2590.73 USD

          2016-03-14 * "INVESTMENT SEC   TRANSFER   A5144608        WEB ID: 1234456789"
            Assets:Bank  -150.00 USD

          2016-03-06 * "ATM WITHDRAWAL                       001234  03/8888 DELANC"
            Assets:Bank  -60.00 USD

          2016-03-05 * "CA STATE         NYSTTAXRFD                 PPD ID: 1111111111"
            Assets:Bank  110.00 USD

          2016-03-04 * "BOOGLE           WALLET     US000NEI9T      WEB ID: C234567890"
            Assets:Bank  -1300.00 USD

          2016-03-19 balance Assets:Bank                                     3409.86 USD

        """, entries)

    @test_utils.docfile
    def test_date_formats(self, filename):
        """\
          Posting,Description,Amount
          11/7/2016,A,2
          12/7/2016,B,3
          13/7/2016,C,4
        """
        importer = csv.CSVImporter({Col.DATE: 'Posting',
                                    Col.NARRATION: 'Description',
                                    Col.AMOUNT: 'Amount'},
                                   'Assets:Bank', 'EUR', [],
                                   dateutil_kwds={'dayfirst': True})
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

          2016-07-11 * "A"
            Assets:Bank  2 EUR

          2016-07-12 * "B"
            Assets:Bank  3 EUR

          2016-07-13 * "C"
            Assets:Bank  4 EUR

        """, entries)


    @test_utils.docfile
    def test_links(self, filename):
        """\
          Date,Description,Amount,Link
          2020-07-03,A,2,
          2020-07-03,B,3,123
        """
        importer = csv.CSVImporter({Col.DATE: 'Date',
                                    Col.NARRATION: 'Description',
                                    Col.AMOUNT: 'Amount',
                                    Col.REFERENCE_ID: 'Link'},
                                   'Assets:Bank', 'EUR', [])
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

          2020-07-03 * "A"
            Assets:Bank  2 EUR

          2020-07-03 * "B" ^123
            Assets:Bank  3 EUR
        """, entries)


    @test_utils.docfile
    def test_tags(self, filename):
        """\
          Date,Description,Amount,Tag
          2020-07-03,A,2,
          2020-07-03,B,3,foo
        """
        importer = csv.CSVImporter({Col.DATE: 'Date',
                                    Col.NARRATION: 'Description',
                                    Col.AMOUNT: 'Amount',
                                    Col.TAG: 'Tag'},
                                   'Assets:Bank', 'EUR', [])
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

          2020-07-03 * "A"
            Assets:Bank  2 EUR

          2020-07-03 * "B" #foo
            Assets:Bank  3 EUR
        """, entries)


    @test_utils.docfile
    def test_zero_balance_produces_assertion(self, filename):
        """\
          Details,Posting Date,"Description",Amount,Type,Balance,Check or Slip #,
          DEBIT,3/18/2016,"Payment to Chafe card ending in 1234 03/18",-2680.89,ACCT_XFER,0,,
        """
        importer = csv.CSVImporter({Col.DATE: 'Posting Date',
                                    Col.NARRATION1: 'Description',
                                    Col.NARRATION2: 'Check or Slip #',
                                    Col.AMOUNT: 'Amount',
                                    Col.BALANCE: 'Balance',
                                    Col.DRCR: 'Details'},
                                   'Assets:Bank',
                                   'USD',
                                   ('Details,Posting Date,"Description",Amount,'
                                    'Type,Balance,Check or Slip #,'),
                                   institution='chafe')
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

          2016-03-18 * "Payment to Chafe card ending in 1234 03/18"
            Assets:Bank  -2680.89 USD

          2016-03-19 balance Assets:Bank                                     0 USD

        """, entries)

    @test_utils.docfile
    def test_currency_and_balances_where_there_are_multiple_currency_transactions(self, filename):
        """\
          Posting Date,"Description",Amount,Currency,Balance
          3/18/2016,"1st Payment in GBP",-1.00,GBP,-1
          3/18/2016,"1st Payment in PLN",-1,PLN,-1
          3/18/2016,"1st Payment in ZAR",-1.0,ZAR,-1
          3/19/2016,"2nd Payment in GBP",-2,GBP,-3
          3/19/2016,"2nd Payment in Main Currency",-2.00,,-3
          3/20/2016,"3rd Payment in GBP",-3,GBP,-6
        """
        importer = csv.CSVImporter({Col.DATE: 'Posting Date',
                                    Col.NARRATION1: 'Description',
                                    Col.AMOUNT: 'Amount',
                                    Col.CURRENCY: 'Currency',
                                    Col.BALANCE: 'Balance'},
                                   'Assets:Bank',
                                   'PLN')
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

           2016-03-18 * "1st Payment in GBP"
             Assets:Bank  -1.00 GBP

           2016-03-18 * "1st Payment in PLN"
             Assets:Bank  -1 PLN

           2016-03-18 * "1st Payment in ZAR"
             Assets:Bank  -1.0 ZAR

           2016-03-19 * "2nd Payment in GBP"
             Assets:Bank  -2 GBP

           2016-03-19 * "2nd Payment in Main Currency"
             Assets:Bank  -2.00 PLN

           2016-03-20 * "3rd Payment in GBP"
             Assets:Bank  -3 GBP

           2016-03-20 balance Assets:Bank  -3 PLN

           2016-03-19 balance Assets:Bank  -1 ZAR

           2016-03-21 balance Assets:Bank  -6 GBP

        """, entries)

    @test_utils.docfile
    def test_zero_balance_assertion_is_added_with_currency_field(self, filename):
        """\
          Posting Date,"Description",Amount,Currency,Balance
          3/18/2016,"1st Payment in GBP",-1.00,GBP,-1
          3/18/2016,"1st Payment in PLN",-1,PLN,-1
          3/18/2016,"1st Payment in ZAR",-1.0,ZAR,-1
          3/19/2016,"2nd Payment in GBP",-2,GBP,-3
          3/19/2016,"2nd Payment in Main Currency",-2.00,,-3
          3/20/2016,"3rd Payment in GBP",-3,GBP,-6
          3/21/2016,"4th Payment in GBP",6,GBP,0
        """
        importer = csv.CSVImporter({Col.DATE: 'Posting Date',
                                    Col.NARRATION1: 'Description',
                                    Col.AMOUNT: 'Amount',
                                    Col.CURRENCY: 'Currency',
                                    Col.BALANCE: 'Balance'},
                                   'Assets:Bank',
                                   'PLN')
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

           2016-03-18 * "1st Payment in GBP"
             Assets:Bank  -1.00 GBP

           2016-03-18 * "1st Payment in PLN"
             Assets:Bank  -1 PLN

           2016-03-18 * "1st Payment in ZAR"
             Assets:Bank  -1.0 ZAR

           2016-03-19 * "2nd Payment in GBP"
             Assets:Bank  -2 GBP

           2016-03-19 * "2nd Payment in Main Currency"
             Assets:Bank  -2.00 PLN

           2016-03-20 * "3rd Payment in GBP"
             Assets:Bank  -3 GBP

           2016-03-21 * "4th Payment in GBP"
             Assets:Bank  6 GBP

           2016-03-20 balance Assets:Bank  -3 PLN

           2016-03-19 balance Assets:Bank  -1 ZAR

           2016-03-22 balance Assets:Bank  0 GBP

        """, entries)


    @test_utils.docfile
    def test_currency_and_balances_when_none_are_in_the_main_currency(self, filename):
        """\
          Posting Date,"Description",Amount,Currency,Balance
          3/18/2016,"1st Payment in GBP",-1.00,GBP,-1
          3/18/2016,"1st Payment in ZAR",-1.0,ZAR,-1
          3/19/2016,"2nd Payment in GBP",-2,GBP,-3
          3/20/2016,"3rd Payment in GBP",-3,GBP,-6
        """
        importer = csv.CSVImporter({Col.DATE: 'Posting Date',
                                    Col.NARRATION1: 'Description',
                                    Col.AMOUNT: 'Amount',
                                    Col.CURRENCY: 'Currency',
                                    Col.BALANCE: 'Balance'},
                                   'Assets:Bank',
                                   'PLN')
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

           2016-03-18 * "1st Payment in GBP"
             Assets:Bank  -1.00 GBP

           2016-03-18 * "1st Payment in ZAR"
             Assets:Bank  -1.0 ZAR

           2016-03-19 * "2nd Payment in GBP"
             Assets:Bank  -2 GBP

           2016-03-20 * "3rd Payment in GBP"
             Assets:Bank  -3 GBP

           2016-03-19 balance Assets:Bank  -1 ZAR

           2016-03-21 balance Assets:Bank  -6 GBP

        """, entries)

    @test_utils.docfile
    def test_main_currency_should_be_used_when_no_currency_is_specified(self, filename):
        """\
          Posting Date,"Description",Amount,Currency,Balance
          3/18/2016,"1st Payment",-1.00,,-1
          3/18/2016,"2nd Payment",-1.0,,-2
          3/19/2016,"3rd Payment",-2,,-4
          3/20/2016,"4th Payment",-3,,-7
        """
        importer = csv.CSVImporter({Col.DATE: 'Posting Date',
                                    Col.NARRATION1: 'Description',
                                    Col.AMOUNT: 'Amount',
                                    Col.CURRENCY: 'Currency',
                                    Col.BALANCE: 'Balance'},
                                   'Assets:Bank',
                                   'PLN')
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

           2016-03-18 * "1st Payment"
             Assets:Bank  -1.00 PLN

           2016-03-18 * "2nd Payment"
             Assets:Bank  -1.0 PLN

           2016-03-19 * "3rd Payment"
             Assets:Bank  -2 PLN

           2016-03-20 * "4th Payment"
             Assets:Bank  -3 PLN

           2016-03-21 balance Assets:Bank  -7 PLN

        """, entries)

    @test_utils.docfile
    def test_categorizer_one_argument(self, filename):
        """\
          Date,Amount,Payee,Description
          6/2/2020,30.00,"Payee here","Description"
          7/2/2020,-25.00,"Supermarket","Groceries"
        """
        def categorizer(txn):
            if txn.narration == "Groceries":
                txn.postings.append(
                    data.Posting("Expenses:Groceries",
                                 -txn.postings[0].units,
                                 None, None, None, None))

            return txn

        importer = csv.CSVImporter({Col.DATE: 'Date',
                                    Col.NARRATION: 'Description',
                                    Col.AMOUNT: 'Amount'},
                                   'Assets:Bank',
                                   'EUR',
                                   ('Date,Amount,Payee,Description'),
                                   categorizer=categorizer,
                                   institution='foobar')
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

          2020-06-02 * "Description"
            Assets:Bank  30.00 EUR

          2020-07-02 * "Groceries"
            Assets:Bank  -25.00 EUR
            Expenses:Groceries  25.00 EUR
        """, entries)

    @test_utils.docfile
    def test_categorizer_two_arguments(self, filename):
        """\
          Date,Amount,Payee,Description
          6/2/2020,30.00,"Payee here","Description"
          7/2/2020,-25.00,"Supermarket","Groceries"
        """
        def categorizer(txn, row):
            txn = txn._replace(payee=row[2])
            txn.meta['source'] = pformat(row)
            return txn

        importer = csv.CSVImporter({Col.DATE: 'Date',
                                    Col.NARRATION: 'Description',
                                    Col.AMOUNT: 'Amount'},
                                   'Assets:Bank',
                                   'EUR',
                                   ('Date,Amount,Payee,Description'),
                                   categorizer=categorizer,
                                   institution='foobar')
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

          2020-06-02 * "Payee here" "Description"
            source: "['6/2/2020', '30.00', 'Supermarket', 'Groceries']"
            Assets:Bank  30.00 EUR

          2020-07-02 * "Supermarket" "Groceries"
            source: "['7/2/2020', '-25.00', 'Supermarket', 'Groceries']"
            Assets:Bank  -25.00 EUR
        """, entries)

    @test_utils.docfile
    def test_explict_encoding_utf8(self, filename):
        """\
          Posting,Description,Amount
          2020/08/08,🍏,2
        """
        importer = csv.CSVImporter({Col.DATE: 'Posting',
                                    Col.NARRATION: 'Description',
                                    Col.AMOUNT: 'Amount'},
                                   'Assets:Bank', 'EUR', [],
                                   encoding='utf-8')
        entries = importer.extract(filename)
        self.assertEqualEntries(r"""

          2020-08-08 * "🍏"
            Assets:Bank  2 EUR

        """, entries)

    def test_newlines(self):
        content = textwrap.dedent("""\
          Date,Description,Amount
          2020-07-03,A,2
          2020-07-03,B,3
        """)
        importer = csv.CSVImporter({Col.DATE: 'Date',
                                    Col.NARRATION: 'Description',
                                    Col.AMOUNT: 'Amount'},
                                   'Assets:Bank', 'EUR', [])
        for nl in '\n', '\r\n', '\r':
            with tempfile.NamedTemporaryFile('w') as temp:
                temp.write(content.replace('\n', nl))
                temp.flush()
                entries = importer.extract(temp.name)
                self.assertEqualEntries("""
                  2020-07-03 * "A"
                    Assets:Bank  2 EUR

                  2020-07-03 * "B"
                    Assets:Bank  3 EUR
                """, entries)


# TODO: Test things out with/without payee and with/without narration.
# TODO: Test balance support.
# TODO: Add balances every month or week.
# TODO: Test ascending and descending orders.
# TODO: Add a test for all the supported fields, e.g. NARRATION2.
