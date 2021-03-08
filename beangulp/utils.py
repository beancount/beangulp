import os
from os import path
from typing import Iterator
import click


def logger(verbosity: int = 0):
    """Convenient logging method factory."""
    color = False if os.getenv('TERM', '') in ('', 'dumb') else None
    def log(msg, level=0, **kwargs):
        if level <= verbosity:
            click.secho(msg, color=color, **kwargs)
    return log


def walk(paths: str) -> Iterator[str]:
    """Yield all the files under 'paths'.

    Args:
      paths: A list of filenames and/or directory names.
    Yields:
      Absolute filenames.
    """
    for file_or_dir in paths:
        if path.isdir(file_or_dir):
            for root, dirs, files in os.walk(file_or_dir):
                for filename in sorted(files):
                    yield path.join(root, filename)
            continue
        yield file_or_dir
