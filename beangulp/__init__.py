"""Code to help identify, extract, and file external downloads.

This package contains code to help you build importers and drive the
process of identifying which importer to run on an externally
downloaded file, extract transactions from them and file away these
files under a clean and rigidly named hierarchy for preservation.

"""
__copyright__ = "Copyright (C) 2016,2018  Martin Blais"
__license__ = "GNU GPLv2"


import datetime
import difflib
import os
import sys
import io
import warnings
from os import path

import click

from beancount import loader
from typing import Optional
from typing import List
from typing import TextIO
from beancount.core import data
from beancount.parser import printer

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
def _extract(
    ctx: "Ingest",
    src: str,
    output: io.TextIOBase,
    existing: Optional[str],
    reverse: bool,
    failfast: bool,
    quiet: bool,
):
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

    extracted: List[extract.ExtractedEntry] = []
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
def _archive(ctx: 'Ingest', src: str, destination: str, dry_run: bool, overwrite: bool, failfast: bool, quiet: bool):
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
def _identify(ctx: 'Ingest', src: str, failfast: bool, verbose: bool):
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


@click.command("test")
@click.argument("src", nargs=-1, type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--expected",
    "-e",
    metavar="DIR",
    type=click.Path(file_okay=False, resolve_path=True),
    help="Directory containing the expecrted output files.",
)
@click.option("--verbose", "-v", count=True, help="Enable verbose output.")
@click.option("--quiet", "-q", count=True, help="Suppress all output.")
@click.option("--failfast", "-x", is_flag=True, help="Stop at the first test failure.")
@click.pass_obj
def _test(ctx, src: List[str], expected: str, verbose: int, quiet: int, failfast: bool):
    """Test the importer.

    Run the importer on all DOCUMENTS and verify that it produces the
    desired output.  The desired output is stored in Beancount ledger
    files with a header containing additional metadata and can be
    generated with the "generate" command.

    The name of the desired output files is derived appending a
    ".beancount" suffix to the name of the input files, and are
    searched in the same directory where the input document is
    located, unless a different location is specified through the
    "--expected DIR" option.

    DOCUMENTS can be files or directories.  Directories are walked and
    the importer is called on all files with names not ending in
    ".beancount".  All and only the documents for which a desired
    output file exists must be positively identify by the importer.

    """
    return _run(ctx, src, expected, verbose, quiet, failfast=failfast)


@click.command("generate")
@click.argument("src", nargs=-1, type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--expected",
    "-e",
    metavar="DIR",
    type=click.Path(file_okay=False, resolve_path=True),
    help="Directory containing the expecrted output files.",
)
@click.option("--verbose", "-v", count=True, help="Enable verbose output.")
@click.option("--quiet", "-q", count=True, help="Suppress all output.")
@click.option("--force", "-f", is_flag=True, help="Alow to overwrite existing files.")
@click.pass_obj
def _generate(ctx, src: List[str], expected: str, verbose: int, quiet: int, force: bool):
    """Generate expected files for tests.

    Run the importer on all DOCUMENTS and save the import results in
    Beancount ledger files with an header containing additional
    metadata that can be used to as regression tests for the importer.

    The name of the desired output files is derived appending a
    ".beancount" suffix to the name of the input files, and are
    written in the same directory where the input document is located,
    unless a different location is specified through the "--expected
    DIR" option.

    DOCUMENTS can be files or directories.  Directories are walked and
    the importer is called on all files with names not ending in
    ".beancount".

    """
    return _run(ctx, src, expected, verbose, quiet, generate=True, force=force)


def _run(ctx, src, expected, verbose, quiet, generate=False, failfast=False, force=False):
    log = utils.logger(verbose)
    errors = exceptions.ExceptionsTrap(log)

    verbosity = verbose - quiet
    failures = 0

    if len(src) == 0 and "src" in ctx.defaults:
        src = (ctx.defaults["src"],) if isinstance(ctx.defaults["src"], str) else ctx.defaults["src"]

    for filename in _walk(src, log):
        with errors:
            importer = identify.identify(ctx.importers, filename)
            if not importer:
                log("")  # Newline.
                continue

            account = importer.account(filename)
            date = importer.date(filename)
            name = importer.filename(filename)
            entries = extract.extract_from_file(importer, filename, [])

            expected_filename = f"{filename}.beancount"
            if expected:
                expected_filename = path.join(expected, path.basename(expected_filename))

            if generate:
                try:
                    write_expected_file(expected_filename, account, date, name, entries, force=force)
                except FileExistsError as ex:
                    failures += 1
                    log("  ERROR", fg="red")
                    log("  FileExistsError: {}".format(ex.filename))
                    continue
                log("  OK", fg="green")
                continue

            try:
                diff = compare_expected(expected_filename, account, date, name, entries)
            except FileNotFoundError:
                # The importer has positively identified a document
                # for which there is no expecred output file.
                failures += 1
                log("  ERROR", fg="red")
                log("  ExpectedOutputFileNotFound")
                continue
            if diff:
                # Test failure. Log an error.
                failures += 1
                log("  ERROR", fg="red")
                if verbosity >= 0:
                    sys.stdout.writelines(diff)
                    sys.stdout.write(os.linesep)
                    continue
            log("  PASSED", fg="green")

        if failfast and errors:
            break

    if errors:
        sys.exit(1)


def write_expected(
    outfile: TextIO, account: data.Account, date: Optional[datetime.date], name: Optional[str], entries: data.Entries
):
    """Produce the expected output file.

    Args:
      outfile: The file object where to write.
      account: The account name produced by the importer.
      date: The date of the downloads file, produced by the importer.
      name: The filename for filing, produced by the importer.
      entries: The list of entries extracted by the importer.
    """
    date = date.isoformat() if date else ""
    name = name or ""
    print(f";; Account: {account}", file=outfile)
    print(f";; Date: {date}", file=outfile)
    print(f";; Name: {name}", file=outfile)
    printer.print_entries(entries, file=outfile)


def compare_expected(filepath: str, *data) -> List[str]:
    """Compare the expected file with extracted data."""
    with io.StringIO() as buffer:
        write_expected(buffer, *data)
        # rewind to the beginning of the stream
        buffer.seek(0)
        lines_imported = buffer.readlines()

    with open(filepath, "r") as infile:
        lines_expected = infile.readlines()

    diff = difflib.unified_diff(lines_expected, lines_imported, tofile="expected.beancount", fromfile="imported.beancount")
    return list(diff)


def write_expected_file(filepath: str, *data, force: bool = False):
    """Writes out the expected file."""
    mode = "w" if force else "x"
    with open(filepath, mode) as expfile:
        write_expected(expfile, *data)


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
    def __init__(self, importers: list, hooks=None):
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
        cli.add_command(_test)
        cli.add_command(_generate)

        self.cli = cli

    def __call__(self):
        return self.cli()
