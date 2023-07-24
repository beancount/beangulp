__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import os
import re
import shutil

from beangulp import utils
from beangulp.exceptions import Error


# Template for the documents archival name.
FILENAME = '{date:%Y-%m-%d}.{name}'


def filepath(importer, filepath: str) -> str:
    """Compute filing path for a document.

    The path mirrors the structure of the accounts associated to the
    documents and with a file name composed by the document date and
    document name returned by the importer.

    Args:
      importer: The importer instance to handle the document.
      filepath: Filesystem path to the document.

    Returns:
      Filing tree location where to store the document.

    Raises:
      beangulp.exceptions.Error: The canonical file name returned by
      the importer contains a path separator charachter or seems to
      contain a date.

    """
    # Get the account corresponding to the file.
    account = importer.account(filepath)
    filename = importer.filename(filepath) or os.path.basename(filepath)
    date = importer.date(filepath) or utils.getmdate(filepath)

    # The returned filename cannot contain the file path separator character.
    if os.sep in filename:
        raise Error("The filename contains path separator character.")

    if re.match(r'\d\d\d\d-\d\d-\d\d\.', filename):
        raise Error("The filename contains what looks like a date.")

    # Prepend account directory and date prefix.
    filename = os.path.join(account.replace(':', os.sep), FILENAME.format(date=date, name=filename))

    return filename


def move(src: str, dst: str):
    """Move a file, potentially across devices.

    The destination direcory, and all intermediate path segments, are
    created if they do not exist. The move is performed with the
    shutil.move() function. See the documentation of this function for
    details of the semantic.

    Args:
      src: Filesystem path of the file to move.
      dst: Desitnation filesytem path. For the creation of the
        destination directory, this is assumed to be a file path and
        not a directory, namely the directory structure up to only
        path.dirname(dst) is created.

    """
    # Create missing directories.
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    # Copy the file to its new name: use shutil.move() instead of
    # os.rename() to support moving across filesystems.
    shutil.move(src, dst)
