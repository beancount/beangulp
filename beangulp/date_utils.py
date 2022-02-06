import datetime
import dateutil.parser


def parse_date(string: str) -> datetime.date:
    """Parse any date format into a date string."""
    return dateutil.parser.parse(string).date()
