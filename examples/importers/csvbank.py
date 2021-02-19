from beangulp.importers import csv
from beangulp.testing import main


class Importer(csv.Importer):
    def __init__(self, account):
        super().__init__(
            {csv.Col.DATE: 'Posting Date',
             csv.Col.NARRATION1: 'Description',
             csv.Col.NARRATION2: 'Check or Slip #',
             csv.Col.AMOUNT: 'Amount',
             csv.Col.BALANCE: 'Balance',
             csv.Col.DRCR: 'Details'},
            account,
            'USD',
            ('Details,Posting Date,"Description",Amount,''Type,Balance,Check or Slip #,'),
            institution='csvbank')


if __name__ == '__main__':
    main(Importer('Assets:US:CSVBank'))
