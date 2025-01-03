import abc
import csv
import datetime
import decimal
import re

from collections import defaultdict
from itertools import islice
from typing import Any, Dict, FrozenSet
from beancount.core import data

import beangulp

EMPTY: FrozenSet[str] = frozenset()


def _resolve(spec, names):
    """Resolve column specification into column index.

    Args:
      spec: Column name or index.
      names: A dict mapping column names to column indices.

    Returns:
      Column index.
    """
    if isinstance(spec, int):
        return spec
    if names is None:
        raise KeyError(f'Column {spec!r} cannot be found in file without column names')
    col = names.get(spec)
    if col is None:
        cols = ', '.join(repr(name) for name in names.keys())
        raise KeyError(f'Cannot find column {spec!r} in column names: {cols}')
    return col


class Column:
    """Field descriptor.

    Args:
      name: Column name or index.
      default: Value to return if the field is empty.
    """

    def __init__(self, *names, default=None):
        self.names = names
        self.default = default

    def __repr__(self):
        names = ', '.join(repr(i) for i in self.names)
        return f'{self.__class__.__module__}.{self.__class__.__name__}({names})'

    def getter(self, names):
        """Generate an attribute accessor for the column specification.

        The returned function is a getitem-like function that takes a
        tuple as argument and returns the value of the field described
        by the column specificaion. The function returns the field
        default value if all columns are empty. The value is parsed
        with the column parser function.

        Args:
          names: A dict mapping column names to column indices.

        Returns:
          An accessor function.

        """
        idxs = [_resolve(x, names) for x in self.names]
        def func(obj):
            value = tuple(obj[i] for i in idxs)
            if not all(value) and self.default:
                return self.default
            return self.parse(*value)
        return func

    def parse(self, value):
        """Parse column value.

        Args:
          value: Field string value obtained from the CSV reader.

        Returns:
          Field parsed value.

        """
        return value.strip()


class Columns(Column):
    """Specialized Column for multiple column fields.

    Args:
      name: Column names or indexes.
      sep: Separator to use to join columns.

    """
    def __init__(self, *names, sep=' '):
        super().__init__(*names)
        self.sep = sep

    def parse(self, *values):
        return self.sep.join(val.strip() for val in values if val)


class Date(Column):
    """Specialized Column descriptor for date fields.

    Parse strings into datetime.date objects accordingly to the
    provided format specification. The format specification is the
    same understood by datetime.datetime.strptime().

    Args:
      name: Column name or index.
      frmt: Date format specification.

    """
    def __init__(self, name, frmt='%Y-%m-%d'):
        super().__init__(name)
        self.frmt = frmt

    def parse(self, value):
        return datetime.datetime.strptime(value.strip(), self.frmt).date()


class Amount(Column):
    """Specialized Column descriptor for decimal fields.

    Parse strings into decimal.Decimal objects. Optionally apply
    regexp substitutions before parsing the decimal number. This
    allows to normalize locale formatted decimal numbers into the
    format expected by decimal.Decimal().

    Args:
      name: Column name or index.
      subs: Dictionary mapping regular expression patterns to
        replacement strings. Substitutions are performed with
        re.sub() in the order they are specified.

    """

    def __init__(self, name, subs=None):
        super().__init__(name)
        self.subs = subs if subs is not None else {}

    def parse(self, value):
        for pattern, replacement in self.subs.items():
            value = re.sub(pattern, replacement, value)
        return decimal.Decimal(value)


# The CSV Importer class needs to inherit from beangulp.Importer which
# is an abstract base class having abc.ABCMeta as metaclass. To be
# able to do so out CSV metaclass need to be a sublcass of
# abc.ABCMeta.
class CSVMeta(abc.ABCMeta):
    """A metaclass that extracts column specifications from class members
    and stores them in a columns dictionary keyed by the member name."""
    def __new__(mcs, name, bases, dct):
        columns = {}
        others = {}
        for key, value in dct.items():
            if isinstance(value, Column):
                columns[key] = value
                continue
            others[key] = value
        others['columns'] = columns
        return super().__new__(mcs, name, bases, others)


