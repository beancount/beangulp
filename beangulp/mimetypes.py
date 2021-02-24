from mimetypes import *

# Register some MIME types used in financial downloads.
_extra_mime_types = [
    ('application/vnd.intu.qbo', '.qbo'), # Quicken files.
    ('application/x-ofx', '.qfx', '.ofx'), # Open Financial Exchange files.
]

for mime, *extensions in _extra_mime_types:
    for ext in extensions:
        add_type(mime, ext, strict=False)
