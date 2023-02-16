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
  ...     def extract(self, filepath, existing):
  ...         name = path.basename(filepath)
  ...         raise ValueError(name)

Test harness:

  >>> importers = [
  ...     Importer('test.ImporterA', 'Assets:Tests', 'text/csv'),
  ...     ErrorImporter('test.ImporterE', 'Assets:Tests', None),
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

  >>> r = run('extract', '--help')
  >>> r.exit_code
  0
  >>> print(r.output)
  Usage: main extract [OPTIONS] [SRC]...

Test with an empty downloads directory:

  >>> r = run('extract', downloads)
  >>> r.exit_code
  0
  >>> print(r.output)

Add some documents:

  >>> fnames = ['aaa.txt', 'bbb.csv', 'zzz.txt']
  >>> for fname in fnames:
  ...     with open(path.join(downloads, fname), 'w') as f:
  ...         pass

  >>> output = path.join(temp, 'output.beancount')
  >>> r = run('extract', downloads, '-o', output)
  >>> r.exit_code
  0
  >>> print(r.output)
  * .../downloads/aaa.txt
  * .../downloads/bbb.csv ... OK
  * .../downloads/zzz.txt

Check the output file:

  >>> with open(output, 'r') as f:
  ...     extracted = f.read()
  >>> print(extracted)
  ;; -*- mode: beancount -*-
  <BLANKLINE>
  **** .../downloads/bbb.csv
  <BLANKLINE>

Disable Sections

  >>> r = run('extract', downloads, '-o', output, '-ns')
  >>> r.exit_code
  0
  >>> with open(output, 'r') as f:
  ...     extracted = f.read()
  >>> print(extracted)
  ;; -*- mode: beancount -*-

Test importer raising an error:

  >>> with open(path.join(downloads, 'error.foo'), 'w') as f:
  ...     pass

  >>> output = path.join(temp, 'output.beancount')
  >>> r = run('extract', downloads, '-o', output)
  >>> r.exit_code
  1
  >>> print(r.output)
  * .../downloads/aaa.txt
  * .../downloads/bbb.csv ... OK
  * .../downloads/error.foo ... ERROR
    Exception in importer code.
    Traceback (most recent call last):
      ...
    ValueError: error.foo
  * .../downloads/zzz.txt

Check the output file:

  >>> with open(output, 'r') as f:
  ...     extracted = f.read()
  >>> print(extracted)
  ;; -*- mode: beancount -*-
  <BLANKLINE>
  **** .../downloads/bbb.csv
  <BLANKLINE>


Cleanup
-------

  >>> rmtree(temp)
