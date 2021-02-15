"""Implementation of testing and generate functionality."""

from os import path
from typing import Callable, Iterator, List, Optional, Tuple
import datetime
import difflib
import hashlib
import io
import os
import re
import sys

import click

from beancount.parser import printer
from beancount.core import data
from beancount.core.data import Account

import beangulp
from beangulp.importer import ImporterProtocol
from beangulp import cache
from beangulp import extract


def walk(paths: str, ignore: str) -> Iterator[str]:
    """Yield all the files under 'paths'.

    Args:
      paths: A list of filenames and/or directory names.
      ignore: A regular expression for filenames to ignore.
    Yields:
      Absolute filenames not matching 'ignore'.
    """
    for file_or_dir in paths:
        file_or_dir = path.normpath(file_or_dir)
        if path.isdir(file_or_dir):
            for root, dirs, files in os.walk(file_or_dir):
                for filename in sorted(files):
                    if not re.match(ignore, filename):
                        yield path.join(root, filename)
            continue
        if path.exists(file_or_dir):
            if not re.match(ignore, file_or_dir):
                yield file_or_dir


def sha1sum(filepath: str) -> str:
    """Compute hash of given filename"""
    with open(filepath, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def write_expected(outfile: str,
                   account: Account,
                   date: Optional[datetime.date],
                   name: Optional[str],
                   entries: data.Entries):
    """Produce expected file.

    Args:
      outfile: The name of the expected filename to write.
      account: The account name produced by the importer.
      date: The date of the downloads file, produced by the importer.
      name: The filename for filing, produced by the importer.
      entries: The list of entries extracted by the importer.
    """
    print(';; Account: {}'.format(account), file=outfile)
    print(';; Date: {}'.format(date.isoformat() if date else ''), file=outfile)
    print(';; Name: {}'.format(name or ''), file=outfile)
    printer.print_entries(entries, file=outfile)


def write_expected_file(filepath: str, *data, force: bool = False):
    """Writes out the expected file."""
    mode = 'w' if force else 'x'
    with open(filepath, mode) as expfile:
        write_expected(expfile, *data)


def compare_expected(filepath: str, *data) -> List[str]:
    """Compare the expected file with extracted data."""
    with io.StringIO() as buffer:
        write_expected(buffer, *data)
        # rewind to the beginning of the stream
        buffer.seek(0)
        lines_imported = buffer.readlines()

    with open(filepath, 'r') as infile:
        lines_expected = infile.readlines()

    diff = difflib.unified_diff(lines_expected, lines_imported,
                                tofile='expected.beancount',
                                fromfile='imported.beancount')
    return list(diff)


def run_importer(importer: ImporterProtocol,
                 cfile: cache._FileMemo) -> Tuple[Account,
                                                  Optional[datetime.date],
                                                  Optional[str],
                                                  data.Entries]:
    """Run the various importer methods on the given cached file."""
    account = importer.file_account(cfile)
    date = importer.file_date(cfile)
    name = importer.file_name(cfile)
    entries = extract.extract_from_file(cfile.name, importer, None, None)
    return account, date, name, entries


def modification_date(filepath: str) -> datetime.date:
    """Return file modification date."""
    mtime = path.getmtime(filepath)
    return datetime.datetime.fromtimestamp(mtime).date()


def logger(verbosity: int):
    """Convenient logging method factory."""
    color = False if os.getenv('TERM', '') in ('', 'dumb') else None
    def log(msg, level=0, **kwargs):
        if level <= verbosity:
            click.secho(msg, color=color, **kwargs)
    return log


@click.command('test')
@click.argument('documents', nargs=-1,
                type=click.Path(exists=True, resolve_path=True))
@click.option('--expected', '-e', metavar='DIR',
              type=click.Path(file_okay=False, resolve_path=True),
              help="Directory containing the expecrted output files.")
@click.option('--verbose', '-v', count=True,
              help="Enable verbose output.")
@click.option('--quiet', '-q', count=True,
              help="Suppress all output.")
@click.option('--exitfirst', '-x', is_flag=True,
              help="Stop at the first test failure.")
@click.pass_obj
def _test(ctx,
          documents: List[str],
          expected: str,
          verbose: int,
          quiet: int,
          exitfirst: bool):
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
    return _run(ctx, documents, expected, verbose, quiet, exitfirst=exitfirst)


@click.command('generate')
@click.argument('documents', nargs=-1,
                type=click.Path(exists=True, resolve_path=True))
@click.option('--expected', '-e', metavar='DIR',
              type=click.Path(file_okay=False, resolve_path=True),
              help="Directory containing the expecrted output files.")
@click.option('--verbose', '-v', count=True,
              help="Enable verbose output.")
@click.option('--quiet', '-q', count=True,
              help="Suppress all output.")
@click.option('--force', '-f', is_flag=True,
              help='Alow to overwrite existing files.')
@click.pass_obj
def _generate(ctx,
              documents: List[str],
              expected: str,
              verbose: int,
              quiet: int,
              force: bool):
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
    return _run(ctx, documents, expected, verbose, quiet, generate=True, force=force)


def _run(ctx,
         documents: List[str],
         expected: str,
         verbose: int,
         quiet: int,
         generate: bool = False,
         exitfirst: bool = False,
         force: bool = False):
    """Do it."""

    assert len(ctx.importers) == 1
    importer = ctx.importers[0]

    verbosity = verbose - quiet
    log = logger(verbosity)
    failures = 0

    for doc in walk(documents, r".*\.beancount$"):
        # Unless verbose mode is enabled, do not output a newline so
        # the test result is printed on the same line as the test
        # document filename.
        log(f'* {doc}', nl=verbosity > 0)

        # Compute the path to the expected output file.
        expected_filename = f"{doc}.beancount"
        if expected:
            expected_filename = path.join(expected, path.basename(expected_filename))

        # Use the in-memory cache.
        # TODO(blais): This will get replaced by an on-disk cache.
        cached_file = cache.get_file(path.abspath(doc))

        # Run the importer's identify() method.
        if importer.identify(cached_file):
            account, date, name, entries = run_importer(importer, cached_file)
            log(f'  {expected_filename}', 1)
            if account is None:
                failures += 1
                log('  ERROR', fg='red')
                log('  ValueError: account() should not return None')
                continue
            log('  {}/{:%Y-%m-%d}-{}'.format(
                account.replace(":", "/"),
                date or modification_date(doc),
                name or path.basename(doc)), 1)
            if generate:
                try:
                    write_expected_file(expected_filename, account, date, name, entries,
                        force=force)
                except FileExistsError as ex:
                    failures += 1
                    log('  ERROR', fg='red')
                    log('  FileExistsError: {}'.format(ex.filename))
                    continue
                log('  OK', fg='green')
                continue
            try:
                diff = compare_expected(expected_filename, account, date, name, entries)
            except FileNotFoundError:
                # The importer has positively identified a document
                # for which there is no expecred output file.
                failures += 1
                log('  ERROR', fg='red')
                log('  ExpectedOutputFileNotFound')
                continue
            if diff:
                # Test failure. Log an error.
                failures += 1
                log('  ERROR', fg='red')
                if verbosity >= 0:
                    sys.stdout.writelines(diff)
                    sys.stdout.write(os.linesep)
                    continue
            log('  PASSED', fg='green')

        elif path.exists(expected_filename):
            # The importer has not identified a document it should have.
            failures += 1
            log('  ERROR', fg='red')
            log('  DocumentNotIdentified')

        else:
            # ignore files that are not positively identified by the
            # importer and for which there is no expected output file.
            log('  IGNORED')

        if exitfirst and failures:
            break

    if failures:
        sys.exit(1)


def wrap(importer: ImporterProtocol) -> Callable[[], None]:
    """Wrap a single importer for ingestion."""
    main = beangulp.Ingest([importer]).main
    main.help = importer.__doc__
    main.add_command(_test)
    main.add_command(_generate)
    return main


def main(importer: ImporterProtocol):
    """Call main program on a single importer. This is the main entry point."""
    main = wrap(importer)
    main()
