Setup
-----

  >>> from os import mkdir, path, unlink
  >>> from shutil import rmtree
  >>> from tempfile import mkdtemp
  >>> import click.testing
  >>> import beangulp
  >>> from beangulp.tests.utils import Importer

An importer to create error conditions:

  >>> class ErrorImporter(Importer):
  ...
  ...     def identify(self, f):
  ...         name = path.basename(f.name)
  ...         # An exception raised from importer code.
  ...         if name == 'error.txt':
  ...             raise ValueError(name)
  ...         # A collision in identification.
  ...         if name == 'error.csv':
  ...             return True
  ...         return False

Test harness:

  >>> importers = [
  ...     Importer('test.ImporterA', 'Assets:Tests', 'text/csv'),
  ...     ErrorImporter('test.ImporterB', 'Assets:Tests', None),
  ... ]
  >>> runner = click.testing.CliRunner()
  >>> def run(*args):
  ...     func = beangulp.Ingest(importers).main
  ...     return runner.invoke(func, args, catch_exceptions=False)

Create a dowloads directory:

  >>> temp = mkdtemp()
  >>> downloads = path.join(temp, 'downloads')
  >>> mkdir(downloads)


Tests
-----

The basics:

  >>> r = run('identify', '--help')
  >>> r.exit_code
  0
  >>> print(r.output)
  Usage: main identify [OPTIONS] [SRC]...

Test with an empty downloads directory:

  >>> r = run('identify', downloads)
  >>> r.exit_code
  0
  >>> print(r.output)

Add some documents:

  >>> fnames = ['aaa.txt', 'bbb.csv', 'zzz.txt']
  >>> for fname in fnames:
  ...     with open(path.join(downloads, fname), 'w') as f:
  ...         pass

  >>> r = run('identify', downloads)
  >>> r.exit_code
  0
  >>> print(r.output)
  * .../downloads/aaa.txt
  * .../downloads/bbb.csv ... OK
    test.ImporterA
  * .../downloads/zzz.txt


Error conditions
----------------

Exception raised in importer code:

  >>> with open(path.join(downloads, 'error.txt'), 'w') as f:
  ...     pass
  >>> r = run('identify', downloads)
  >>> r.exit_code
  1
  >>> print(r.output)
  * .../downloads/aaa.txt
  * .../downloads/bbb.csv ... OK
    test.ImporterA
  * .../downloads/error.txt ERROR
    Exception in importer code.
    Traceback (most recent call last):
    ...
    ValueError: error.txt
  * .../downloads/zzz.txt

  >>> unlink(path.join(downloads, 'error.txt'))

Two importers matching the same document:

  >>> with open(path.join(downloads, 'error.csv'), 'w') as f:
  ...     pass
  >>> r = run('identify', downloads)
  >>> r.exit_code
  1
  >>> print(r.output)
  * .../downloads/aaa.txt
  * .../downloads/bbb.csv ... OK
    test.ImporterA
  * .../downloads/error.csv ERROR
    test.ImporterA
    test.ImporterB
    Document identified by more than one importer.
  * .../downloads/zzz.txt


Cleanup
-------

  >>> rmtree(temp)
