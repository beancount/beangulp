"""Implementation of testing and generate functionality."""

from os import path
from typing import Callable, List, Optional, TextIO, Tuple, Union
import datetime
import difflib
import io
import os
import sys
import warnings

import click

from beancount.parser import printer
from beancount.core import data

import beangulp
from beangulp.importer import Importer, ImporterProtocol
from beangulp import extract
from beangulp import utils


def write_expected(outfile: TextIO,
                   account: data.Account,
                   date: Optional[datetime.date],
                   name: Optional[str],
                   entries: data.Entries):
    """Produce the expected output file.

    Args:
      outfile: The file object where to write.
      account: The account name produced by the importer.
      date: The date of the downloads file, produced by the importer.
      name: The filename for filing, produced by the importer.
      entries: The list of entries extracted by the importer.
    """
    formatted_date = date.isoformat() if date else ''
    name = name or ''
    print(f';; Account: {account}', file=outfile)
    print(f';; Date: {formatted_date}', file=outfile)
    print(f';; Name: {name}', file=outfile)
    printer.print_entries(entries, file=outfile)


def write_expected_file(filepath: str, *data, force: bool = False):
    """Writes out the expected file."""
    mode = 'w' if force else 'x'
    with open(filepath, mode) as expfile:
        write_expected(expfile, *data)  # type: ignore


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


def run_importer(importer: Importer,
                 document: str) -> Tuple[data.Account,
                                         Optional[datetime.date],
                                         Optional[str],
                                         data.Entries]:
    """Run the various importer methods on the given cached file."""
    account = importer.account(document)
    date = importer.date(document)
    name = importer.filename(document)
    entries = extract.extract_from_file(importer, document, [])
    return account, date, name, entries


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
@click.option('--failfast', '-x', is_flag=True,
              help="Stop at the first test failure.")
@click.pass_obj
def _test(ctx,
          documents: List[str],
          expected: str,
          verbose: int,
          quiet: int,
          failfast: bool):
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
    return _run(ctx, documents, expected, verbose, quiet, failfast=failfast)


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
         failfast: bool = False,
         force: bool = False):
    """Implement the test and generate commands."""

    assert len(ctx.importers) == 1
    importer = ctx.importers[0]

    verbosity = verbose - quiet
    log = utils.logger(verbosity)
    failures = 0

    for doc in utils.walk(documents):
        if doc.endswith('.beancount'):
            continue

        # Unless verbose mode is enabled, do not output a newline so
        # the test result is printed on the same line as the test
        # document filename.
        log(f'* {doc}', nl=verbosity > 0)

        # Compute the path to the expected output file.
        expected_filename = f"{doc}.beancount"
        if expected:
            expected_filename = path.join(expected, path.basename(expected_filename))

        # Run the importer's identify() method.
        if importer.identify(doc):
            account, date, name, entries = run_importer(importer, doc)
            log(f'  {expected_filename}', 1)
            if account is None:
                failures += 1
                log('  ERROR', fg='red')
                log('  ValueError: account() should not return None')
                continue
            log('  {}/{:%Y-%m-%d}-{}'.format(
                account.replace(":", "/"),
                date or utils.getmdate(doc),
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
            # Ignore files that are not positively identified by the
            # importer and for which there is no expected output file.
            log('  IGNORED')

        if failfast and failures:
            break

    if failures:
        sys.exit(1)


def wrap(importer: Union[Importer, ImporterProtocol]) -> Callable[[], None]:
    """Wrap a single importer for ingestion."""
    cli = beangulp.Ingest([importer]).cli
    cli.help = importer.__doc__
    cli.add_command(_test)
    cli.add_command(_generate)
    return cli


def main(importer: Union[Importer, ImporterProtocol]):
    """Call main program on a single importer. This is the main entry point."""
    if not sys.warnoptions:
        # Even if DeprecationWarnings are ignored by default print
        # them anyway unless other warnings settings are specified by
        # the -W Python command line flag.
        warnings.simplefilter('default')
    main = wrap(importer)
    main()
