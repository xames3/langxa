"""langXA error module.

This module hosts all the errors raised by langXA and its derivatives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langxa.lexer import Position

__all__ = ["Error", "InvalidCharacterError", "langXABaseError"]


class langXABaseError(Exception):
    """Base class for all errors raised by langXA.

    This exception class is meant for subclassing exceptions which are
    required for langXA's internals.

    :param description: Custom or runtime description of the error.
    :var _description: Default or generic description of the error.

    .. warning::

        This class should be extended only if there are special errors
        or exceptions that needs to be handled by the langXA's code
        environment.
    """

    _description: str

    def __init__(self, description: str | None = None) -> None:
        """Initialize exception with error description."""
        if description:
            self._description = description
        super().__init__(self._description)


class langXACodeError(langXABaseError):
    """Error to be raised when there is an exception while running the
    langXA code.

    :param start: Starting position of the error.
    :param end: Ending position of the error.
    :param description: Custom or runtime description of the error,
        defaults to None.
    :var _offset: Number of characters to match the interpreter prefix.
    :var _description: Default or generic description of the error.
    """

    _offset: int
    _description: str

    def __init__(
        self,
        start: Position,
        end: Position,
        description: str | None = None,
    ) -> None:
        """Initialize langXACodeError with error positions and a
        description.
        """
        self.start = start
        self.end = end
        super().__init__(description)

    @property
    def message(self) -> str:
        """Output message to display when an error occurs."""
        return (
            f"File {self.start.filename!r} at line {self.start.ln + 1}, "
            f"col {self.start.idx + 1}\n... [{'x' * (self._offset)}]: "
            f"{type(self).__name__}: {self._description}"
        )


Error = langXACodeError


class InvalidCharacterError(Error):
    """Error to be raised when the interpreter comes across an
    unexpected or invalid character while tokenizing.
    """