class CSVReader(metaclass=CSVMeta):
    encoding = 'utf8'
    """File encoding."""
    skiplines = 0
    """Number of input lines to skip before startign processing."""
    names = True
    """Whether the data file contains a row with column names."""
    dialect = None
    """The CSV dialect used in the input file."""
    comments = '#'
    """Comment character."""

    # This is populated by the CSVMeta metaclass.
    columns: Dict[Any, Any] = {}

    def read(self, filepath):
        """Read CSV file according to class defined columns specification.

        Use the first rown in the data file to resolve columns
        specification. Yield namedtuple-like objects with attribute
        accessors to access the data fields as defined by the class
        columns specification.

        Args:
          filepath: Filesystem path to the input file.

        Yields:
          Namedtuple-like objects.

        """

        with open(filepath, encoding=self.encoding) as fd:
            # Skip header lines.
            lines = islice(fd, self.skiplines, None)

            # Filter out comment lines.
            if self.comments:
                lines = filter(lambda x: not x.startswith(self.comments), lines)

            reader = csv.reader(lines, dialect=self.dialect)

            # Map column names to column indices.
            names = None
            if self.names:
                headers = next(reader, None)
                if headers is None:
                    raise IndexError('The input file does not contain an header line')
                names = {name.strip(): index for index, name in enumerate(headers)}

            # Construct a class with attribute accessors for the
            # configured columns that works similarly to a namedtuple.
            attrs = {}
            for name, column in self.columns.items():
                attrs[name] = property(column.getter(names))
            row = type('Row', (tuple, ), attrs)

            # Return data rows.
            for x in reader:
                yield row(x)


class Importer(beangulp.Importer, CSVReader):
    """CSV files importer base class.

    This class provides the infrastructure and the basic functionality
    necessary for importing transactions and balance assertions from
    CSV files. To do anything useful it needs to be subclassed to add
    fields definitions. Fields are defined as class attributes of type
    Column.

    Args:
      account: Importer default account.
      currency: Importer default currency.
      flag: Importer default flag for new transactions.

    """
    def __init__(self, account, currency, flag='*'):
        self.importer_account = account
        self.currency = currency
        self.flag = flag

    def date(self, filepath):
        """Implement beangulp.Importer::date()"""
        return max(row.date for row in self.read(filepath))

    def account(self, filepath):
        """Implement beangulp.Importer::account()"""
        return self.importer_account

    def extract(self, filepath, existing):
        """Implement beangulp.Importer::extract()

        This methods costructs a transaction for each data row using
        the date, narration, and amount required fields and the flag,
        payee, account, currency, tag, link, balance optional fields.

        Transaction metadata is constructed with the metadata() method
        and the finalize() method is called on each transaction. These
        can be redefine in subclasses. For customization that cannot
        be implemented with these two extension points, consider
        basing the importer on the CSVReader class and implement
        tailored data processing in the extract() method.

        """

        entries = []
        balances = defaultdict(list)
        default_account = self.account(filepath)

        # Compute the line number of the first data line.
        offset = int(self.skiplines) + bool(self.names) + 1

        for lineno, row in enumerate(self.read(filepath), offset):
            # Skip empty lines.
            if not row:
                continue

            tag = getattr(row, 'tag', None)
            tags = {tag} if tag else EMPTY

            link = getattr(row, 'link', None)
            links = {link} if link else EMPTY

            # This looks like an exercise in defensive programming
            # gone too far, but we do not want to depend on any field
            # being defined other than the essential ones.
            flag = getattr(row, 'flag', self.flag)
            payee = getattr(row, 'payee', None)
            account = getattr(row, 'account', default_account)
            currency = getattr(row, 'currency', self.currency)
            units = data.Amount(row.amount, currency)

            # Create a transaction.
            txn = data.Transaction(self.metadata(filepath, lineno, row),
                                   row.date, flag, payee, row.narration, tags, links, [
                                       data.Posting(account, units, None, None, None, None),
                                   ])

            # Apply user processing to the transaction.
            txn = self.finalize(txn, row)

            # Add the transaction to the output list.
            entries.append(txn)

            # Add balance to balances list.
            balance = getattr(row, 'balance', None)
            if balance is not None:
                date = row.date + datetime.timedelta(days=1)
                units = data.Amount(balance, currency)
                meta = data.new_metadata(filepath, lineno)
                balances[currency].append(data.Balance(meta, date, account, units, None, None))

        if not entries:
            return []

        # Reverse the list if the file is in descending order.
        if not entries[0].date <= entries[-1].date:
            entries.reverse()

        # Append balances.
        for currency, balances in balances.items():
            entries.append(max(balances, key=lambda x: x.date))

        return entries

    def metadata(self, filepath, lineno, row):
        """Build transaction metadata dictionary.

        This method can be extended to add customized metadata
        entries based on the content of the data row.

        Args:
          filepath: Path to the file being imported.
          lineno: Line number of the data being processed.
          row: The data row being processed.

        Returns:
          A metadata dictionary.

        """
        return data.new_metadata(filepath, lineno)

    def finalize(self, txn, row):
        """Post process the transaction.

        Args:
          txn: The just build Transaction object.
          row: The data row being processed.

        Returns:
          A potentially extended or modified Transaction object.

        """
        return txn
