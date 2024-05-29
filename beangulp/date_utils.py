import dateutil.parser


def parse_date(string, parse_kwargs_dict=None):
    """Parse arbitrary strings to dates.

    This function is intended to support liberal inputs, so that we can use it
    in accepting user-specified dates on command-line scripts.

    Args:
      string: A string to parse.
      parse_kwargs_dict: Dict of kwargs to pass to dateutil parser.
    Returns:
      A datetime.date object.
    """
    # At the moment, rely on the most excellent dateutil.
    if parse_kwargs_dict is None:
        parse_kwargs_dict = {}
    return dateutil.parser.parse(string, **parse_kwargs_dict).date()
