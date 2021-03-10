__copyright__ = "Copyright (C) 2016-2017  Martin Blais"
__license__ = "GNU GPLv2"

import inspect
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


def print_extracted_entries(extracted, output):
    """Print extracgted entries.

    Entries marked as duplicates are printed as comments.

    Args:
      extracted: List of (filepath, entries) tuples where entries is
        the list of ledger entries extracted from the filepath.
      output: A file object to write to. The object just need to
       implement a .write() method.

    """
    if extracted:
        output.write(HEADER + '\n')

    for filepath, entries in extracted:
        output.write(SECTION.format(filepath) + '\n\n')

        for entry in entries:
            string = printer.format_entry(entry)
            # If the entry is a duplicate, comment it out.
            if entry.meta.get(DUPLICATE, False):
                string = textwrap.indent(string, '; ')
            output.write(string)
            output.write('\n')

        output.write('\n')
