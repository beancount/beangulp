"""CSV importer."""

# Postpone evaluation of annotations. This solves an issue with the
# import of the standard library csv module when this module or its
# associated test are executed as scripts. This requires Python >3.7
# and has to wait till we will drop suppport for Python 3.6
# from __future__ import annotations

__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

from inspect import signature
from os import path
from typing import Callable, Dict, List, Optional, Union, Tuple
import collections
import csv
import datetime
import enum
import io
import warnings

import dateutil.parser

from beancount.core import data
from beancount.core import flags
from beancount.core.amount import Amount
from beancount.core.number import ZERO, D
from beangulp import utils
from beangulp import cache
from beangulp import date_utils
from beangulp import importer
from beangulp.importers.mixins import filing, identifier


class Col(enum.Enum):
    """The set of interpretable columns."""

    # The settlement date, the date we should create the posting at.
    DATE = '[DATE]'

    # The date at which the transaction took place.
    TXN_DATE = '[TXN_DATE]'

    # The time at which the transaction took place.
    # Beancount does not support time field -- just add it to metadata.
    TXN_TIME = '[TXN_TIME]'

    # The payee field.
    PAYEE = '[PAYEE]'

    # The narration fields. Use multiple fields to combine them together.
    NARRATION = NARRATION1 = '[NARRATION1]'
    NARRATION2 = '[NARRATION2]'
    NARRATION3 = '[NARRATION3]'

    # The amount being posted.
    AMOUNT = '[AMOUNT]'

    # Debits and credits being posted in separate, dedicated columns.
    AMOUNT_DEBIT = '[DEBIT]'
    AMOUNT_CREDIT = '[CREDIT]'

    # The balance amount, after the row has posted.
    BALANCE = '[BALANCE]'

    # A field to use as a tag name.
    TAG = '[TAG]'

    # A field to use as a unique reference id or number.
    REFERENCE_ID = '[REF]'

    # A column which says DEBIT or CREDIT (generally ignored).
    DRCR = '[DRCR]'

    # Last 4 digits of the card.
    LAST4 = '[LAST4]'

    # An account name.
    ACCOUNT = '[ACCOUNT]'

    # Categorization, if the institution supports it. You could, in theory,
    # specialize your importer to use this automatically assign a good expenses
    # account.
    CATEGORY = '[CATEGORY]'

    # A column that indicates the amount currency for the current row which may
    # be different to the base currency.
    CURRENCY = '[CURRENCY]'


def get_amounts(iconfig, row, allow_zero_amounts, parse_amount):
    """Get the amount columns of a row.

    Args:
      iconfig: A dict of Col to row index.
      row: A row array containing the values of the given row.
      allow_zero_amounts: Is a transaction with amount D('0.00') okay? If not,
        return (None, None).
    Returns:
      A pair of (debit-amount, credit-amount), both of which are either an
      instance of Decimal or None, or not available.
    """
    debit, credit = None, None
    if Col.AMOUNT in iconfig:
        credit = row[iconfig[Col.AMOUNT]]
    else:
        debit = row[iconfig[Col.AMOUNT_DEBIT]] if Col.AMOUNT_DEBIT in iconfig else None
        credit = row[iconfig[Col.AMOUNT_CREDIT]] if Col.AMOUNT_CREDIT in iconfig else None

    # If zero amounts aren't allowed, return null value.
    is_zero_amount = ((credit is not None and parse_amount(credit) == ZERO) and
                      (debit is not None and parse_amount(debit) == ZERO))
    if not allow_zero_amounts and is_zero_amount:
        return (None, None)

    return (-parse_amount(debit) if debit else None,
            parse_amount(credit) if credit else None)


def normalize_config(config, head, dialect='excel', skip_lines: int = 0):
    """Using the header line, convert the configuration field name lookups to int indexes.

    Args:
      config: A dict of Col types to string or indexes.
      head: A string, some decent number of bytes of the head of the file.
      dialect: A dialect definition to parse the header
      skip_lines: Skip first x (garbage) lines of file.
    Returns:
      A pair of
        A dict of Col types to integer indexes of the fields, and
        a boolean, true if the file has a header.
    Raises:
      ValueError: If there is no header and the configuration does not consist
        entirely of integer indexes.
    """
    # Skip garbage lines before sniffing the header
    assert isinstance(skip_lines, int)
    assert skip_lines >= 0

    head = io.StringIO(head, newline=None)
    lines = list(head)[skip_lines:]

    has_header = csv.Sniffer().has_header('\n'.join(lines))
    if has_header:
        header = next(csv.reader(lines, dialect=dialect))
        field_map = {name.strip(): index for index, name in enumerate(header)}
        index_config = {}
        for field_type, field in config.items():
            if isinstance(field, str):
                field = field_map[field]
            index_config[field_type] = field
    else:
        if any(not isinstance(field, int)
               for field_type, field in config.items()):
            raise ValueError("CSV config without header has non-index fields: "
                             "{}".format(config))
        index_config = config
    return index_config, has_header


