"""Code to help identify, extract, and file external downloads.

This package contains code to help you build importers and drive the
process of identifying which importer to run on an externally
downloaded file, extract transactions from them and file away these
files under a clean and rigidly named hierarchy for preservation.

"""
__copyright__ = "Copyright (C) 2016,2018  Martin Blais"
__license__ = "GNU GPLv2"


import os
import sys
import warnings
import click
from typing import Any, Optional, Union, Sequence

from beancount import loader

from beangulp import archive
from beangulp import cache  # noqa: F401
from beangulp import exceptions
from beangulp import extract
from beangulp import identify
from beangulp import utils
from beangulp.importer import Importer, ImporterProtocol, Adapter


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
@click.option('--failfast', '-x', is_flag=True,
              help='Stop processing at the first error.')
@click.option('--quiet', '-q', count=True,
              help='Suppress all output.')
@click.pass_obj
def _extract(ctx, src, output, existing, reverse, failfast, quiet):
    """Extract transactions from documents.

    Walk the SRC list of files or directories and extract the ledger
    entries from each file identified by one of the configured
    importers.  The entries are written to the specified output file
    or to the standard output in Beancount ledger format in sections
    associated to the source document.

    """
    verbosity = -quiet
    log = utils.logger(verbosity, err=True)
    errors = exceptions.ExceptionsTrap(log)

    # Load the ledger, if one is specified.
    existing_entries = loader.load_file(existing)[0] if existing else []

    extracted = []
    for filename in _walk(src, log):
        with errors:
            importer = identify.identify(ctx.importers, filename)
            if not importer:
                log('') # Newline.
                continue

            # Signal processing of this document.
            log(' ...', nl=False)

            # Extract entries.
            entries = extract.extract_from_file(importer, filename, existing_entries)
            account = importer.account(filename)

            extracted.append((filename, entries, account, importer))
            log(' OK', fg='green')

        if failfast and errors:
            break

    # Sort.
    extract.sort_extracted_entries(extracted)

    # Deduplicate.
    for filename, entries, account, importer in extracted:
        importer.deduplicate(entries, existing_entries)
        existing_entries.extend(entries)

    # Invoke hooks.
    for func in ctx.hooks:
        extracted = func(extracted, existing_entries)

    # Serialize entries.
    extract.print_extracted_entries(extracted, output)

    if errors:
        sys.exit(1)


@click.command('archive')
@click.argument('src', nargs=-1, type=click.Path(exists=True, resolve_path=True))
@click.option('--destination', '-o', metavar='DIR',
              type=click.Path(exists=True, file_okay=False, resolve_path=True),
              help='The destination documents tree root directory.')
@click.option('--overwrite', '-f', is_flag=True,
              help='Overwrite destination files with the same name.')
@click.option('--dry-run', '-n', is_flag=True,
              help='Just print where the files would be moved.')
@click.option('--failfast', '-x', is_flag=True,
              help='Stop processing at the first error.')
@click.option('--quiet', '-q', count=True,
              help='Suppress all output.')
@click.pass_obj
def _archive(ctx, src, destination, dry_run, overwrite, failfast, quiet):
    """Archive documents.

    Walk the SRC list of files or directories and move each file
    identified by one of the configured importers in a directory
    hierarchy mirroring the structure of the accounts associated to
    the documents and with a file name composed by the document date
    and document name returned by the importer.

    Documents are moved to their filing location only when no errors
    are encountered processing all the input files.  Documents in the
    destination directory are not overwritten, unless the --force
    option is used.  When the directory hierarchy root is not
    specified with the --destination DIR options, it is assumed to be
    directory in which the ingest script is located.

    """
    # If the output directory is not specified, move the files at the
    # root where the import script is located. Providing this default
    # seems better than using a required option.
    if destination is None:
        import __main__
        destination = os.path.dirname(os.path.abspath(__main__.__file__))

    verbosity = -quiet
    log = utils.logger(verbosity, err=True)
    errors = exceptions.ExceptionsTrap(log)
    renames = []

    for filename in _walk(src, log):
        with errors:
            importer = identify.identify(ctx.importers, filename)
            if not importer:
                log('') # Newline.
                continue

            # Signal processing of this document.
            log(' ...', nl=False)

            destpath = archive.filepath(importer, filename)

            # Prepend destination directory path.
            destpath = os.path.join(destination, destpath)

            # Check for destination filename collisions.
            collisions = [src for src, dst in renames if dst == destpath]
            if collisions:
                raise exceptions.Error('Collision in destination file path.', destpath)

            # Check if the destination file already exists.
            if not overwrite and os.path.exists(destpath):
                raise exceptions.Error('Destination file already exists.', destpath)

            renames.append((filename, destpath))
            log(' OK', fg='green')
            log(f'  {destpath:}')

        if failfast and errors:
            break

    # If there are any errors, stop here.
    if errors:
        log('# Errors detected: documents will not be filed.')
        sys.exit(1)

    if not dry_run:
        for filename, destpath in renames:
            archive.move(filename, destpath)


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
            account = importer.account(filename) if verbose else None

            log(' OK', fg='green')
            log(f'  {importer.name:}')
            log(f'  {account:}', 1)

        if failfast and errors:
            break

    if errors:
        sys.exit(1)


def _importer(importer):
    """Check that the passed instance implements the Importer interface.

    Wrap ImporterProtocol instances with Adapter as needed.

    """
    if isinstance(importer, Importer):
        return importer
    if isinstance(importer, ImporterProtocol):
        warnings.warn('The beangulp.importer.ImporterProtocol interface for '
                      'importers has been replaced by the beangulp.Importer '
                      'interface and is therefore deprecated. Please update '
                      'your importer {} to the new interface.'.format(importer),
                      stacklevel=3)
        return Adapter(importer)
    raise TypeError(f'expected bengulp.Importer not {type(importer):}')


class Ingest:
    def __init__(self, importers: Sequence[Union[Importer, ImporterProtocol]], hooks: Optional[Sequence[Any]] = None) -> None:
        self.importers = [_importer(i) for i in importers]
        self.hooks = list(hooks) if hooks is not None else []

        while extract.find_duplicate_entries in self.hooks:
            self.hooks.remove(extract.find_duplicate_entries)
            warnings.warn('beangulp.extract.find_duplicate_entries has been removed '
                          'from the import hooks. Deduplication is now integral part '
                          'of the extract processing and can be customized by the '
                          'importers. See beangulp.importer.Importer.', stacklevel=2)

        @click.group('beangulp')
        @click.version_option()
        @click.pass_context
        def cli(ctx):
            """Import data from and file away documents from financial institutions."""
            ctx.obj = self

        cli.add_command(_archive)
        cli.add_command(_extract)
        cli.add_command(_identify)

        self.cli = cli

    def __call__(self):
        return self.cli()
