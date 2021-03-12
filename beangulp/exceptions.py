import contextlib
import textwrap
import traceback


class Error(RuntimeError):
    def __init__(self, message, *args):
        self.message = message
        self.args = args

    def __str__(self):
        return '\n'.join((*self.args, self.message))


class ExceptionsTrap(contextlib.AbstractContextManager):
    """A contect manager to log exceptions.

    Works similarly to contextlib.suppress() but logs the exceptions
    instead than simply discarding them. This is used to shorten and
    unify exception handling in the command line wrappers. The format
    of the reporting is specific to the Beangulp command line
    interface.

    """
    def __init__(self, func):
        self.log = func
        self.errors = 0

    def __exit__(self, exctype, excinst, exctb):
        if exctype is None:
            return True
        self.errors += 1
        self.log('  ERROR', fg='red')
        if issubclass(exctype, Error):
            # Beangulp validation error.
            self.log(textwrap.indent(str(excinst), '  '))
            return True
        if issubclass(exctype, Exception):
            # Unexpected exception.
            self.log('  Exception in importer code.')
            exc = ''.join(traceback.format_exception(exctype, excinst, exctb))
            self.log(textwrap.indent(exc, '  ').rstrip())
            return True
        return False

    def __bool__(self):
        """Return True if any error occurred."""
        return self.errors != 0
