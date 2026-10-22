import datetime
import decimal
import re
import unittest
from itertools import dropwhile

from beancount.core import data
from beancount.parser import cmptest
from beancount.utils.test_utils import docfile
from beangulp.importers.csvbase import (
    _chomp,
    Column,
    Columns,
    Date,
    Amount,
    CSVMeta,
    CSVReader,
    Order,
    Importer,
    CreditOrDebit,
)


class TestColumn(unittest.TestCase):
    def test_index_spec(self):
        column = Column(0)
        func = column.getter(None)
        value = func(
            (
                "0",
                "1",
                "2",
                "3",
            )
        )
        self.assertEqual(value, "0")

    def test_named_spec(self):
        column = Column("Num")
        func = column.getter({"Num": 1})
        value = func(
            (
                "0",
                "1",
                "2",
                "3",
            )
        )
        self.assertEqual(value, "1")

    def test_named_errrors(self):
        column = Column("A")
        with self.assertRaisesRegex(KeyError, "Cannot find column 'A' in "):
            column.getter({"B": 0, "C": 1})
        with self.assertRaisesRegex(KeyError, "Column 'A' cannot be found in "):
            column.getter(None)

    def test_strip(self):
        # The default field parser strips whitespace.
        column = Column(0)
        func = column.getter(None)
        value = func((" value ",))
        self.assertEqual(value, "value")

    def test_default_value(self):
        column = Column(0, default=42)
        func = column.getter(None)
        value = func(("",))
        self.assertEqual(value, 42)

    def test_default_value_none(self):
        column = Column(0, default=None)
        func = column.getter(None)
        value = func(("",))
        self.assertIsNone(value)


class TestDateColumn(unittest.TestCase):
    def test_default_format(self):
        column = Date(0)
        func = column.getter(None)
        value = func(("2021-05-16",))
        self.assertEqual(value, datetime.date(2021, 5, 16))

    def test_custom_format(self):
        column = Date(0, "%d.%m.%Y")
        func = column.getter(None)
        value = func(("16.05.2021",))
        self.assertEqual(value, datetime.date(2021, 5, 16))

    def test_default_value(self):
        column = Date(0, default=datetime.date.today())
        func = column.getter(None)
        value = func(("",))
        self.assertEqual(value, datetime.date.today())

    def test_default_value_none(self):
        column = Date(0, default=None)
        func = column.getter(None)
        value = func(("",))
        self.assertIsNone(value)


class TestColumnsColumn(unittest.TestCase):
    def test_default_sep(self):
        column = Columns(0, 1)
        func = column.getter(None)
        value = func(
            (
                "0",
                "1",
                "2",
                "3",
            )
        )
        self.assertEqual(value, "0 1")

    def test_custom_sep(self):
        column = Columns(0, 1, sep=": ")
        func = column.getter(None)
        value = func(
            (
                "0",
                "1",
                "2",
                "3",
            )
        )
        self.assertEqual(value, "0: 1")

    def test_default_value(self):
        column = Columns(0, 1, default="something")
        func = column.getter(None)
        value = func(
            (
                "",
                "",
            )
        )
        self.assertEqual(value, "something")

    def test_default_value_none(self):
        column = Columns(0, 1, default=None)
        func = column.getter(None)
        value = func(
            (
                "",
                "",
            )
        )
        self.assertIsNone(value)

    def test_some_empty(self):
        column = Columns(0, 1, default=None)
        func = column.getter(None)
        value = func(
            (
                "this",
                "",
            )
        )
        self.assertEqual(value, "this")


class TestAmountColumn(unittest.TestCase):
    def test_parse_decimal(self):
        column = Amount(0)
        func = column.getter(None)
        value = func(("1.0",))
        self.assertIsInstance(value, decimal.Decimal)
        self.assertEqual(value, decimal.Decimal("1.0"))

    def test_parse_subs_one(self):
        column = Amount(0, subs={",": ""})
        func = column.getter(None)
        value = func(("1,000.00",))
        self.assertIsInstance(value, decimal.Decimal)
        self.assertEqual(value, decimal.Decimal("1000.00"))

    def test_parse_subs_two(self):
        column = Amount(0, subs={"\\.": "", ",": "."})
        func = column.getter(None)
        value = func(("1.000,00",))
        self.assertIsInstance(value, decimal.Decimal)
        self.assertEqual(value, decimal.Decimal("1000.00"))

    def test_parse_subs_currency(self):
        column = Amount(0, subs={"\\$(.*)": "\\1", ",": ""})
        func = column.getter(None)
        value = func(("$1,000.00",))
        self.assertIsInstance(value, decimal.Decimal)
        self.assertEqual(value, decimal.Decimal("1000.00"))

    def test_default_value(self):
        column = Amount(0, default=decimal.Decimal(42))
        func = column.getter(None)
        value = func(("",))
        self.assertEqual(value, decimal.Decimal(42))

    def test_default_value_none(self):
        column = Amount(0, default=None)
        func = column.getter(None)
        value = func(("",))
        self.assertIsNone(value)

    def test_parse_negate(self):
        column = Amount(0, negate=True)
        func = column.getter(None)
        value = func(("123.45",))
        self.assertIsInstance(value, decimal.Decimal)
        self.assertEqual(value, -decimal.Decimal("123.45"))


