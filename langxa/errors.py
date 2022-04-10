"""langXA error module.

This module hosts all the errors raised by langXA and its derivatives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Optional

if TYPE_CHECKING:
    from langxa.lexer import Position


class langXABaseError(Exception):
    """Base class for all errors raised by langXA.

    This exception class is meant for subclassing exceptions which are
    required for langXA's internals.

    .. warning::

        This class should be extended only if there are special errors
        or exceptions that needs to be handled by the langXA's code
        environment.
    """

    _description: str

    def __init__(self, description: Optional[str] = None) -> None:
        """Initialize exception with error description."""
        if description:
            self._description = description
        super().__init__(self._description)


class langXACodeError(langXABaseError):
    """Error to be raised when there is an exception while running the
    langXA code.
    """

    _offset: int
    _description: str

    def __init__(
        self,
        err_start: Position,
        err_end: Position,
        description: Optional[str] = None,
    ) -> None:
        """Initialize langXACodeError with error positions and a
        description.
        """
        self.err_start = err_start
        self.err_end = err_end
        self.error = type(self).__name__
        super().__init__(description)

    @property
    def message(self) -> str:
        """Output message to display when an error occurs."""
        return (
            f"File {self.err_start.filename!r}, line {self.err_start.ln + 1}, "
            f"col {self.err_start.idx + 1}\n... [{'x' * (self._offset)}]: "
            f"{self.error}: {self._description}"
        )


Error = langXACodeError


class InvalidCharacterError(Error):
    """Error to be raised when the interpreter comes across an
    unexpected or invalid character while tokenizing.
    """
