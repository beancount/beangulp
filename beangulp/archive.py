__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import os
import re
import shutil

from beancount.utils import misc_utils
from beangulp import cache
from beangulp import utils
from beangulp.exceptions import Error


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
    file = cache.get_file(filepath)

    # Get the account corresponding to the file.
    account = importer.file_account(file)
    filename = importer.file_name(file) or os.path.basename(file.name)
    date = importer.file_date(file) or utils.getmdate(file.name)

    # The returned filename cannot contain the file path separator character.
    if os.sep in filename:
        raise Error("The filename contains path separator character.")

    if re.match(r'\d\d\d\d-\d\d-\d\d', filename):
        raise Error("The filename contains what looks like a date.")

    # Remove whitespace and other funny characters from the filename.
    # TODO(dnicolodi): This should probably be importer responsibility.
    filename = misc_utils.idify(filename)

    # Prepend account directory and date prefix.
    filename = os.path.join(account.replace(':', os.sep), f'{date:%Y-%m-%d}.{filename:}')

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
