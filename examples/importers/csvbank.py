from os import path
from beangulp import mimetypes
from beangulp.importers import csvbase
from beangulp.testing import main


class Importer(csvbase.Importer):
    date = csvbase.Date('Posting Date', '%m/%d/%Y')  # type: ignore
    narration = csvbase.Columns('Description', 'Check or Slip #', sep='; ')
    amount = csvbase.Amount('Amount')
    balance = csvbase.Amount('Balance')

    def identify(self, filepath):
        mimetype, encoding = mimetypes.guess_type(filepath)
        if mimetype != 'text/csv':
            return False
        with open(filepath) as fd:
            head = fd.read(1024)
        return head.startswith('Details,Posting Date,"Description",'
                               'Amount,Type,Balance,Check or Slip #,')

    def filename(self, filepath):
        return 'csvbank.' + path.basename(filepath)


if __name__ == '__main__':
    main(Importer('Assets:US:CSVBank', 'USD'))
