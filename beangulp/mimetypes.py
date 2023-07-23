# TODO(blais): Make this only register the new types, and keep the user
# referring to the interface directly. There's no real need to 'import *' here.
# The root package would automatically register those new types.

"""The standard Python 'mimetypes' module with some custom registrations for
types commonly used for accounting. Import 'from beangulp import mimetypes'
instead of 'import mimetypes'.
"""

from mimetypes import *  # noqa: F403

# Register some MIME types used in financial downloads.
_extra_mime_types = [
    ('text/beancount', '.beancount', '.beans'), # Beancount ledgers.
    ('application/vnd.intu.qbo', '.qbo'), # Quicken files.
    ('application/x-ofx', '.qfx', '.ofx'), # Open Financial Exchange files.
]

for mime, *extensions in _extra_mime_types:
    for ext in extensions:
        add_type(mime, ext, strict=False)  # noqa: F405
