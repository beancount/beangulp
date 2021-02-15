# Beangulp Example

This directory contains an example for how to organize yourself and your files
to automate your Beancount ledger update. See
http://furius.ca/beancount/doc/beangulp for a fuller documentation and
discussion of these files.

There are five directories demonstrated here:

* `ledger`: This is a directory, typically a repository under source control,
  containing your Beancount ledger file(s) (e.g., `ledger.beancount`) and import
  configuration ('ledger.import'), which is a Python file.

* `documents`: This is directory which contains your past imported files.
  Beangulps' filing command is able to automatically date and rename the files
  there after you've finished updating your Beancount ledger.

* `importers`: This is directory, typically a repository under source control,
  which contains your custom importers implementations. Note that in the most
  general case this does not include examples of your downloaded files nor any
  personal account-specific information (e.g. account ids), because you may want
  to share your importers with others.

* `importers_tests`: This directory complements `importers` and provides
  examples of real downloaded files from your institutions, which will serve as
  regression tests. Next to each downloaded file is a `*.beancount` golden file
  with the correct contents extracted by the importer. Those should be generated
  by the "generate" command from the importer and eyeballed for correctness.
  Running the "test" after a change of your importer code will cross-check the
  importer's updated output with the existing golden files. This is a really
  fast way to add some testing and regression detection around your custom
  importer codes.

* `Downloads`: This is the location where your browser might store the files you
  fetch from your bank(s).


Note that you could further simplify and merge some of these together for your
convenience. This example shows that in the most general case you could store
all of these things separately. In fact, the first four directories could all be
stored to a single repository, if you want to keep really simple.