class TestCreditOrDebitColumn(unittest.TestCase):
    def test_parse_credit(self):
        column = CreditOrDebit(0, 1)
        func = column.getter(None)
        value = func(("1.0", ""))
        self.assertEqual(value, decimal.Decimal("1.0"))

    def test_parse_debit(self):
        column = CreditOrDebit(0, 1)
        func = column.getter(None)
        value = func(("", "1.0"))
        self.assertEqual(value, -decimal.Decimal("1.0"))

    def test_parse_subs(self):
        column = CreditOrDebit(0, 1, subs={",": ""})
        func = column.getter(None)
        value = func(("1,000.00", ""))
        self.assertIsInstance(value, decimal.Decimal)
        self.assertEqual(value, decimal.Decimal("1000.00"))

    def test_default_value(self):
        column = CreditOrDebit(0, 1, default=decimal.Decimal(42))
        func = column.getter(None)
        value = func(("", ""))
        self.assertEqual(value, decimal.Decimal(42))

    def test_default_value_none(self):
        column = CreditOrDebit(0, 1, default=None)
        func = column.getter(None)
        value = func(("", ""))
        self.assertIsNone(value)

    def test_both_columns(self):
        column = CreditOrDebit(0, 1)
        func = column.getter(None)
        with self.assertRaisesRegex(
            ValueError, "The credit and debit fields cannot be populated at the same time"
        ):
            func(("1.0", "2.0"))

    def test_neither_columns(self):
        column = CreditOrDebit(0, 1)
        func = column.getter(None)
        with self.assertRaisesRegex(
            ValueError, "Neither credit or debit fields are populated"
        ):
            func(("", ""))


class TestCSVMeta(unittest.TestCase):
    def test_collect_fields(self):
        class CSVTest(metaclass=CSVMeta):
            first = Column(0)
            second = Column(1)

        # pylint: disable=no-member
        self.assertEqual(CSVTest.columns.keys(), {"first", "second"})


