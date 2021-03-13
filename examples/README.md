# Beangulp Example

This directory contains an example for how to organize yourself and your files
to automate your Beancount ledger update. See
http://furius.ca/beancount/doc/beangulp for a fuller documentation and
discussion of these files.

## Example Files Organization - Sophisticated

There are five directories demonstrated here:

* `ledger`: This is a directory, typically a repository under source control,
  containing your Beancount ledger files.

* `documents`: This is a directory containing your past imported files.
  Beangulps' filing command is able to automatically date and rename the files
  there after you've finished updating your Beancount ledger.

* `importers`: This is a directory, typically a repository under source control,
  containing your custom importers implementations. Note that in the most
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


## Example Files Organization - Simpler

Note that you could further simplify and merge some of these together for your
convenience. The example above shows that in the most general case you could
store all of these things separately. In fact, the first four directories could
all be stored to a single repository, if you wanted to keep things really
simple. We recommend you start that way, especially if all the information is
overwhelming.

Here's an example for how you could start with all your files in one directory:

    ledger/
    ├── import.py
    ├── ledger.beancount
    ├── importers
    │   ├── acme
    │   │   ├── acmebank1.pdf
    │   │   ├── acmebank1.pdf.beancount
    │   │   └── acme.py
    │   └── utrade
    │       ├── UTrade20140713.csv
    │       ├── UTrade20140713.csv.beancount
    │       ├── UTrade20150225.csv
    │       ├── UTrade20150225.csv.beancount
    │       ├── UTrade20150720.csv
    │       ├── UTrade20150720.csv.beancount
    │       └── utrade.py
    └── documents
        ├── Assets
        │   └── US
        │       ├── AcmeBank
        │       └── UTrade
        │           └── ...
        ├── Expenses
        ├── Income
        └── Liabilities
            └── US
                └── CreditCard
                    └── ...
