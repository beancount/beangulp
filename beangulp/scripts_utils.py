__copyright__ = "Copyright (C) 2016,2018  Martin Blais"
__license__ = "GNU GPLv2"

from beangulp import Ingest

def ingest(importers, hooks=None):
    # This function is provided for backward compatibility with the
    # ``beancount.ingest`` framework. It will be removed eventually.
    main = Ingest(importers, hooks)
    main()