class TestCSVReader(unittest.TestCase):
    @docfile
    def test_named_columns(self, filename):
        """\
        First, Second
        1, 2
        3, 4
        """

        class Reader(CSVReader):
            first = Column("First")
            second = Column("Second")

        reader = Reader()
        rows = list(reader.read(filename))
        self.assertEqual(len(rows), 2)
        # tuple elements
        self.assertEqual(rows[0][0], "1")
        # leading space is preserved
        self.assertEqual(rows[1][1], " 4")
        # attribute accessors
        self.assertEqual(rows[0].first, "1")
        self.assertEqual(rows[1].second, "4")

    @docfile
    def test_named_no_enough_lines(self, filename):
        """\
        # comment
        """

        class Reader(CSVReader):
            first = Column("First")
            second = Column("Second")

        reader = Reader()
        with self.assertRaisesRegex(IndexError, "The input file does not contain "):
            list(reader.read(filename))

    @docfile
    def test_indexed_columns_names_false(self, filename):
        """\
        First, Second
        1, 2
        3, 4
        """

        class Reader(CSVReader):
            first = Column(0)
            second = Column(1)
            names = False

        reader = Reader()
        rows = list(reader.read(filename))
        self.assertEqual(len(rows), 3)
        # tuple elements
        self.assertEqual(rows[0][0], "First")
        # leading space is preserved
        self.assertEqual(rows[2][1], " 4")
        # attribute accessors
        self.assertEqual(rows[0].first, "First")
        self.assertEqual(rows[2].second, "4")

    @docfile
    def test_indexed_columns_names_true(self, filename):
        """\
        First, Second
        1, 2
        3, 4
        """

        class Reader(CSVReader):
            first = Column(0)
            second = Column(1)

        reader = Reader()
        rows = list(reader.read(filename))
        self.assertEqual(len(rows), 2)
        # tuple elements
        self.assertEqual(rows[0][0], "1")
        # leading space is preserved
        self.assertEqual(rows[1][1], " 4")
        # attribute accessors
        self.assertEqual(rows[0].first, "1")
        self.assertEqual(rows[1].second, "4")

    @docfile
    def test_comments(self, filename):
        """\
        First, Second
        # ignore
        a, b
        c, d
        """

        class Reader(CSVReader):
            first = Column(0)
            second = Column(1)

        reader = Reader()
        rows = list(reader.read(filename))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "a")

    @docfile
    def test_no_comments(self, filename):
        """\
        First, Second
        # ignore
        a, b
        c, d
        """

        class Reader(CSVReader):
            first = Column(0)
            second = Column(1)
            comments = False

        reader = Reader()
        rows = list(reader.read(filename))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], "# ignore")

    @docfile
    def test_custom_comments(self, filename):
        """\
        First, Second
        # ignore
        ; ignore
        a, b
        c, d
        """

        class Reader(CSVReader):
            first = Column(0)
            second = Column(1)
            comments = ";"

        reader = Reader()
        rows = list(reader.read(filename))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], "# ignore")

    @docfile
    def test_skiplines(self, filename):
        """\
        Skip
        Skip
        First, Second
        a, b
        """

        class Reader(CSVReader):
            first = Column(0)
            second = Column(1)
            skiplines = 2

        reader = Reader()
        rows = list(reader.read(filename))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "a")

    @docfile
    def test_footer(self, filename):
        """\
        Header
        First, Second
        a, b
        Footer
        Footer
        """

        class Reader(CSVReader):
            first = Column(0)
            second = Column(1)
            header = 1
            footer = 2

        reader = Reader()
        rows = list(reader.read(filename))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "a")

    @docfile
    def test_custom_open(self, filename):
        """\
        Skip this line
        Skip this too
        First, Second
        a, b
        c, d
        """

        class Reader(CSVReader):
            first = Column("First")
            second = Column("Second")

            def open(self, filepath):
                """Skip lines until we find the column headers."""
                lines = super().open(filepath)
                return dropwhile(lambda line: "First" not in line, lines)

        reader = Reader()
        rows = list(reader.read(filename))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].first, "a")
        self.assertEqual(rows[1].second, "d")


class Base(Importer):
    def identify(self, filepath):
        return True


