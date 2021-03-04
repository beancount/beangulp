import os
import unittest
import click.testing

from beancount.utils import test_utils
from beangulp import Ingest
from beangulp import importer
from beangulp import cache


class _TestFileImporter(importer.ImporterProtocol):

    def __init__(self, name, account, mimetype):
        self._name = name
        self.account = account
        self.mimetype = mimetype

    def name(self):
        return self._name

    def identify(self, file):
        mimetype = file.convert(cache.mimetype)
        if mimetype == self.mimetype:
            return True
        return False

    def file_account(self, _):
        return self.account


class TestScriptsBase(test_utils.TestTempdirMixin, unittest.TestCase):

    def ingest(self, *args):
        runner = click.testing.CliRunner()
        result = runner.invoke(self.main, args)
        return result

    def setUp(self):
        super().setUp()

        files = [
            'Downloads/ofxdownload.ofx',
            'Downloads/Subdir/bank.csv',
            'Downloads/Subdir/readme.txt',
        ]
        for filename in files:
            absname = os.path.join(self.tempdir, filename)
            os.makedirs(os.path.dirname(absname), exist_ok=True)
            with open(absname, 'w') as file:
                pass

        importers = [
            _TestFileImporter('ofxbank.Importer', 'Assets:Checking', 'application/x-ofx'),
            _TestFileImporter('csvbank.Importer', 'Liabilities:CreditCard', 'text/csv'),
        ]
        self.main = Ingest(importers).main
