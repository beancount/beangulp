from datetime import date
from beangulp import importer
from beangulp import mimetypes


class Importer(importer.ImporterProtocol):
    def __init__(self, name, account, mimetype):
        self._name = name
        self._account = account
        self._mimetype = mimetype

    def name(self):
        return self._name

    def identify(self, file):
        mimetype, encoding = mimetypes.guess_type(file.name, False)
        return mimetype == self._mimetype

    def file_date(self, file):
        return date(1970, 1, 1)

    def file_account(self, file):
        return self._account

    def file_name(self, file):
        return None

    def extract(self, file, existing_entries=None):
        return []
