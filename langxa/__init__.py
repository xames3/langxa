"""langXA: A dummy programming language written in Python.

The whole inspiration of writing this language comes from an internal
office joke and another toy language, ``Bhailang.JS``. Although this
is an internal pet project, its worth investing some time in learning
new things like building a programming language using the constructs of
another language.

The language is certainly not intended to use for any production related
workload since it wouldn't be ready for it also the use cases would be
heavily limited, it is worth checking out for the fun sake.
"""

from langxa.errors import Error
from langxa.errors import InvalidCharacterError
from langxa.errors import langXABaseError
from langxa.interpreter import Interpreter
from langxa.lexer import Lexer
from langxa.lexer import Position
from langxa.logger import ANSIFormatter
from langxa.logger import FileHandler
from langxa.logger import Handler
from langxa.logger import RotatingFileHandler
from langxa.logger import StreamHandler
from langxa.logger import TTYInspector
from langxa.logger import customize_logger
from langxa.logger import get_logger
from langxa.logger import init
from langxa.tokenizer import DIGITS
from langxa.tokenizer import Token
from langxa.tokenizer import TokenType

__all__ = [
    "Error",
    "InvalidCharacterError",
    "langXABaseError",
    "Interpreter",
    "Lexer",
    "Position",
    "ANSIFormatter",
    "FileHandler",
    "Handler",
    "RotatingFileHandler",
    "StreamHandler",
    "TTYInspector",
    "customize_logger",
    "get_logger",
    "init",
    "DIGITS",
    "Token",
    "TokenType",
]
