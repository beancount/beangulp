import difflib
import hashlib
import io
import os
import sys
import click

from beancount.parser import printer

import beangulp
from beangulp import cache
from beangulp import extract


def walk(paths):
    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for f in files:
                    yield os.path.join(root, f)
            continue
        if os.path.exists(path):
            yield path


def sha1sum(filepath):
    with open(filepath, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def write_expected(f, account, date, name, entries):
    print(f';; Account: {account:}', file=f)
    print(f';; Date: {date:%Y-%m-%d}', file=f)
    print(f';; Name: {name:}', file=f)
    printer.print_entries(entries, file=f)


def write_expected_file(filepath, *data):
    with open(filepath, 'w') as f:
        write_expected(f, *data)


def compare_expected(filepath, *data):
    with io.StringIO() as f:
        write_expected(f, *data)
        # rewind to the beginning of the stream
        f.seek(0)
        lines_imported = f.readlines()

    try:
        with open(filepath, 'r') as f:
            lines_expected = f.readlines()
    except FileNotFoundError:
        lines_expected = []

    diff = difflib.unified_diff(lines_expected, lines_imported,
                                tofile='expected.beancount',
                                fromfile='imported.beancount')
    return list(diff)


def run_importer(importer, f):
    account = importer.file_account(f)
    date = importer.file_date(f)
    name = importer.file_name(f)
    entries = extract.extract_from_file(f.name, importer, None, None)
    return account, date, name, entries


def logger(verbosity):
    def log(msg, level=0, **kwargs):
        if level <= verbosity:
            click.secho(msg, **kwargs)
    return log


@click.command('test', short_help="Test the importer.")
@click.argument('documents',type=click.Path(exists=True), nargs=-1)
@click.option('--expected', '-e', type=click.Path(file_okay=False), metavar='DIR',
              help="Directory containing the expecrted output files.")
@click.option('--generate', '-g', is_flag=True, help="Generate the expected output files.")
@click.option('--verbose', '-v', count=True, help="Enable verbose output.")
@click.option('--quiet', '-q', count=True, help="Suppress all output.")
@click.option('--exitfirst', '-x', is_flag=True, help="Stop at the first test failure.")
@click.pass_obj
def _test(ctx, documents, expected, generate, verbose, quiet, exitfirst):
    """Run the importer on all DOCUMENTS and verify that it produces the
    desired output.  The desired output is stored in Beancount ledger
    files with an header containing additional metadata.  These files
    are named as the SHA1 digest of the documents and can be generated
    with the --generate option.

    DOCUMENTS can be files or directories.  Directories are walked and
    the importer is called on all files.  When no DOCUMENTS path is
    specified on the command line, the tests/documents/ directory
    relative to the test script location is used.  All documents for
    which an expected output file exist must be positively identified
    by the importer.

    Expected output files are searched in the tests/expected/$NAME/
    directory relative to the test script location, where $NAME is
    replaced with the importer name, if the path exists, or in the
    tests/expected/ directory.  This path can be overwritten through
    the --expected DIR option.

    """
    assert len(ctx.importers) == 1
    importer = ctx.importers[0]

    import __main__
    root = os.path.dirname(__main__.__file__)

    if not documents:
        documents = (os.path.join(root, 'tests','documents'), )

    if not expected:
        expected = os.path.join(root, 'tests', 'expected', importer.name())
        if not os.path.exists(expected):
            expected = os.path.join(root, 'tests', 'expected')

    verbosity = verbose - quiet
    log = logger(verbosity)
    failures = 0

    for doc in walk(documents):
        # unless verbose mode is enabled, do not output a newline so
        # the test result is printed on the same line as the test
        # document filename.
        log(f'∙ {os.path.relpath(doc):}', nl=verbosity > 0)

        # compute the path to the expected output file
        path = os.path.join(expected, sha1sum(doc) + '.beancount')
        f = cache.get_file(os.path.abspath(doc))

        if importer.identify(f):
            account, date, name, entries = run_importer(importer, f)
            log(f'  {os.path.relpath(path):}', 1)
            log(f'  {account.replace(":", "/"):}/{date:%Y-%m-%d}-{name:}', 1)
            if generate:
                write_expected_file(path, account, date, name, entries)
                log('  OK', fg='green')
                continue
            diff = compare_expected(path, account, date, name, entries)
            if not diff:
                log('  PASSED', fg='green')
                continue
            # test failure
            failures += 1
            log('  ERROR', fg='red')
            if verbosity >= 0:
                sys.stdout.writelines(diff)
                sys.stdout.write(os.linesep)

        elif os.path.exists(path):
            # the importer has not identified a document it should have
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


def wrap(importer):
    main = beangulp.Ingest([importer]).main
    main.help = importer.__doc__
    main.add_command(_test)
    return main


def main(importer):
    main = wrap(importer)
    main()
