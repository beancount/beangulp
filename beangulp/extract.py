__copyright__ = "Copyright (C) 2016-2017  Martin Blais"
__license__ = "GNU GPLv2"

import bisect
import datetime
import operator
import textwrap
import warnings

from typing import Callable

from beancount.core import data
from beancount.parser import printer
from beangulp import similar


# Header for the file where the extracted entries are written.
HEADER = ';; -*- mode: beancount -*-\n'

# Format for the section titles separating entries extracted from
# different documents. This is used as a format sting passing the
# document filesystem path as argument.
SECTION = '**** {}'

# Metadata field that indicates the entry is a likely duplicate.
DUPLICATE = '__duplicate__'


def extract_from_file(importer, filename, existing_entries):
    """Import entries from a document.

    Args:
      importer: The importer instance to handle the document.
      filename: Filesystem path to the document.
      existing_entries: Existing entries.

    Returns:
      The list of imported entries.
    """
    entries = importer.extract(filename, existing_entries)
    if not entries:
        return []

    # Sort the newly imported entries.
    importer.sort(entries)

    # Ensure that the entries are typed correctly.
    for entry in entries:
        data.sanity_check_types(entry)

    return entries


def sort_extracted_entries(extracted):
    """Sort the extraxted entries.

    Sort extracged entries, grouped by source document, in the order
    in which they will be used in deduplication and in which they will
    be serialized to file.

    Args:
      extracted: List of (filepath, entries, account, importer) tuples
        where entries is the list of entries extracted from the
        document at filepath by importer.

    """

    # The entries are sorted on a key composed by (max-date, account,
    # min-date, filename) where max-date and min-date are the latest
    # and earliest date appearing in the entries list.  This should
    # place entries from documents produced earlier in time at before
    # ones coming from documents produced later.
    #
    # Most imports have a balance statement at the end with a date
    # that is one day later than the reporting period (balance
    # statement are effective at the beginning of the day).  Thus
    # using the end date should be more predictable than sorting on
    # the earliest entry.
    #
    # This diagram, where the bars represents the time span covered by
    # contained entries, represent the sort order we want to obtain:
    #
    # Assets:Ali   (-----)
    # Assets:Ali   (=====--------)
    # Assets:Bob    (------------)
    # Assets:Bob             (===----)
    # Assets:Ali                 (--------------)
    # Assets:Bob                (====-----------)
    #
    # The sections marked with = represent the time spans in which
    # duplicated entries could be present.  We want entries form
    # documents produced earlier in time to take precedence over
    # entries from documents produced later in time.

    def key(element):
        filename, entries, account, importer = element
        dates = [entry.date for entry in entries]
        # Sort documents that do not contain any entry last.
        max_date = min_date = datetime.date(9999, 1, 1)
        if dates:
            max_date, min_date = max(dates), min(dates)
        return max_date, account, min_date, filename

    extracted.sort(key=key)


def find_duplicate_entries(extracted, existing):
    """Flag potentially duplicate entries.

    Args:
      extracted: List of (filepath, entries, account, importer) tuples
        where entries is the list of entries extracted from the
        document at filepath by importer.
      existing: Existing entries.

    Returns:
      A copy of the list of new entries with the potentially duplicate
      entries marked setting the "__duplicate__" metadata field to True.

    """
    # This function is kept only for backwards compatibility.
    warnings.warn('The find_duplicate_entries() function is kept only for '
                  'backwards compatibility with import scripts that explicitly '
                  'added it to the import hooks. It does not conform to the '
                  'current way of implementing deduplication and it is not to '
                  'be used.', stacklevel=2)

    ret = []
    for filepath, entries, account, importer in extracted:

        # Sort the existing entries by date: find_similar_entries()
        # uses bisection to reduce the list of existing entries to the
        # set in a narrow date interval around the date of each entry
        # in the set it is comparing against.
        existing.sort(key=operator.attrgetter('date'))

        # Find duplicates.
        pairs = similar.find_similar_entries(entries, existing)

        # We could do something smarter than throwing away the
        # information about which entry is the source of the possible
        # duplication.
        duplicates = { id(duplicate) for duplicate, source in pairs }
        marked = []
        for entry in entries:
            if id(entry) in duplicates:
                meta = entry.meta.copy()
                meta[DUPLICATE] = True
                entry = entry._replace(meta=meta)
            marked.append(entry)
        ret.append((filepath, marked, account, importer))

        # Append the current batch of extracted entries to the
        # existing entries. This allows to deduplicate entries in the
        # current extraction run.
        existing.extend(marked)

    return ret


def mark_duplicate_entries(
        entries: data.Entries,
        existing: data.Entries,
        window: datetime.timedelta,
        compare: Callable[[data.Directive, data.Directive], bool]) -> None:
    """Mark duplicate entries.

    Compare newly extracted entries to the existing entries. Only
    existing entries dated within the given time window around the
    date of the each existing entry.

    Entries that are determined to be duplicates of existing entries
    are marked setting the "__duplicate__" metadata field.

    Args:
      entries: Entries to be deduplicated.
      existing: Existing entries.
      window: Time window in which entries are compared.
      compare: Entry comparison function.

    """
    # The use of bisection to identify the entries in the existing
    # list that have dates within a given window around the date
    # of each newly extracted entry requires the existing entries
    # to be sorted by date.
    existing.sort(key=operator.attrgetter('date'))
    dates = [entry.date for entry in existing]

    def entries_date_window_iterator(date):
        lo = bisect.bisect_left(dates, date - window)
        hi = bisect.bisect_right(dates, date + window)
        for i in range(lo, hi):
            yield existing[i]

    for entry in entries:
        for target in entries_date_window_iterator(entry.date):
            if compare(entry, target):
                entry.meta[DUPLICATE] = target


def print_extracted_entries(extracted, output):
    """Print extracted entries.

    Entries marked as duplicates are printed as comments.

    Args:
      extracted: List of (filepath, entries, account, importer) tuples
        where entries is the list of entries extracted from the
        document at filepath by importer.
      output: A file object to write to. The object needs to implement
       a write() method that accepts an unicode string.

    """
    if extracted and HEADER:
        output.write(HEADER + '\n')

    for filepath, entries, account, importer in extracted:
        output.write(SECTION.format(filepath) + '\n\n')

        for entry in entries:
            duplicate = entry.meta.pop(DUPLICATE, False)
            string = printer.format_entry(entry)
            # If the entry is a duplicate, comment it out and report
            # of which other entry this is a duplicate.
            if duplicate:
                if isinstance(duplicate, type(entry)):
                    filename = duplicate.meta.get('filename')
                    lineno = duplicate.meta.get('lineno')
                    if filename and lineno:
                        output.write(f'; duplicate of {filename}:{lineno}\n')
                string = textwrap.indent(string, '; ')
            output.write(string)
            output.write('\n')

        output.write('\n')
