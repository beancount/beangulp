Setup
-----

  >>> from datetime import date
  >>> from os import mkdir, path, rename, unlink
  >>> from shutil import rmtree
  >>> from tempfile import mkdtemp
  >>> from beangulp.tests.utils import Importer
  >>> import click.testing

Import the module under test:

  >>> import beangulp.testing

Test harness:

  >>> importer = Importer('test.Importer', 'Assets:Tests', 'text/csv')
  >>> runner = click.testing.CliRunner()
  >>> def run(*args):
  ...     func = beangulp.testing.wrap(importer)
  ...     return runner.invoke(func, args, catch_exceptions=False)


Tests
-----

Check the basics:

  >>> r = run()
  >>> r.exit_code
  0
  >>> print(r.output)
  Usage: main [OPTIONS] COMMAND [ARGS]...

  >>> r = run('test', '--help')
  >>> r.exit_code
  0
  >>> print(r.output)
  Usage: main test [OPTIONS] [DOCUMENTS]...

  >>> r = run('test')
  >>> r.exit_code
  0
  >>> print(r.output)
  <BLANKLINE>

Create a documents directory:

  >>> temp = mkdtemp()
  >>> documents = path.join(temp, 'documents')
  >>> mkdir(documents)

Poulate it with a file that should be ignored:

  >>> with open(path.join(documents, 'test.txt'), 'w') as f:
  ...     pass

The test harness should report this file as ignored and report success:

  >>> r = run('test', documents)
  >>> r.exit_code
  0
  >>> print(r.output)
  * .../documents/test.txt  IGNORED

and no expected output file should be generated for it:

  >>> r = run('generate', documents)
  >>> r.exit_code
  0
  >>> print(r.output)
  * .../documents/test.txt  IGNORED

  >>> unlink(path.join(documents, 'test.txt'))

Try the same with a file that should be recognized by the importer.
When there is no epxected output file the test harness should report a
test error:

  >>> with open(path.join(documents, 'test.csv'), 'w') as f:
  ...     pass
  >>> r = run('test', documents)
  >>> r.exit_code
  1
  >>> print(r.output)
  * .../documents/test.csv  ERROR
  ExpectedOutputFileNotFound

Generate the expected output file:

  >>> r = run('generate', documents)
  >>> r.exit_code
  0
  >>> print(r.output)
  * .../documents/test.csv  OK

Now the test should succeed:

  >>> r = run('test', documents)
  >>> r.exit_code
  0
  >>> print(r.output)
  * .../documents/test.csv  PASSED

Overwriting the expected output file is an error:

  >>> r = run('generate', documents)
  >>> r.exit_code
  1
  >>> print(r.output)
  * .../documents/test.csv  ERROR
  FileExistsError: .../test.csv.beancount

unless the --force options is specified:

  >>> r = run('generate', documents, '--force')
  >>> r.exit_code
  0
  >>> print(r.output)
  * .../documents/test.csv  OK

Put back a file that should be ignored and verify that it is:

  >>> with open(path.join(documents, 'test.txt'), 'w') as f:
  ...     pass
  >>> r = run('test', documents)
  >>> r.exit_code
  0
  >>> print(r.output)
  * .../documents/test.csv  PASSED
  * .../documents/test.txt  IGNORED

  >>> unlink(path.join(documents, 'test.txt'))

Altering the expected output file should result in a test error:

  >>> filename = path.join(documents, 'test.csv.beancount')
  >>> with open(filename, 'a') as f:
  ...     f.write('FAIL')
  4
  >>> r = run('test', documents)
  >>> r.exit_code
  1
  >>> print(r.output)
  * .../documents/test.csv  ERROR
  --- imported.beancount
  +++ expected.beancount
  @@ -1,4 +1,3 @@
   ;; Account: Assets:Tests
   ;; Date: 1970-01-01
   ;; Name:
  -FAIL

When the importer does not positively identify a document that should,
a test error is reported:

  >>> rename(path.join(documents, 'test.csv'), path.join(documents, 'test.foo'))
  >>> rename(path.join(documents, 'test.csv.beancount'), path.join(documents, 'test.foo.beancount'))
  >>> r = run('test', documents)
  >>> r.exit_code
  1
  >>> print(r.output)
  * .../documents/test.foo  ERROR
  DocumentNotIdentified


Cleanup
-------

  >>> rmtree(temp)
