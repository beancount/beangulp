"""Example importer for PDF statements from ACME Bank.

This importer identifies the file from its contents and only supports
filing, it cannot extract any transactions from the PDF conversion to
text.  This is common, and I figured I'd provide an example for how
this works.

"""
__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import re
import subprocess

from dateutil.parser import parse as parse_datetime

import beangulp
from beangulp import mimetypes
from beangulp.cache import cache
from beangulp.testing import main


@cache
def pdf_to_text(filename):
    """Convert a PDF document to a text equivalent."""
    r = subprocess.run(['pdftotext', filename, '-'],
                       stdout=subprocess.PIPE, check=True)
    return r.stdout.decode()


class Importer(beangulp.Importer):
    """An importer for ACME Bank PDF statements."""

    def __init__(self, account_filing):
        self.account_filing = account_filing

    def identify(self, filepath):
        mimetype, encoding = mimetypes.guess_type(filepath)
        if mimetype != 'application/pdf':
            return False

        # Look for some words in the PDF file to figure out if it's a statement
        # from ACME. The filename they provide (Statement.pdf) isn't useful.
        text = pdf_to_text(filepath)
        if text:
            return re.match('ACME Bank', text) is not None

    def filename(self, filepath):
        # Normalize the name to something meaningful.
        return 'acmebank.pdf'

    def account(self, filepath):
        return self.account_filing

    def date(self, filepath):
        # Get the actual statement's date from the contents of the file.
        text = pdf_to_text(filepath)
        match = re.search('Date: ([^\n]*)', text)
        if match:
            return parse_datetime(match.group(1)).date()


if __name__ == '__main__':
    importer = Importer("Assets:US:ACMEBank")
    main(importer)