def prepare_for_identifier(regexps: Union[str, List[str]],
                           matchers: Optional[List[Tuple[str, str]]]) -> Dict[str, List[Tuple[str, str]]]:
    """Prepare data for identifier mixin."""
    if isinstance(regexps, str):
        regexps = [regexps]
    matchers = matchers or []
    matchers.append(('mime', 'text/csv'))
    if regexps:
        for regexp in regexps:
            matchers.append(('content', regexp))
    return {'matchers': matchers}


def prepare_for_filing(account: str, institution: Optional[str],
                       prefix: Optional[str]) -> Dict[str, str]:
    """Prepare kwds for filing mixin."""
    kwds = {'filing': account}
    if institution:
        prefix = kwds.get('prefix', None)
        assert prefix is None
        kwds['prefix'] = institution
    return kwds


class _CSVImporterBase:
    """Base class for CSV importer implementations.

    Note that many existing importers are based on this; be careful with
    modification of the attribute names and types. See concrete implementations
    below.
    """
    # pylint: disable=too-many-instance-attributes

    FLAG = flags.FLAG_OKAY

    def __init__(self, config, account, currency,
                 regexps=None,
                 skip_lines: int = 0,
                 last4_map: Optional[Dict] = None,
                 categorizer: Optional[Callable] = None,
                 institution: Optional[str] = None,
                 debug: bool = False,
                 csv_dialect: Union[str, csv.Dialect] = 'excel',
                 dateutil_kwds: Optional[Dict] = None,
                 narration_sep: str = '; ',
                 encoding: Optional[str] = None,
                 invert_sign: Optional[bool] = False,
                 **kwds):
        """Constructor.

        Args:
          config: A dict of Col enum types to the names or indexes of the columns.
          account: An account string, the account to post this to.
          currency: A currency string, the currency of this account.
          regexps: A list of regular expression strings.
          skip_lines: Skip first x (garbage) lines of file.
          last4_map: A dict that maps last 4 digits of the card to a friendly string.
          categorizer: A callable with two arguments (transaction, row) that can attach
            the other posting (usually expenses) to a transaction with only single posting.
          institution: An optional name of an institution to rename the files to.
          debug: Whether or not to print debug information
          csv_dialect: A `csv` dialect given either as string or as instance or
            subclass of `csv.Dialect`.
          dateutil_kwds: An optional dict defining the dateutil parser kwargs.
          narration_sep: A string, a separator to use for splitting up the payee and
            narration fields of a source field.
          encoding: Encoding for the file, utf-8 if not specified or None.
          invert_sign: If true, invert the amount's sign unconditionally.
          **kwds: Extra keyword arguments to provide to the base mixins.
        """
        assert isinstance(config, dict), "Invalid type: {}".format(config)
        self.config = config

        self.currency = currency
        assert isinstance(skip_lines, int)
        self.skip_lines = skip_lines
        self.last4_map = last4_map or {}
        self.debug = debug
        self.dateutil_kwds = dateutil_kwds
        self.csv_dialect = csv_dialect
        self.narration_sep = narration_sep
        self.encoding = encoding or 'utf-8'
        self.invert_sign = invert_sign
        self.categorizer = categorizer
        super().__init__(**kwds)

    def file_date(self, file):
        "Get the maximum date from the file."
        iconfig, has_header = normalize_config(
            self.config,
            file.head(encoding=self.encoding),
            self.csv_dialect,
            self.skip_lines,
        )
        if Col.DATE in iconfig:
            with open(file.name, encoding=self.encoding) as infile:
                reader = iter(csv.reader(infile, dialect=self.csv_dialect))
                for _ in range(self.skip_lines):
                    next(reader)
                if has_header:
                    next(reader)
                max_date = None
                for row in reader:
                    if not row:
                        continue
                    if row[0].startswith('#'):
                        continue
                    date_str = row[iconfig[Col.DATE]]
                    date = date_utils.parse_date(date_str, self.dateutil_kwds)
                    if max_date is None or date > max_date:
                        max_date = date
                return max_date

    def _do_extract(self, file, account, existing_entries=None):
        entries = []

        # Normalize the configuration to fetch by index.
        iconfig, has_header = normalize_config(
            self.config,
            file.head(encoding=self.encoding),
            self.csv_dialect,
            self.skip_lines,
        )

        with open(file.name, encoding=self.encoding) as infile:
            reader = iter(csv.reader(infile, dialect=self.csv_dialect))

            # Skip garbage lines
            for _ in range(self.skip_lines):
                next(reader)

            # Skip header, if one was detected.
            if has_header:
                next(reader)

            def get(row, ftype):
                try:
                    return row[iconfig[ftype]] if ftype in iconfig else None
                except IndexError:  # FIXME: this should not happen
                    return None

            # Parse all the transactions.
            first_row = last_row = None
            for index, row in enumerate(reader, 1):
                if not row:
                    continue
                if row[0].startswith('#'):
                    continue

                # If debugging, print out the rows.
                if self.debug:
                    print(row)

                if first_row is None:
                    first_row = row
                last_row = row

                # Extract the data we need from the row, based on the configuration.
                date = get(row, Col.DATE)
                txn_date = get(row, Col.TXN_DATE)
                txn_time = get(row, Col.TXN_TIME)

                payee = get(row, Col.PAYEE)
                if payee:
                    payee = payee.strip()

                fields = filter(None, [get(row, field)
                                       for field in (Col.NARRATION1,
                                                     Col.NARRATION2,
                                                     Col.NARRATION3)])
                narration = self.narration_sep.join(
                    field.strip() for field in fields).replace('\n', '; ')

                tag = get(row, Col.TAG)
                tags = {tag} if tag else data.EMPTY_SET

                link = get(row, Col.REFERENCE_ID)
                links = {link} if link else data.EMPTY_SET

                last4 = get(row, Col.LAST4)

                balance = get(row, Col.BALANCE)

                currency = get(row, Col.CURRENCY) or self.currency

                # Create a transaction
                meta = data.new_metadata(file.name, index)
                if txn_date is not None:
                    meta['date'] = date_utils.parse_date(txn_date,
                                                         self.dateutil_kwds)
                if txn_time is not None:
                    meta['time'] = str(dateutil.parser.parse(txn_time).time())
                if balance is not None:
                    meta['balance'] = Amount(self.parse_amount(balance), currency)
                if last4:
                    last4_friendly = self.last4_map.get(last4.strip())
                    meta['card'] = last4_friendly if last4_friendly else last4
                date = date_utils.parse_date(date, self.dateutil_kwds)
                txn = data.Transaction(meta, date, self.FLAG, payee, narration,
                                       tags, links, [])

                # Attach one posting to the transaction
                amount_debit, amount_credit = self.get_amounts(iconfig, row,
                                                               False, self.parse_amount)

                # Skip empty transactions
                if amount_debit is None and amount_credit is None:
                    continue

                for amount in [amount_debit, amount_credit]:
                    if amount is None:
                        continue
                    if self.invert_sign:
                        amount = -amount
                    units = Amount(amount, currency)
                    txn.postings.append(
                        data.Posting(account, units, None, None, None, None))

                # Attach the other posting(s) to the transaction.
                txn = self.call_categorizer(txn, row)

                # Add the transaction to the output list
                entries.append(txn)

        # Figure out if the file is in ascending or descending order.
        first_date = date_utils.parse_date(get(first_row, Col.DATE),
                                           self.dateutil_kwds)
        last_date = date_utils.parse_date(get(last_row, Col.DATE),
                                          self.dateutil_kwds)
        is_ascending = first_date < last_date

        # Reverse the list if the file is in descending order
        if not is_ascending:
            entries = list(reversed(entries))

        # Add a balance entry if possible. If more than one currency
        # can appear in the input, add one balance statement for each.
        if Col.BALANCE in iconfig:
            balances = set()
            for entry in reversed(entries):
                # Remove the 'balance' metadata.
                balance = entry.meta.pop('balance', None)
                if balance is None:
                    continue
                # Only add the newest entry for each currency in the file
                if balance.currency not in balances:
                    date = entry.date + datetime.timedelta(days=1)
                    meta = data.new_metadata(file.name, index)
                    entries.append(data.Balance(meta, date, account, balance, None, None))
                    balances.add(balance.currency)

        return entries

    def call_categorizer(self, txn, row):
        if not isinstance(self.categorizer, collections.abc.Callable):
            return txn

        # TODO(blais): Remove introspection here, just commit to the two
        # parameter version.
        params = signature(self.categorizer).parameters
        if len(params) < 2:
            return self.categorizer(txn)
        return self.categorizer(txn, row)

    def parse_amount(self, string):
        """The method used to create Decimal instances. You can override this."""
        return D(string)

    def get_amounts(self, iconfig, row, allow_zero_amounts, parse_amount):
        """See function get_amounts() for details.

        This method is present to allow clients to override it in order to deal
        with special cases, e.g., columns with currency symbols in them.
        """
        return get_amounts(iconfig, row, allow_zero_amounts, parse_amount)


