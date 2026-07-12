class DataFrameEmptyError(Exception):
    """Raised when a specified DataFrame is empty."""


class ColumnNotFoundError(Exception):
    """Raised when a required column is missing."""


class GameIDsBySourceEmptyError(Exception):
    """Raised when there are no game IDs for the source."""


class NoSuffixesError(Exception):
    """Raised when no suffixes are specified for the source name."""
