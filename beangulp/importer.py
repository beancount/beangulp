"""Importer protocol definition."""

__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import abc
import datetime
import inspect

from typing import Optional

from beancount.core import flags
from beancount.core import data
from beangulp import cache
from beangulp import utils
from beangulp import extract
from beangulp import similar


class Importer(abc.ABC):
    """Interface that all source importers need to comply with.

    The interface is defined as an abstract base class implementing
    base behavior for all importers. Importer implementations need to
    provide at least the identify() and account() methods.

    """

    @property
    def name(self) -> str:
        """Unique id for the importer.

        The name is used to identify the importer in the command line
        interface. Conventionally this is a dotted string containing
        the module and name of the class, however a specific format is
        not enforced.

        """
        return f"{self.__class__.__module__}.{self.__class__.__name__}"

    @abc.abstractmethod
    def identify(self, filepath: str) -> bool:
        """Return True if this importer matches the given file.

        Args:
          filepath: Filesystem path to the document to be matched.

        Returns:
          True if this importer can handle this file.

        """
        raise NotImplementedError

    @abc.abstractmethod
    def account(self, filepath: str) -> data.Account:
        """Return the account associated with the given file.

        The account is used to determine the archival folder for the
        document. While the interface allows returning different
        accounts for different documents, normally the returned
        account is a just a function of the importer instance.

        Args:
          filepath: Filesystem path to the document being imported.

        Returns:
          An account name.

        """
        raise NotImplementedError

    def date(self, filepath: str) -> Optional[datetime.date]:
        """Return the archival date the given file.

        The date is used by the archive command to form the archival
        filename of the document. If this method returns None, the
        date corresponding to the file document modification time is
        used.

        Args:
          filepath: Filesystem path to the document being imported.

        Returns:
          A date object or None.

        """
        return None

    def filename(self, filepath: str) -> Optional[str]:
        """Return the archival filename for the given file.

        Tidy filenames or rename documents when archiving them. This
        method should return a valid filename or None. In the latter
        case, the file path basename is used unmodified.

        Args:
          filepath: Filesystem path to the document being imported.

        Returns:
          The document filename to use for archiving.

        """
        return None

    def extract(self, filepath: str, existing: data.Entries) -> data.Entries:
        """Extract transactions and other directives from a document.

        The existing entries list is loaded from the existing ledger
        file, if the user specified one on the command line. It can be
        used to supplement the information provided by the document
        being processed to drive the extraction. For example to derive
        the prior state of the inventory.

        Args:
          filepath: Filesystem path to the document being imported.
          existing: Entries loaded from the existing ledger.

        Returns:
          A list of imported directives extracted from the document.

        """
        return []

    cmp = staticmethod(similar.heuristic_comparator())

    def deduplicate(self, entries: data.Entries, existing: data.Entries) -> None:
        """Mark duplicates in extracted entries.

        The default implementation uses the cmp() method to compare
        each newly extracted entries to the existing entries. Only
        existing entries dated within a 5 days window around the date
        of the each existing entry (two days prior and two days past)
        are considered.

        Duplicated entries are marked setting the "__duplicate__"
        entry metadata field to the entry of which the entry is a
        duplicate.

        Args:
          entries: Entries extracted from the document being processed.
          existing: Entries loaded from the existing ledger.

        """
        window = datetime.timedelta(days=2)
        extract.mark_duplicate_entries(entries, existing, window, self.cmp)

    def sort(self, entries: data.Entries, reverse=False) -> None:
        """Sort the extracted directives.

        The sort is in-place and stable. The reverse flag can be set
        to sort in descending order. Importers can implement this
        method to have entries serialized to file in a specific
        order. The default implementation sorts the entries according
        to beancount.core.data.entry_sortkey().

        Args:
          entries: Entries list to sort.
          reverse: When True sort in descending order.

        Returns:
          None.

        """
        return entries.sort(key=data.entry_sortkey, reverse=reverse)


class ImporterProtocol:
    """Old importers interface, superseded by the Importer ABC.

    The main difference is that the methods of this class accept a
    cache._FileMemo instance instead than the filesystem path to the
    imported document.

    """

    # A flag to use on new transaction. Override this flag in derived classes if
    # you prefer to create your imported transactions with a different flag.
    FLAG = flags.FLAG_OKAY

    def name(self) -> str:
        """See Importer class name property."""
        return f"{self.__class__.__module__}.{self.__class__.__name__}"

    __str__ = name

    def identify(self, file) -> bool:
        """See Importer class identify() method."""
        # Type error ignore for backwards compatibility - this should be overridden
        # and implemented in subclasses
        return None  # type: ignore

    def file_account(self, file) -> data.Account:
        """See Importer class account() method."""
        # Type error ignore for backwards compatibility - this should be overridden
        # and implemented in subclasses
        return None  # type: ignore

    def file_date(self, file) -> Optional[datetime.date]:
        """See Importer class date() method."""

    def file_name(self, file) -> Optional[str]:
        """See Importer class filename() method."""

    def extract(self, file, existing_entries: Optional[data.Entries] = None) -> data.Entries:
        """See Importer class extract() method."""
        return []


class Adapter(Importer):
    """Adapter from ImporterProtocol to Importer ABC interface."""

    def __init__(self, importer: ImporterProtocol) -> None:
        assert isinstance(importer, ImporterProtocol)
        self.importer = importer

    @property
    def name(self) -> str:
        return self.importer.name()

    def identify(self, filepath):
        return self.importer.identify(cache.get_file(filepath))

    def account(self, filepath):
        return self.importer.file_account(cache.get_file(filepath))

    def date(self, filepath):
        return self.importer.file_date(cache.get_file(filepath))

    def filename(self, filepath):
        filename = self.importer.file_name(cache.get_file(filepath))
        # The current implementation of the archive command does not
        # modify the filename returned by the importer. This preserves
        # backward compatibility with the old implementation of the
        # command.
        return utils.idify(filename) if filename else None

    def extract(self, filepath, existing):
        p = inspect.signature(self.importer.extract).parameters
        if len(p) > 1:
            return self.importer.extract(cache.get_file(filepath), existing)
        return self.importer.extract(cache.get_file(filepath))
