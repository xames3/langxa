"""Logging module to capture and control the langXA's output logs.

The module provides the necessary abstractions for overriding the
standard logging capabilities provided by default. This is done by
monkey patching the objects from the ``logging`` module.

This module is also responsible for rendering colors on the terminal
for foreshadowing the severity of the logging levels. Besides this, we
tend to capture all the inputs and outputs (stdin, stdout and stderr)
from the terminal.
"""

import logging
import os
import re
import sys
import types
from typing import Any
from typing import Final
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Union

from langxa.logger._handlers import RotatingFileHandler
from langxa.logger._handlers import StreamHandler

__all__ = ["ISO8601", "get_logger", "init"]

SysExcInfoType = Tuple[type, BaseException, Optional[types.TracebackType]]

ISO8601: Final[str] = "%Y-%m-%dT%H:%M:%SZ"
ANSI_ESCAPE_RE: Final[str] = r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"

ATTRS: Tuple[str, ...] = ("color", "gray", "reset")
# See https://stackoverflow.com/a/14693789/14316408 for the RegEx logic
# behind the ANSI escape sequence.
ANSI_HUES: Mapping[int, str] = {
    90: "\x1b[38;5;242m",
    60: "\x1b[38;5;128m",
    50: "\x1b[38;5;197m",
    40: "\x1b[38;5;204m",
    30: "\x1b[38;5;215m",
    20: "\x1b[38;5;41m",
    10: "\x1b[38;5;14m",
    00: "\x1b[0m",
}

# Pre-compiling regex before is always helpful than doing every single
# time at runtime.
esc = re.compile(ANSI_ESCAPE_RE)

_log = logging.getLogger("langxa.main")


def _use_color(status: bool) -> str:
    """Return log format based on the status.

    If status is True, colored log format is returned else non-colored
    format is returned.

    :param status: Boolean value to allow colored logs.
    :returns: Colored or non-colored log format based on status.
    """
    if status:
        return (
            "%(gray)s%(asctime)s %(color)s%(levelname)8s%(reset)s "
            "%(gray)s%(stack)s:%(lineno)d%(reset)s : %(message)s"
        )
    else:
        return "%(asctime)s %(levelname)8s %(stack)s:%(lineno)d : %(message)s"