# Deprecated. TODO(blais): Remove this eventually (on a major release).
class Importer(_CSVImporterBase, identifier.IdentifyMixin, filing.FilingMixin):
    """Importer for CSV files.

    This class implements the old ImporterProtocol interface. It is
    deprecated and will be removed eventually. Use the CSVImporter
    class instead.

    """

    def __init__(self, config, account, currency,
                 regexps=None,
                 skip_lines: int = 0,
                 last4_map: Optional[Dict] = None,
                 categorizer: Optional[Callable] = None,
                 institution: Optional[str] = None,
                 debug: bool = False,
                 csv_dialect: Union[str, csv.Dialect] = 'excel',
                 dateutil_kwds: Optional[Dict] = None,
                 narration_sep: str = '; ',
                 encoding: Optional[str] = None,
                 invert_sign: Optional[bool] = False,
                 **kwds):
        warnings.warn('beangulp.importers.csv.Importer is deprecated. '
                      'Base your importer on beangulp.importers.csvbase.Importer instead.',
                      DeprecationWarning, stacklevel=2)

        kwds.update(prepare_for_identifier(regexps, kwds.get('matchers')))
        kwds.update(prepare_for_filing(account, kwds.get('prefix', None), institution))
        super().__init__(config, account, currency, **kwds)

    def extract(self, file, existing_entries=None):
        account = self.file_account(file)
        return self._do_extract(file, account, existing_entries)


