"""Code that guesses a MIME type for a filename.

This attempts to identify the mime-type of a file using the built-in
mimetypes library, augmented with MIME types commonly used in
financial downloads.  If this does not produce any match it falls back
to MIME type sniffing using ``python-magic``, if available.

This module is deprecated. Please use ``beancount.mimetypes`` instead.

"""
__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import warnings
from typing import Optional
from beangulp import mimetypes


# python-magic is an optional dependency.
try:
    import magic
except (ImportError, OSError):
    magic = None  # type: ignore


def guess_file_type(filename: str) -> Optional[str]:
    """Attempt to guess the type of the input file.

    Args:
      filename: A string, the name of the file to guess the type for.
    Returns:
      A suitable mimetype string, or None if we could not guess.
    """

    warnings.warn('beangulp.file_type.guess_file_type() is deprecated. '
                  'Use the beangulp.mimetypes module instead.',
                  DeprecationWarning, stacklevel=2)

    filetype, encoding = mimetypes.guess_type(filename, strict=False)
    if filetype:
        return filetype

    if magic:
        filetype = magic.from_file(filename, mime=True)
        if isinstance(filetype, bytes):
            filetype = filetype.decode('utf8')

    return filetype