class TestImporter(cmptest.TestCase):
    @docfile
    def test_date(self, filename):
        """\
        2021-05-17, Test, 1.00
        2021-05-18, Test, 1.00
        2021-05-16, Test, 1.00
        """

        class CSVImporter(Base):
            date = Date(0)

        importer = CSVImporter("Account:CSV", "EUR")
        date = importer.date(filename)
        self.assertEqual(date, datetime.date(2021, 5, 18))

    @docfile
    def test_extract(self, filename):
        """\
        2021-05-17, Test, 1.00
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            names = False

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-17 * "Test"
          Assets:CSV  1.00 EUR
        """,
        )

    @docfile
    def test_extract_payee(self, filename):
        """\
        2021-05-17, Payee, Test, 1.00
        """

        class CSVImporter(Base):
            date = Date(0)
            payee = Column(1)
            narration = Column(2)
            amount = Amount(3)
            names = False

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-17 * "Payee" "Test"
          Assets:CSV  1.00 EUR
        """,
        )

    @docfile
    def test_extract_account(self, filename):
        """\
        2021-05-17, Test, Assets:Test, 1.00
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            account = Column(2)
            amount = Amount(3)
            names = False

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-17 * "Test"
          Assets:Test  1.00 EUR
        """,
        )

    @docfile
    def test_extract_balance(self, filename):
        """\
        2021-05-17, Test A, 1.00, 1.00
        2021-05-18, Test B, 2.00, 3.00
        2021-05-18, Test C, 1.00, 4.00
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            balance = Amount(3)
            names = False

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-17 * "Test A"
          Assets:CSV  1.00 EUR
        2021-05-18 * "Test B"
          Assets:CSV  2.00 EUR
        2021-05-18 * "Test C"
          Assets:CSV  1.00 EUR
        2021-05-19 balance Assets:CSV  4.00 EUR
        """,
        )

    @docfile
    def test_extract_balance_order(self, filename):
        """\
        2021-05-18, Test B, 2.00, 4.00
        2021-05-18, Test C, 1.00, 2.00
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            balance = Amount(3)
            names = False
            order = Order.DESCENDING

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-18 * "Test C"
          Assets:CSV  1.00 EUR
        2021-05-18 * "Test B"
          Assets:CSV  2.00 EUR
        2021-05-19 balance Assets:CSV  4.00 EUR
        """,
        )

    @docfile
    def test_extract_flag(self, filename):
        """\
        2021-05-17, Test, 1.00, !
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            flag = Column(3)
            names = False

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-17 ! "Test"
          Assets:CSV  1.00 EUR
        """,
        )

    @docfile
    def test_extract_link_and_tag(self, filename):
        """\
        2021-05-17, Test, 1.00, link, tag
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            link = Column(3)
            tag = Column(4)
            names = False

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-17 * "Test" ^link #tag
          Assets:CSV  1.00 EUR
        """,
        )

    @docfile
    def test_extract_currency(self, filename):
        """\
        2021-05-17, Test A US, 1.00, 1.00, USD
        2021-05-17, Test A EU, 2.00, 2.00, EUR
        2021-05-18, Test B US, 2.00, 3.00, USD
        2021-05-18, Test B EU, 3.00, 5.00, EUR
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            balance = Amount(3)
            currency = Column(4)
            names = False

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-17 * "Test A US"
          Assets:CSV  1.00 USD
        2021-05-17 * "Test A EU"
          Assets:CSV  2.00 EUR
        2021-05-18 * "Test B US"
          Assets:CSV  2.00 USD
        2021-05-18 * "Test B EU"
          Assets:CSV  3.00 EUR
        2021-05-19 balance Assets:CSV  3.00 USD
        2021-05-19 balance Assets:CSV  5.00 EUR
        """,
        )

    @docfile
    def test_extract_metadata(self, filename):
        """\
        2021-05-17, Test, 1.00, data, 42
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            meta = Column(3)
            data = Amount(4)
            names = False

            def metadata(self, filepath, lineno, row):
                meta = super().metadata(filepath, lineno, row)
                for field in "meta", "data":
                    meta[field] = getattr(row, field)
                return meta

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-17 * "Test"
          meta: "data"
          data: 42
          Assets:CSV  1.00 EUR
        """,
        )

    @docfile
    def test_extract_finalize(self, filename):
        """\
        2021-05-17, Test, -1.00, Testing
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            category = Column(3)
            names = False

            def finalize(self, txn, row):
                posting = data.Posting(
                    "Expenses:" + row.category,
                    # This could be None in a real importer. However,
                    # the trsting framework accepts only complete
                    # transactions, thus we do the booking manually.
                    -txn.postings[0].units,
                    None,
                    None,
                    None,
                    None,
                )
                txn.postings.append(posting)
                return txn

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqualEntries(
            entries,
            """
        2021-05-17 * "Test"
          Assets:CSV  -1.00 EUR
          Expenses:Testing  1.00 EUR
        """,
        )

    @docfile
    def test_extract_finalize_remove(self, filename):
        """\
        2021-05-17, Test, -1.00, Testing
        2021-05-18, Drop, -2.00, Testing
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            names = False

            def finalize(self, txn, row):
                if txn.narration == "Drop":
                    return None
                return txn

        importer = CSVImporter("Assets:CSV", "EUR")
        entries = importer.extract(filename, [])
        self.assertEqual(len(entries), 1)

    @docfile
    def test_report_exception(self, filename):
        """\
        2025-01-25, Test, -1.00
        2025-01-26, Test, invalid
        """

        class CSVImporter(Base):
            date = Date(0)
            narration = Column(1)
            amount = Amount(2)
            names = False

        importer = CSVImporter("Assets:CSV", "EUR")
        msg = re.escape(
            f"Error processing {filename} line 3 with values ('2025-01-26', ' Test', ' invalid'"
        )
        with self.assertRaisesRegex(RuntimeError, msg) as ctx:
            importer.extract(filename, [])
        self.assertIsInstance(ctx.exception.__cause__, decimal.InvalidOperation)


class TestChomp(unittest.TestCase):

    def test_header(self):
        self.assertEqual(list(_chomp(range(10), 2, 0)), [2, 3, 4, 5, 6, 7, 8, 9])

    def test_footer(self):
        self.assertEqual(list(_chomp(range(10), 0, 3)), [0, 1, 2, 3, 4, 5, 6])

    def test_header_and_footer(self):
        self.assertEqual(list(_chomp(range(10), 2, 3)), [2, 3, 4, 5, 6])

    def test_short(self):
        self.assertEqual(list(_chomp(range(1), 2, 3)), [])
