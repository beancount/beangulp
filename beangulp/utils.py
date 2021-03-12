import os
import datetime

from os import path
from typing import Iterator, Sequence

import click


def getmdate(filepath: str) -> datetime.date:
    """Return file modification date."""
    mtime = path.getmtime(filepath)
    return datetime.datetime.fromtimestamp(mtime).date()


    """Convenient logging method factory."""
    color = False if os.getenv('TERM', '') in ('', 'dumb') else None
    def log(msg, level=0, **kwargs):
        if level <= verbosity:
            click.secho(msg, color=color, **kwargs)
    return log


def walk(paths: Sequence[str]) -> Iterator[str]:
    """Yield all the files under paths.

    Takes a sequence of file or directory paths. Directories are
    traversed with os.walk() and complete file paths are returned
    joining filenames to the root directory path. Other elements of
    the list are assumed to be file paths and returned unchanged.

    Args:
      paths: List of filesystems paths.

    Yields:
      Filesystem paths of all the files under paths.

    """
    for file_or_dir in paths:
        if path.isdir(file_or_dir):
            for root, dirs, files in os.walk(file_or_dir):
                for filename in sorted(files):
                    yield path.join(root, filename)
            continue
        yield file_or_dir