class CSVImporter(importer.Importer):
    """Importer for CSV files.

    This class adapts the old CSV code to implement the new redesigned
    Importer interface. The new beangulp.importers.csvbase.Importer
    may be a better base for newly developed importers.

    """

    def __init__(self, config, account, currency,
                 regexps=None,
                 skip_lines: int = 0,
                 last4_map: Optional[Dict] = None,
                 categorizer: Optional[Callable] = None,
                 institution: Optional[str] = None,
                 debug: bool = False,
                 csv_dialect: Union[str, csv.Dialect] = 'excel',
                 dateutil_kwds: Optional[Dict] = None,
                 narration_sep: str = '; ',
                 encoding: Optional[str] = None,
                 invert_sign: Optional[bool] = False,
                 **kwds):
        """See _CSVImporterBase."""

        self.base = _CSVImporterBase(config, account, currency,
                                     regexps,
                                     skip_lines,
                                     last4_map,
                                     categorizer,
                                     institution,
                                     debug,
                                     csv_dialect,
                                     dateutil_kwds,
                                     narration_sep,
                                     encoding,
                                     invert_sign)

        filing_kwds = prepare_for_filing(account, kwds.get('prefix', None), institution)
        self.filing = filing.FilingMixin(**filing_kwds)

        ident_kwds = prepare_for_identifier(regexps, kwds.get('matchers'))
        self.ident = identifier.IdentifyMixin(**ident_kwds)

    def identify(self, filepath):
        return self.ident.identify(cache.get_file(filepath))

    def account(self, filepath):
        return self.filing.file_account(cache.get_file(filepath))

    def date(self, filepath):
        return self.base.file_date(cache.get_file(filepath))

    def filename(self, filepath):
        return path.basename(utils.idify(filepath))

    def extract(self, filepath, existing=None):
        account = self.account(filepath)
        return self.base._do_extract(cache.get_file(filepath), account, existing)
