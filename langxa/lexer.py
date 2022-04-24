"""langXA's lexical analyzer.

This module performs lexical analysis. In the beginning, scanning and
lexical analysis were two different steps but due to the increased speed
of processors, they now refer to one and the same process and are used
interchangeably.

Scanning means to pass over or scan a string character by character
whereas Lexical Analysis is the process whereby the scanned characters
are turned into something called as ``Lexemes``. Lexeme is a recognised
piece of string. For example: "XAMES3 is a god", if we have a string
like this we might build a parser that outputs the following lexemes:

    lexeme 1: XAMES3
    lexeme 2: is
    lexeme 3: a
    lexeme 4: god

Now lets take a code sample, "yo_mama = 42 + 69". For this code sample,
the parser would output following lexemes:

    lexeme 1: yo_mama
    lexeme 2: =
    lexeme 3: 42
    lexeme 4: +
    lexeme 5: 42

This module provides these abstractions that can seperate those pieces.

.. seealso::

    [1] See this Medium post `here <https://rb.gy/gofmgt>`_ to build a
    lexer in Python. The blog post doesn't do actually helps building a
    lexer, but does a good job explaining it.
"""

from __future__ import annotations

from langxa.errors import Error
from langxa.errors import InvalidCharacterError
from langxa.tokenizer import DIGITS
from langxa.tokenizer import Token
from langxa.tokenizer import TokenType

__all__ = ["Lexer", "Position"]

tt = TokenType()


class Position:
    """Keep track of the lexer.

    This class keeps a check on the position of the currently tokenized
    character by the lexer. It tracks its line and column number along
    with its index with respect to the column. This helps in locating
    the origin or the source of syntactic errors.

    .. seealso::

        [1] Checkout the implementation of :py:class:`Lexer() <Lexer()>`
        for the usage of this class.
    """

    def __init__(
        self, idx: int, ln: int, col: int, filename: str, input_: str
    ) -> None:
        """Initialize Position for the lexer."""
        self.idx = idx
        self.ln = ln
        self.col = col
        self.filename = filename
        self.input = input_

    def _next(self, character: str | None) -> Position:
        """Move on to the next index and update line and column number,
        if necessary.

        :returns: Updated position for the lexer.
        """
        self.idx += 1
        self.col += 1
        if character == "\n":
            # Jump on to the next line and reset the column number to 0.
            # This allows us to start fresh on the new line.
            self.ln += 1
            self.col = 0
        return self

    def copy(self) -> Position:
        """Create copy of positions to keep track of the errors."""
        return Position(self.idx, self.ln, self.col, self.filename, self.input)


class Lexer:
    """Class to create lexemes.

    This class performs the lexical analysis on the input provided
    captured from the interpreter. It tokenizes (breaks or splits) the
    input command into something called as Lexemes. These lexemes are
    the tokens (unit) of the program. Each token has two parts - type
    of the token and its optional value.

    Every input is tokenized line by line and is temporarily stored in
    a list which is returned when no character is found.
    """

    character: str | None = None

    def __init__(self, filename: str, input_: str) -> None:
        """Initialize Lexer with input from the interpreter."""
        self.filename = filename
        self.input = input_
        # NOTE: The length of the input text is required to grab the
        # current character while parsing. Although this check happens
        # every single time when we increment the index position of
        # our current character, we don't need to calculate the length
        # every single time we move forward as the length of the input
        # text will always remain same for the instance' lifetime.
        self.len = len(input_)
        # The ``self.pos`` purposely starts off with -1 value. Since the
        # ``self._next()`` is called immediately after its assignment,
        # it will start the parsing process from 0 a.k.a the start of
        # the input text from first line and first column.
        self.pos = Position(-1, 0, 1, filename, input_)
        self._next()

    def _next(self) -> None:
        """Move on to the next character in the input sequence."""
        self.pos._next(self.character)
        _ = self.pos.idx
        # We keep progressing through the input text and when we reach
        # at the end of the text, we mark ``self.character`` to None.
        # When the ``self.character`` is None, it means that we have
        # reached at the end of the input command and we can't parse it
        # beyond this point. This is perhaps an indicator for the fact
        # that we should probably stop tokenizing.
        self.character = self.input[_] if _ < self.len else None

    def _number(self) -> Token:
        """Return number token, either int or float from input text.

        This method detects if a character is a digit (0-9) or not and
        if it is detected, returns the number token (int or float).
        Since the number can be more than one character, we need to
        define this method for explicitly checking it's validity.

        :returns: Number token either int or float depending upon the
            type of number.
        """
        tmp, decimal = "", 0
        while self.character and self.character in (DIGITS + ".eE"):
            if self.character == ".":
                # If we already have one decimal (dot) in the tmp string
                # we won't be adding another one, as it makes no sense,
                # break out instead.
                if decimal == 1:
                    break
                decimal += 1
                tmp += "."
            else:
                tmp += self.character
            self._next()
        try:
            return Token(tt.LT_NUMBER, int(tmp))
        except ValueError:
            return Token(tt.LT_NUMBER, float(tmp))

    def tokenize(self) -> tuple[list[Token], Error | None]:
        """Identify and add tokens from the input sequence.

        This method defines "rules" and checks the type of the character
        and returns the associated token with it. If an unknown
        character is detected, it returns an error.

        These said "rules" are nothing but token or character comparison
        with the pre-defined values. If the character matches with the
        value, it is added to the token list and returned back.

        :returns: List of detected tokens and error, if any.
        """
        tokens: list[Token] = []
        while self.character:
            if self.character in DIGITS:
                tokens.append(self._number())
            elif self.character in " \t\f":
                self._next()
            elif self.character == "+":
                tokens.append(Token(tt.OP_PLUS))
                self._next()
            elif self.character == "-":
                tokens.append(Token(tt.OP_MINUS))
                self._next()
            elif self.character == "*":
                tokens.append(Token(tt.OP_TIMES))
                self._next()
            elif self.character == "/":
                tokens.append(Token(tt.OP_DIVIDE))
                self._next()
            elif self.character == "(":
                tokens.append(Token(tt.PN_LPAREN))
                self._next()
            elif self.character == ")":
                tokens.append(Token(tt.PN_RPAREN))
                self._next()
            else:
                # NOTE: We save the position from the point where the
                # error actually began. This is needed for displaying
                # this information back to the interpreter.
                start = self.pos.copy()
                # We need to save the invalid or untokenizable character
                # so that we can raise it as an error.
                description = f"Couldn't tokenize {self.character!r}"
                self._next()
                return [], InvalidCharacterError(start, self.pos, description)
        return tokens, None
