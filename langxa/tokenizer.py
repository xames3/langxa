"""Tokenizer for langXA source code."""

from __future__ import annotations

from typing import Any
from typing import Final
from typing import NamedTuple

__all__ = ["DIGITS", "Token", "TokenType"]

DIGITS: Final[str] = "0123456789"


class TokenType(NamedTuple):
    """Token type constants.

    This class provides constants which represent the types of leaf
    nodes of the parsed tree. The token types are prefixed with certain
    characters. These prefixes carry certain meaning which is explained
    below.

    KW      Keywords are the pre-defined set of words in a language that
            perform their specific function. One cannot assign a new
            value or task to them other than the pre-defined one. They
            can't be used as a variable, class, function, object or any
            other identifier. For example: if, else, for, while, True,
            False, None, break, etc.
    ID      Identifiers are the names that you can assign a value to. An
            identifier can be anything that you give to your variable,
            function, or class. Well there are certain rules that you
            have to follow while defining a valid identifier name.
            For example: charlotte = 10. Here, ``charlotte`` is a valid
            identifier.
    LT      Literals are the fixed or constant values. They can either
            be string, numbers or boolean. For example: "XAMES3" is a
            string literal, similarly 42 or 69.0 are numeric literals
            and True or False are the boolean literals.
    OP      Operators are the symbols which are used to perform various
            operations between operands. There are different types of
            operators, namely Unary, Binary and Ternary Operators.
            Unary Operators have single operand. For example: +42, -69,
            etc. Binary Operators work on two operands. For example:
            42 + 69, 13 * 14, etc and similarly Ternary Operators work
            on three operands.
    PN      Punctuators, also known as separators give a structure to
            the code. They are mostly used to define blocks in a
            program. These are basically the symbols that are used in
            programing language to organize sentence structure.
            For example: single quotes (' ') , double quote (" ") ,
            parenthesis (( )), brackets ([ ]), Braces ({ }), colon (:),
            comma (,), etc.
    """

    LT_NUMBER: str = "NUMBER"
    LT_STRING: str = "STRING"
    LT_BOOLEAN: str = "BOOLEAN"
    OP_PLUS: str = "PLUS"
    OP_MINUS: str = "MINUS"
    OP_TIMES: str = "TIMES"
    OP_DIVIDE: str = "DIVIDE"
    PN_LPAREN: str = "LPAREN"
    PN_RPAREN: str = "RPAREN"
    PN_WHITESPACE: str = "WHITESPACE"


class Token:
    """Class representing a token.

    A token or a lexical unit is the smallest individual unit in a
    program. They are the building blocks of a language.

    :param type_: Token type.
    :param value: Value of the token, defaults to None.
    """

    def __init__(self, type_: str, value: Any | None = None) -> None:
        """Initialize Token class with no value."""
        type_ = type_.lower()
        self.args = (f"{type_}={value}", type_)[value is None]

    def __repr__(self) -> str:
        """Return a printable representation of token instance."""
        return f"{type(self).__name__}({self.args})"
