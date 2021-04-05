__copyright__ = "Copyright (C) 2016-2017  Martin Blais"
__license__ = "GNU GPLv2"

import datetime
import inspect
import operator
import textwrap

from beancount.core import data
from beancount.parser import printer

from beangulp import cache
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
    file = cache.get_file(filename)

    # Support calling without the existing entries.
    kwargs = {}
    if 'existing_entries' in inspect.signature(importer.extract).parameters:
        kwargs['existing_entries'] = existing_entries
    entries = importer.extract(file, **kwargs)
    if entries is None:
        entries = []

    # Make sure the newly imported entries are sorted; don't trust the importer.
    entries.sort(key=data.entry_sortkey)

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

    ret = []
    for filepath, entries, account, importer in extracted:

        # Sort the existing entries by date: find_similar_entries()
        # uses bisection to reduce the list of existing entries to the
        # set in a narrow date interval around the date of each entry
        # in the set it is comparing against.
        existing.sort(key=operator.attrgetter('date'))

        # Find duplicates.
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
        ret.append((filepath, marked, account, importer))

        # Append the current batch of extracted entries to the
        # existing entries. This allows to deduplicate entries in the
        # current extraction run.
        existing.extend(marked)

    return ret


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
    if extracted:
        output.write(HEADER + '\n')

    for filepath, entries, account, importer in extracted:
        output.write(SECTION.format(filepath) + '\n\n')

        for entry in entries:
            string = printer.format_entry(entry)
            # If the entry is a duplicate, comment it out.
            if entry.meta.get(DUPLICATE, False):
                string = textwrap.indent(string, '; ')
            output.write(string)
            output.write('\n')

        output.write('\n')
