"""Tokenizer for langXA source code."""

from typing import Any
from typing import Final
from typing import NamedTuple
from typing import Optional

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

    LT_NUMBER: str = "LT_NUMBER"
    LT_STRING: str = "LT_STRING"
    LT_BOOLEAN: str = "LT_BOOLEAN"
    OP_PLUS: str = "OP_PLUS"
    OP_MINUS: str = "OP_MINUS"
    OP_TIMES: str = "OP_TIMES"
    OP_DIVIDE: str = "OP_DIVIDE"
    PN_LPAREN: str = "PN_LPAREN"
    PN_RPAREN: str = "PN_RPAREN"
    PN_WHITESPACE: str = "PN_WHITESPACE"


class Token:
    """Class representing a token.

    A token or a lexical unit is the smallest individual unit in a
    program. They are the building blocks of a language.

    :param token_type: Token type.
    :param value: Value of the token, defaults to None.
    """

    def __init__(self, token_type: str, value: Optional[Any] = None) -> None:
        """Initialize Token class with no value."""
        self.token_type = token_type
        self.value = value

    def __repr__(self) -> str:
        """Return a printable representation of token instance."""
        type_ = self.token_type[3:].lower()
        _ = type_ if self.value is None else f"{type_}={self.value}"
        return f"{type(self).__name__}({_})"
