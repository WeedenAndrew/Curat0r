"""Domain exceptions. Nothing here knows what HTTP is."""

from __future__ import annotations


class Curat0rError(Exception):
    """Base for every expected domain failure."""


class UnknownSource(Curat0rError):
    """The URL does not match any registered source."""


class IngestNotPermitted(Curat0rError):
    """This source may not be fetched automatically.

    Carries the sanctioned alternative so the caller can tell the user what to
    do instead of merely refusing.
    """

    def __init__(self, source: str, method: str, guidance: str) -> None:
        super().__init__(f"{source} cannot be auto-fetched: {guidance}")
        self.source = source
        self.method = method
        self.guidance = guidance


class CorpusConflict(Curat0rError):
    """An ingested block would overwrite something the user edited."""
