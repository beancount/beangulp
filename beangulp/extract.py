__copyright__ = "Copyright (C) 2016-2017  Martin Blais"
__license__ = "GNU GPLv2"

import bisect
import datetime
import operator
import textwrap

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

    # Deduplicate.
    entries = importer.deduplicate(entries, existing_entries)

    # Sort the newly imported entries.
    importer.sort(entries)

    # Ensure that the entries are typed correctly.
    for entry in entries:
        data.sanity_check_types(entry)

    return entries


def find_duplicate_entries(extracted, existing):
    """Flag potentially duplicate entries.

    Args:
      extracted: List of (filepath, entries) tuples where entries is
        the list of ledger entries extracted from the filepath.
      existing: Existing entries.

    Returns:
      A copy of the list of new entries with the potentially duplicate
      entries marked setting the "__duplicate__" metadata field to True.

    """
    ret = []
    for filepath, entries in extracted:
        pairs = similar.find_similar_entries(entries, existing)
        # We could do something smarter than trowing away the
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
        ret.append((filepath, marked))
    return ret


def mark_duplicate_entries(
        entries: data.Entries,
        existing: data.Entries,
        window: datetime.timedelta,
        compare: Callable[[data.Directive, data.Directive], bool]) -> data.Entries:
    """Mark duplicate entries.

    Compare newly extracted entries to the existing entries. Only
    existing entries dated within the given time window around the
    date of the each existing entry.

    Args:
      entries: Entries to be deduplicated.
      existing: Existing entries.
      window: Time window in which entries are compared.
      compare: Entry comparison function.

    Returns:
      A new list of entries where duplicates have been marked setting
      the "__duplicate__" metadata field to True.

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

    marked = []
    for entry in entries:
        for target in entries_date_window_iterator(entry.date):
            if compare(entry, target):
                meta = entry.meta.copy()
                meta[DUPLICATE] = True
                entry = entry._replace(meta=meta)
        marked.append(entry)
    return marked


def print_extracted_entries(extracted, output, no_sections=False):
    """Print extracted entries.

    Entries marked as duplicates are printed as comments.

    Args:
      extracted: List of (filepath, entries) tuples where entries is
        the list of ledger entries extracted from the filepath.
      output: A file object to write to. The object just need to
       implement a .write() method.

    """
    if extracted:
        output.write(HEADER + '\n')

    if not no_sections:
        print_with_sections(extracted, output)
    else:
        print_without_sections(extracted, output)


def print_without_sections(extracted, output):
    merged = []
    for _, entries in extracted:
        for entry in entries:
            merged.append(entry)
    print_entries(sorted(merged, key=lambda x: x.date), output)


def print_with_sections(extracted, output):
    for filepath, entries in extracted:
        output.write(SECTION.format(filepath) + '\n\n')

        print_entries(entries, output)
        output.write('\n')


def print_entries(entries, output):
    for entry in entries:
        duplicate = entry.meta.pop(DUPLICATE, False)
        string = printer.format_entry(entry)
        # If the entry is a duplicate, comment it out.
        if duplicate:
            string = textwrap.indent(string, '; ')
        output.write(string)
        output.write('\n')
