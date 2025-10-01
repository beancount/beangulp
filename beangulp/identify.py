__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

from typing import List, Optional
from beangulp.exceptions import Error
from beangulp.importer import Importer


# A file size beyond which we will simply ignore the file. This is
# used to skip large files that are commonly present in a Downloads
# directory.
FILE_TOO_LARGE_THRESHOLD = 8 * 1024 * 1024


def identify(importers: List[Importer], filepath: str) -> Optional[Importer]:
    """Identify the correct importer to handle a document.

    Args:
      importers: List of importer instances.
      filepath: Filesystem path to the document.

    Returns:
      The correct importer to handle the document or None if no importer
      matches the document.

    Raises:
      beangulp.exceptions.Error: More than one importer matched the file.

    """
    match = [importer for importer in importers if importer.identify(filepath)]
    if len(match) > 1:
        match = [f"  {importer.name}" for importer in match]
        raise Error("Document identified by more than one importer.", *match)

    return match[0] if match else None
