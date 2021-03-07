import os
import re
import stat
import unittest
import click.testing

from beancount.utils import test_utils
from beangulp import Ingest
from beangulp import importer
from beangulp import cache


class _TestFileImporter(importer.ImporterProtocol):

    def __init__(self, name, account, regexp_mime, regexp_contents):
        self._name = name
        self.account = account
        self.regexp_mime = regexp_mime
        self.regexp_contents = regexp_contents

    def name(self):
        return self._name

    def identify(self, file):
        mimetype = file.convert(cache.mimetype)
        if re.match(self.regexp_mime, mimetype):
            return True
        if re.search(self.regexp_contents, file.contents()):
            return True
        return False

    def file_account(self, _):
        return self.account

CSV_FILE = """\
DATE,TRANSACTION ID,DESCRIPTION,QUANTITY,SYMBOL,PRICE,COMMISSION,AMOUNT,NET CASH BALANCE,REG FEE,SHORT-TERM RDM FEE,FUND REDEMPTION FEE, DEFERRED SALES CHARGE
07/02/2013,10223506553,ORDINARY DIVIDEND (HDV),,HDV,,,31.04,31.04,,,,
07/02/2013,10224851005,MONEY MARKET PURCHASE,,,,,-31.04,0.00,,,,
07/02/2013,10224851017,MONEY MARKET PURCHASE (MMDA10),31.04,MMDA10,,,0.00,0.00,,,,
09/30/2013,10561187188,ORDINARY DIVIDEND (HDV),,HDV,,,31.19,31.19,,,,
09/30/2013,10563719172,MONEY MARKET PURCHASE,,,,,-31.19,0.00,,,,
09/30/2013,10563719198,MONEY MARKET PURCHASE (MMDA10),31.19,MMDA10,,,0.00,0.00,,,,
***END OF FILE***
"""

class TestScriptsBase(test_utils.TestTempdirMixin, unittest.TestCase):

    def ingest(self, *args):
        runner = click.testing.CliRunner()
        result = runner.invoke(self.main, args)
        return result

    # Example input files.
    FILES = {
        'Downloads/ofxdownload.ofx': "OFXHEADER:100",
        'Downloads/Subdir/bank.csv': CSV_FILE,
        'Downloads/Subdir/readme.txt': "sheeMeb0",
    }

    def setUp(self):
        super().setUp()

        for filename, contents in self.FILES.items():
            absname = os.path.join(self.tempdir, filename)
            os.makedirs(os.path.dirname(absname), exist_ok=True)
            with open(absname, 'w') as file:
                file.write(contents)
            if filename.endswith('.py') or filename.endswith('.sh'):
                os.chmod(absname, stat.S_IRUSR|stat.S_IXUSR)

        importers = [
            _TestFileImporter(
                'mybank-checking-ofx', 'Assets:Checking',
                'application/x-ofx', '<FID>3011'),
            _TestFileImporter(
                'mybank-credit-csv', 'Liabilities:CreditCard',
                'text/csv', '.*DATE,TRANSACTION ID,DESCRIPTION,QUANTITY,SYMBOL'),
        ]
        self.main = Ingest(importers).main