class ANSIFormatter(logging.Formatter):
    """ANSI color scheme formatter.

    This class formats the ``record.pathname`` and ``record.exc_info``
    attributes to generate an uniform and clear log message. The class
    adds gray hues to the log's metadata and colorizes the log levels.

    :param fmt: Log message format, defaults to None.
    :param datefmt: Log datetime format, defaults to None.

    .. seealso::

        [1] logging.Formatter.format()
        [2] logging.Formatter.formatException()
    """

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        color: bool = False,
    ) -> None:
        """Initialize the ANSIFormatter with default formats."""
        if fmt is None:
            # NOTE: This debugging message will never be logged using
            # the existing ``get_logger()`` APIs. To see this debugging
            # message, use a root logger.
            _log.debug(
                "No active format set for logging, falling back to default "
                "format: default"
            )
            fmt = _use_color(color)
        if datefmt is None:
            datefmt = ISO8601
        self.fmt = fmt
        self.datefmt = datefmt

    @staticmethod
    def _colorize(record: logging.LogRecord) -> None:
        """Add colors to the logging levels by manipulating log records.

        This implementation works on the edge as it makes changes to the
        record object in runtime. This has a potential drawback. This
        can create memory leaks, so in order to handle this, we check
        if the logging stream is a TTY interface or not. If we are sure
        that the stream is a TTY, we modify the object. This
        implementation thus prevents the record to hold un-readable ANSI
        charcters while writing to a file.

        :param record: Instance of the logged event.
        """
        # The same could've been done using ``hasattr()`` too. This
        # ``isatty`` is a special attribute which is injected by the
        # ``langxa.logger._handlers.TTYInspector()`` class.
        if getattr(record, "isatty", False):
            setattr(record, "color", ANSI_HUES[record.levelno])
            setattr(record, "gray", ANSI_HUES[90])
            setattr(record, "reset", ANSI_HUES[00])
        else:
            for attr in ATTRS:
                setattr(record, attr, "")

    @staticmethod
    def _decolorize(record: logging.LogRecord) -> None:
        """Remove ``color`` and ``reset`` attributes from the log
        record.

        Think of this method as opposite of the ``colorize`` method.
        This method prevents the record from writing un-readable ANSI
        characters to a non-TTY interface.

        :param record: Instance of the logged event.
        """
        for attr in ATTRS:
            delattr(record, attr)

    @staticmethod
    def formatException(ei: Union[SysExcInfoType, Tuple[None, ...]]) -> str:
        r"""Format exception information as text.

        This implementation does not work directly. The standard
        ``logging.Formatter`` is required. The parent class creates an
        output string with ``\n`` which needs to be truncated and this
        method does this well.

        :param ei: Information about the captured exception.
        :return: Formatted exception string.
        """
        fnc, lineno = "<module>", 0
        cls_, msg, tbk = ei
        if tbk:
            fnc, lineno = tbk.tb_frame.f_code.co_name, tbk.tb_lineno
        fnc = "on" if fnc in ("<module>", "<lambda>") else f"in {fnc}() on"
        return f"{cls_.__name__}: {msg} line {lineno}"  # type: ignore[union-attr]

    @staticmethod
    def _stack(path: str, fnc: str) -> str:
        """Format path as stack.

        :param path: Pathname of the module which is logging the event.
        :param fnc: Callable instance which is logging the event.
        :returns: Springboot style formatted path, well kinda...

        .. note::

            If called from a module, the base path of the module would
            be used else "shell" would be returned for the interpreter
            (stdin) based inputs.

        """
        if path == "<stdin>":
            return "shell"
        if os.name == "nt":
            path = os.path.splitdrive(path)[1]
        # NOTE: This presumes we work through a virtual environment.
        # This is a safe assumption as we peruse through the site-
        # packages. In case this is not running via the virtual env, we
        # might get a different result.
        abspath = "site-packages" if "site-packages" in path else os.getcwd()
        path = path.split(abspath)[-1].replace(os.path.sep, ".")[
            path[0] != ":" : -3
        ]
        if fnc not in ("<module>", "<lambda>"):
            path += f".{fnc}"
        return path

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text.

        If any exception is captured then it is formatted using the
        ``ANSIFormatter.formatException()`` and replaced with the
        original message.

        :param record: Instance of the logged event.
        :returns: Captured and formatted output log strings.
        """
        # Update the pathname and the invoking function name using the
        # stack. This stack will be set as a record attribute which will
        # allow us to use the %(stack)s placeholder in the log format.
        setattr(record, "stack", self._stack(record.pathname, record.funcName))
        if record.exc_info:
            record.msg = self.formatException(record.exc_info)
            record.exc_info = record.exc_text = None
        self._colorize(record)
        msg = logging.Formatter(self.fmt, self.datefmt).format(record)
        # Escape the ANSI sequence here as this will render the colors
        # on the TTY but won't add them to the non-TTY interfaces, for
        # example, log file.
        record.msg = esc.sub("", str(record.msg))
        self._decolorize(record)
        return msg


def get_logger(module: str) -> logging.Logger:
    """Return logger instance.

    This function is supposed to be used by the modules for logging.
    This logger is a child logger which reports logs back to the parent
    logger defined by the ``langxa.logger._main.init()``.

    :param module: Module to be logged.
    :return: Logger instance.
    """
    return logging.getLogger("langxa.main").getChild(module)


def init(**kwargs: Any) -> logging.Logger:
    """Initialize an application level logger.

    This function initializes an application level logger with default
    configurations for the logging system. It accepts a lot of different
    keyword arguments for customization.

    If handlers are provided as part of input, this function overrides
    the default behavior (logging to file and streaming colored outputs)
    in favour of the provided handler. It is a convenience function
    intended for use by simple applications to do one-shot
    configuration.

    The default behavior is to create ``StreamHandler`` and a
    ``RotatingFileHandler`` which writes to sys.stderr and an output
    log file respectively.

    A number of optional keyword arguments may be specified, which can
    alter the default behavior.

    filename    Specifies that ``RotatingFileHandler`` should be
                created with the provided filename and output should
                be logged to a file.
    filemode    Specifies the mode to open the file, if filename is
                specified (if filemode is unspecified, it defaults to
                ``a``).
    format      Use the specified format string for the handler.
    datefmt     Use the specified date/time format.
    level       Set the root logger level to the specified level.
    handlers    If specified, this should be an iterable of already
                created handlers, which will be added to the root
                handler.
    encoding    If specified together with a filename, this encoding
                is passed to the created ``RotatingFileHandler``,
                causing it to be used when the file is opened.
    max_bytes   If specified together with a filename, this saves the
                output log files in chunks of provided bytes.
    color       Boolean option to whether display colored log outputs on
                the terminal or not.

    :returns: Logger instance.

    .. seealso::

        [1] logging.basicConfig()
        [2] langxa.logger._handlers.RotatingFileHandler()
        [3] langxa.logger._handlers.StreamHandler()
    """
    name = kwargs.get("name", "langxa.main")
    logger = logging.getLogger(name)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    if not logger.handlers:
        level = kwargs.get("level", logging.INFO)
        logger.setLevel(level)
        fmt = kwargs.get("format")
        datefmt = kwargs.get("datefmt")
        color = kwargs.get("color", True)
        formatter = ANSIFormatter(fmt, datefmt, color)
        handlers = kwargs.get("handlers")
        _msg = ""
        if handlers is None:
            handlers = []
            stream = kwargs.get("stream", sys.stderr)
            handlers.append(StreamHandler(stream, formatter, level))
            filename = kwargs.get("filename")
            filemode = kwargs.get("filemode", "a")
            max_bytes = kwargs.get("max_bytes", 10000000)
            encoding = kwargs.get("encoding")
            _msg = " with StreamHandler (default)"
            if filename:
                rotator = RotatingFileHandler
                sys.stdout = sys.stderr = sys.stdin = rotator(  # type: ignore
                    filename, filemode, max_bytes, encoding
                )
                _msg += " and RotatingFileHandler (for output logging)"
        for handler in handlers:
            handler.add_handler(logger)  # type: ignore
        capture_warnings = kwargs.get("capture_warnings", True)
        logging.captureWarnings(capture_warnings)
        # FIXME: In case you are wondering why some of the logs are not
        # being logged, it is primarily because of how the python's
        # root logger works. If any log messages are created beyond this
        # point, they'll be logged as the handlers have being
        # configured. In case you want to have previous logs, use root
        # logger instead.
        _log.debug("Initializing an application level logger" + _msg)
    return logger
