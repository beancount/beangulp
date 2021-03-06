"""Code to help identify, extract, and file external downloads.

This package contains code to help you build importers and drive the process of
identifying which importer to run on an externally downloaded file, extract
transactions from them and file away these files under a clean and rigidly named
hierarchy for preservation.
"""
__copyright__ = "Copyright (C) 2016,2018  Martin Blais"
__license__ = "GNU GPLv2"


import os
import sys
import click

from beancount import loader
from beangulp import cache
from beangulp import exceptions
from beangulp import extract
from beangulp import file
from beangulp import identify
from beangulp import importer
from beangulp import utils


def _walk(file_or_dirs, log):
    """Convenience wrapper around beangulp.utils.walk()

    Log the name of the file being processed and check the input file
    size against identify.FILE_TOO_LARGE_THRESHOLD for too large input.

    """
    for filename in utils.walk(file_or_dirs):
        log(f'* {filename:}', nl=False)
        if os.path.getsize(filename) > identify.FILE_TOO_LARGE_THRESHOLD:
            log(' ... SKIP')
            continue
        yield filename


@click.command('extract')
@click.argument('src', nargs=-1, type=click.Path(exists=True, resolve_path=True))
@click.option('--output', '-o', type=click.File('w'), default='-',
              help='Output file.')
@click.option('--existing', '-e', type=click.Path(exists=True),
              help='Existing Beancount ledger for de-duplication.')
@click.option('--reverse', '-r', is_flag=True,
              help='Sort entries in reverse order.')
@click.pass_obj
def _extract(ctx, src, output, existing, reverse):
    """Extract transactions from documents."""

    # Load the ledger, if one is specified.
    entries = loader.load_file(existing)[0] if existing else None

    ctx.extract(src, output, entries=entries, reverse=reverse)


@click.command('file')
@click.argument('src', nargs=-1, type=click.Path(exists=True, resolve_path=True))
@click.option('--destination', '-o',
              type=click.Path(exists=True, file_okay=False), metavar='DIR',
              help='The destination documents tree root directory.')
@click.option('--dry-run', '-n', is_flag=True,
              help='Just print where the files would be moved.')
@click.option('--overwrite', '-f', is_flag=True,
              help='Overwrite destination files with the same name.')
@click.pass_obj
def _file(ctx, src, destination, dry_run, overwrite):
    """File away documents.

    Walk the list of SRC filenames or directories of downloaded files,
    and for each of those files, move the file under a filing
    directory corresponding to the assocaited account.

    """
    # If the output directory is not specified, move the files at the
    # root where the import script is located. Providing this default
    # seems better than using a required option.
    if destination is None:
        import __main__
        destination = os.path.dirname(os.path.abspath(__main__.__file__))

    ctx.file(src, destination,
             dry_run=dry_run,
             mkdirs=True,
             overwrite=overwrite,
             idify=True,
             logfile=sys.stdout)


@click.command('identify')
@click.argument('src', nargs=-1, type=click.Path(exists=True, resolve_path=True))
@click.option('--failfast', '-x', is_flag=True,
              help='Stop processing at the first error.')
@click.option('--verbose', '-v', is_flag=True,
              help='Show account information.')
@click.pass_obj
def _identify(ctx, src, failfast, verbose):
    """Identify files for import.

    Walk the SRC list of files or directories and report each file
    identified by one of the configured importers.  When verbose
    output is requested, also print the account name associated to the
    document by the importer.

    """
    log = utils.logger(verbose)
    errors = exceptions.ExceptionsTrap(log)

    for filename in _walk(src, log):
        with errors:
            importer = identify.identify(ctx.importers, filename)
            if not importer:
                log('') # Newline.
                continue

            # Signal processing of this document.
            log(' ...', nl=False)

            # When verbose output is requested, get the associated account.
            account = importer.file_account(cache.get_file(filename)) if verbose else None

            log(' OK', fg='green')
            log(f'  {importer.name():}')
            log(f'  {account:}', 1)

        if failfast and errors:
            break

    if errors:
        sys.exit(1)


class Ingest:
    def __init__(self, importers, hooks=None):
        self.importers = importers
        self.hooks = hooks

        @click.group()
        @click.version_option()
        @click.pass_context
        def main(ctx):
            """Import data from and file away documents from financial institutions."""
            ctx.obj = self

        main.add_command(_extract)
        main.add_command(_file)
        main.add_command(_identify)

        self.main = main

    def extract(self, what, *args, **kwargs):
        extract.extract(self.importers, what, *args, hooks=self.hooks, **kwargs)

    def file(self, what, *args, **kwargs):
        file.file(self.importers, what, *args, **kwargs)

    def __call__(self):
        return self.main()
