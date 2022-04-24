"""Logging module to capture and control langXA's logs.

The module provides the necessary abstractions for overriding the
standard logging capabilities provided by default. This is done by
monkey-patching objects from the logging module.

This module is also responsible for rendering colors on the terminal
for foreshadowing the severity of the logging levels. Besides this, it
captures all the inputs and outputs (stdin, stdout and stderr) from the
terminal.

Additionally, the module provides a couple of handlers which basically
extend the normal usage of the this module.

The file handler implemented below allows us to write the stdin, stdout
and stderr (basically anything that can be printed out) to an output
file.
"""

from __future__ import annotations

import argparse
import fnmatch
import logging
import os
import re
import sys
import types
from functools import cached_property
from typing import IO
from typing import Any
from typing import Final
from typing import Mapping
from typing import Sequence

__all__ = [
    "ANSIFormatter",
    "FileHandler",
    "Handler",
    "RotatingFileHandler",
    "StreamHandler",
    "TTYInspector",
    "customize_logger",
    "get_logger",
    "init",
]

LOGGER_LEVEL: str | None = os.getenv("LANGXA_LOGGING_LEVEL")
SKIP_LOGGING: str | None = os.getenv("LANGXA_SKIP_LOGGING")

ANSI_ESCAPE_RE: Final[str] = r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
LOGGER_NAME: Final[str] = "langxa.main"
ISO8601: Final[str] = "%Y-%m-%dT%H:%M:%SZ"

LOGS_DIR: str = os.path.join(os.path.expanduser("~"), ".langxa")
LOG_FILE: str = os.path.join(LOGS_DIR, "history.log")

ANSI_ATTRS: Sequence[str] = ("color", "gray", "reset")
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
VERBOSITY_LEVELS: Mapping[int, int] = {0: 30, 1: 20, 2: 10}
LOGGING_LEVELS: Mapping[str, int] = {
    "TRACE": 60,
    "FATAL": 50,
    "CRITICAL": 50,
    "ERROR": 40,
    "WARN": 30,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 00,
}

esc = re.compile(ANSI_ESCAPE_RE)


def _setup_logs(override: bool | str, path: str) -> str | None:
    """Setup a log directory and log I/O from the stdin/out to the file.

    The I/O logs are stored in the ``$HOME/.langxa`` directory for
    redundancies and maintaining history*. In case the directory is
    deleted or doesn't exist, this function will create it.

    Although if this behavior is not wanted, you can skip logging
    entirely by setting the environment variable "LANGXA_SKIP_LOGGING"
    to ``TRUE``.

    :param override: Set "LANGXA_SKIP_LOGGING" to True to override
        logging.
    :returns: Path of the log file if "LANGXA_SKIP_LOGGING" is not set
        else None.
    """
    if override or override == "TRUE":  # Input can be a boolean too
        return None
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _skip_output_log(choice: bool) -> bool:
    """Return whether to output logs to a file.

    If the choice is set at an environment variable level by exporting
    the value of "LANGXA_SKIP_LOGGING" to ``TRUE``, it will override the
    passed argument. If nothing is set, it will continue to log output
    to the file.

    :param choice: Boolean flag from the passed argument.
    :returns: Status whether to log file or not.
    """
    # This ensures that only ``TRUE`` is considered as a valid choice
    # here. This is required, else any valid string would be considered
    # as True and loop might accidentally execute.
    if (SKIP_LOGGING and SKIP_LOGGING == "TRUE") or choice:
        return True
    return False


def _select_log_level(level: int | str) -> int:
    """Select which logging level to use.

    If the logging level is set at an environment variable level by
    exporting the value of "LANGXA_LOGGING_LEVEL" to a valid log level,
    it will override the verbosity counter. If nothing is set, it will
    use the value of verbosity for logging. Higher the counter, lower
    the logging level.

    :param level: Verbosity counter value or the implicit logging level.
    :returns: Logging level.

    .. seealso::

        [1] Consider checking out the implementation of
        :py:func:`main() <langxa.__main__.main()>` function to fully
        understand the usage the ``level`` argument.
    """
    if LOGGER_LEVEL:
        return LOGGING_LEVELS[LOGGER_LEVEL]
    elif isinstance(level, str):  # This elif is unnecessary!
        return LOGGING_LEVELS[level]
    if level > 2:
        level = 2  # Enables users to do -vv
    return VERBOSITY_LEVELS[level]


def _use_color(choice: bool) -> str:
    """Return log format based on the choice.

    If choice is True, colored log format is returned else non-colored
    format is returned.

    :param choice: Boolean value to allow colored logs.
    :returns: Colored or non-colored log format based on choice.
    """
    if choice:
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

    :param fmt: Log message format.
    :param datefmt: Log datetime format.
    """

    def __init__(self, fmt: str, datefmt: str) -> None:
        """Initialize the ANSIFormatter with required formats."""
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
        # ``langxa.logger.TTYInspector()`` class.
        if getattr(record, "isatty", False):
            setattr(record, "color", ANSI_HUES[record.levelno])
            setattr(record, "gray", ANSI_HUES[90])
            setattr(record, "reset", ANSI_HUES[00])
        else:
            for attr in ANSI_ATTRS:
                setattr(record, attr, "")

    @staticmethod
    def _decolorize(record: logging.LogRecord) -> None:
        """Remove ``color`` and ``reset`` attributes from the log
        record.

        This method is opposite of :py:meth:`colorize() <colorize()>`.
        It prevents the record from writing un-readable ANSI characters
        to a non-TTY interface.

        :param record: Instance of the logged event.
        """
        for attr in ANSI_ATTRS:
            delattr(record, attr)

    @staticmethod
    def formatException(
        ei: tuple[type, BaseException, types.TracebackType | None]
        | tuple[None, ...]
    ) -> str:
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
        return f"{cls_.__name__}: {msg} line {lineno}"  # type: ignore

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

        If any exception is captured then it is formatted using
        the :py:meth:`formatException() <formatException()>` and
        replaced with the original message.

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


class Handler:
    """Handler class which dispatches logging events to streams.

    This is the base handler class which acts as a placeholder to define
    the handler interface. Using this handler class, one can extend the
    default behavior of the handlers present in the logging module.

    :param handler: Handler instance which will output to a stream.
    :param formatter: Formatter instace to use for formatting.
    :param level: Minimum logging level of the event.
    """

    def __init__(
        self,
        handler: logging.Handler,
        formatter: logging.Formatter,
        level: int | str,
    ) -> None:
        """Initialize the Handler class."""
        self.handler = handler
        # Setting a formatter is technically not required, but this
        # handler deals with things which output something, either to
        # the TTY or to an output file. So providing a formatter makes
        # more sense here.
        self.handler.setFormatter(formatter)
        self.handler.setLevel(level)

    def add_handler(self, logger: logging.Logger) -> None:
        """Add handler to the logger object."""
        logger.addHandler(self.handler)


class FileHandler:
    """Handler class to aid with the underlying metadata of the file.

    This class provides with the metadata like the file's name, stem,
    suffix (extension), parent directory, etc. It behaves like a generic
    class which provides data about any file provided as input. But we
    use it here to provide the meta informations about the log file.

    :param filename: Absolute path of the file whose information needs
        to be extracted.

    .. note::

        The below class could be replaced by ``pathlib.Path()`` but it
        adds time and memory overhead.

    """

    def __init__(self, filename: str) -> None:
        """Initialize FileHandler class with filename."""
        self.filename = os.path.abspath(filename)

    @cached_property
    def parent(self) -> str:
        """Return parent directory of the file."""
        return os.path.dirname(self.filename)

    @cached_property
    def basename(self) -> str:
        """Return only name-part of the file with extension."""
        return os.path.basename(self.filename)

    @cached_property
    def suffix(self) -> str:
        """Return extension of the file."""
        return os.path.splitext(self.filename)[-1]

    @cached_property
    def stem(self) -> str:
        """Return only name-part of the file without extension."""
        return os.path.splitext(os.path.basename(self.filename))[0]

    @property
    def size(self) -> int:
        """Return size of the file in bytes."""
        return os.stat(self.filename).st_size

    @property
    def siblings(self) -> list[str]:
        """Return list of matching files in the parent directory."""
        return sorted(
            fnmatch.filter(os.listdir(self.parent), f"{self.basename}.*?")
        ) + [self.basename]

    @property
    def index(self) -> int:
        """Return count of files with the same name."""
        return len(self.siblings) + 1


class RotatingFileHandler(FileHandler):
    """Handler instance for logging to a set of files which switch from
    one file to the next when the current file reaches a certain size.

    By default, the file grows indefinitely. You can specify particular
    values to allow the file to rollover at a pre-determined size. The
    implementation of this class is very similar to the rotating file
    handler, ``logging.handlers.RotatingFileHandler()`` but allows
    writing from stdin, stdout and stderr to a file.

    :param filename: Absolute path of the log file.
    :param max_bytes: Maximum size in bytes after which the rollover
        should happen.
    :param mode: Mode in which the file needs to be opened, defaults to
        append ``a`` mode.
    :param encoding: Platform-dependent encoding for the file, defaults
        to None.

    .. note::

        Rollover occurs whenever the current log file is nearly
        ``max_bytes`` in size. The system will successively create new
        files with same pathname as the base file, but with extensions
        ".1", ".2", etc. appended to it.

    .. note::

        If ``max_bytes`` is zero, the rollover never occurs. The
        implementation mimics the behavior of rotating file handler
        except the ``backupCount``.

    """

    def __init__(
        self,
        filename: str,
        max_bytes: int,
        mode: str = "a",
        encoding: str | None = None,
    ) -> None:
        """Open the file and use it as the stream for logging."""
        super().__init__(filename)
        self.max_bytes = max_bytes
        if not isinstance(mode, str):
            raise TypeError(f"Invalid mode: {mode}")
        if not set(mode) <= set("xrwabt+"):
            # Technically, the mode = "r" is also valid but it is not
            # useful in this case. Modes, "w" and "a" are the only valid
            # options here.
            raise ValueError(f"Invalid mode: {mode}")
        if self.max_bytes > 0:
            mode = "a"
        self.mode = mode
        if encoding is None:
            encoding = os.device_encoding(0)
        self.encoding = encoding
        self._closed = False
        self.idx = self.index - 1
        self._open()

    def _open(self) -> None:
        """Open file for the I/O operations."""
        self.fd = open(self.filename, self.mode, encoding=self.encoding)
        self._closed = False

    def close(self) -> None:
        """Close the file.

        A closed file cannot be used for further I/O operations. The
        close() may be called more than once without errors. Thus making
        it idempotent.
        """
        if not self._closed:
            self.fd.close()
        self._closed = True

    def flush(self) -> None:
        """Flush write buffer, if applicable.

        This is not implemented for read-only and non-blocking streams.
        Flushing stream ensures that the data has been cleared from the
        internal buffer without any guarantee on whether its written to
        the local disk.

        This means that the data would survive an application crash but
        not necessarily an OS crash.
        """
        self.fd.flush()

    def write(self, data: Any) -> None:
        """Write data to the file.

        This is done after clearing the contents of the file on first
        write and then appending on subsequent calls. This method also
        rotates the file if provided with correct argument.

        This function writes stdin, stdout and stderr to a file.
        """
        # This writes to a file.
        self.fd.write(data)
        self.flush()
        # This writes to the TTY.
        sys.__stdout__.write(data)
        sys.__stdout__.flush()
        self.rotate()

    def rotate(self) -> None:
        """Rotate the current log file when it is nearly in size.

        This method ensures that the current file in use never goes
        beyond the specified size. To do this, the handler checks if
        the size of the file after the data is written exceeds the
        specified size. If the file approaches the size, the handler
        closes the stream, renames the file and continues writing to a
        new file.

        This rotating is also called rollover.
        """
        rollover = False
        if self.max_bytes and self.max_bytes > 0:
            if self.size > self.max_bytes:
                rollover = True
        if rollover:
            self.close()
            if os.path.exists(self.filename):
                os.rename(self.filename, f"{self.filename}.{self.idx}")
                self.idx += 1
            else:
                raise FileNotFoundError
            self._open()

    def __del__(self) -> None:
        """Restore stdin, stdout and stderr."""
        sys.stdout = sys.__stdout__
        sys.stdin = sys.__stdin__
        sys.stderr = sys.__stderr__
        self.close()

    def readline(self) -> str:
        """Read input from stdin to log into the output file."""
        # This takes in input from the stdin.
        line = sys.__stdin__.readline()
        sys.__stdin__.flush()
        self.fd.write(line)
        self.flush()
        return line


class TTYInspector(logging.StreamHandler):  # type: ignore
    """A StreamHandler derivative which inspects if the output stream
    is a TTY or not.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Add hint if the specified stream is a TTY.

        The ``hint`` here, means the boolean specification as this
        attribute helps to identify a stream's interface. This solves
        a major problem when printing un-readable ANSI sequences to a
        non-TTY interface.

        :param record: Instance of the logged event.
        :return: Formatter string for the output stream.
        """
        if hasattr(self.stream, "isatty"):
            try:
                setattr(record, "isatty", self.stream.isatty())
            except ValueError:
                setattr(record, "isatty", False)
        else:
            setattr(record, "isatty", False)
        strict = super().format(record)
        delattr(record, "isatty")
        return strict


class StreamHandler(Handler):
    """Handler class which writes appropriately formatted logging
    records to a TTY stream.

    :param stream: IO stream.
    :param formatter: Formatter instance to be used for formatting
        record.
    :param level: Minimum logging level of the event.

    .. note::

        This class does not close the stream, as ``sys.stdout`` or
        ``sys.stderr`` may be used.

    """

    def __init__(
        self,
        stream: IO[str] | None,
        formatter: logging.Formatter,
        level: int | str,
    ) -> None:
        """Initialize StreamHandler with a TTYInpsector stream."""
        super().__init__(TTYInspector(stream), formatter, level)


def get_logger(module: str) -> logging.Logger:
    """Return logger instance.

    This function is supposed to be used by the modules for logging.
    This logger is a child logger which reports logs back to the parent
    logger defined by the :py:func:`init() <langxa.logger.init()>`.

    :param module: Module to be logged.
    :return: Logger instance.
    """
    return logging.getLogger(LOGGER_NAME).getChild(module)


def init(
    name: str = LOGGER_NAME,
    level: int = logging.INFO,
    fmt: str | None = None,
    datefmt: str = ISO8601,
    color: bool = True,
    filename: str | None = None,
    max_bytes: int = 10_000_000,
    encoding: str | None = None,
    filemode: str = "a",
    skip_logging: bool = False,
    handlers: list[logging.Handler] = [],
    stream: IO[str] | None = sys.stderr,
    capture_warnings: bool = True,
) -> logging.Logger:
    """Initialize an application level logger.

    This function initializes an application level logger with default
    configurations for the logging system.

    If handlers are provided as part of input, this function overrides
    the default behavior (logging to file and streaming colored outputs)
    in favour of the provided handler. It is a convenience function
    intended for use by simple applications to do one-shot
    configuration.

    The default behavior is to create ``StreamHandler`` and a
    ``RotatingFileHandler`` which writes to sys.stderr and an output
    log file respectively.

    :param name: Name for the logger, defaults to "langxa.main".
    :param level: Minimum logging level of the event, defaults to INFO.
    :param fmt: Log message format, defaults to None.
    :param datefmt: Log datetime format, defaults to ISO8601 format.
    :param color: Boolean option to whether display colored log outputs
        on the terminal or not, defaults to True.
    :param filename: Absolute path of the log file, defaults to None.
    :param max_bytes: Maximum size in bytes after which the rollover
        should happen, defaults to 10 MB.
    :param encoding: Platform-dependent encoding for the file, defaults
        to None.
    :param filemode: Mode in which the file needs to be opened, defaults
        to append ``a`` mode.
    :param skip_logging: Boolean option to whether skip the logging
        process, defaults to False.
    :param handlers: List of various logging handlers to use, defaults
        to [].
    :param stream: IO stream, defaults to ``sys.stderr``.
    :param capture_warnings: Boolean option to whether capture the
        warnings while logging, defaults to True.
    :return: Configured logger instance.
    """
    msg = ""
    logger = logging.getLogger(name)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    if not logger.handlers:
        level = _select_log_level(level)
        if fmt is None:
            fmt = _use_color(color)
        formatter = ANSIFormatter(fmt, datefmt)
        stream_handler = StreamHandler(stream, formatter, level)
        msg = " with StreamHandler (default)"
        handlers.append(stream_handler)  # type: ignore
        if not _skip_output_log(skip_logging):
            if filename is None:
                filename = LOG_FILE
                _setup_logs(skip_logging, filename)
                rotator = RotatingFileHandler
                sys.stdout = sys.stderr = sys.stdin = rotator(  # type: ignore
                    filename, max_bytes, filemode, encoding
                )
        logger.setLevel(level)
        for handler in handlers:
            if isinstance(handler, Handler):
                handler.add_handler(logger)
        msg += " and RotatingFileHandler (for output logging)"
        logging.captureWarnings(capture_warnings)
        logger.debug("Initializing an application level logger" + msg)
    return logger


def customize_logger(parser: argparse.ArgumentParser) -> None:
    """Parser for customizing the logger."""
    parser.add_argument(
        "-f",
        "--file",
        default=LOG_FILE,
        help=(
            "Path for logging and maintaining the historical log "
            "(Default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--format",
        help=(
            "Logging message string format. To read more on the log record "
            "attributes, see this: https://docs.python.org/3/library/logging."
            "html#logrecord-attributes."
        ),
    )
    parser.add_argument(
        "--datefmt",
        default=ISO8601,
        help="Logging message datetime format (Default: %(default)s).",
    )
    parser.add_argument(
        "-l",
        "--level",
        default=logging.WARNING,
        help=(
            "Minimum logging level for the message (Default: %(default)s). "
            "The logging level can be overridden by setting the environment "
            "variable 'LANGXA_LOGGING_LEVEL' (corresponding to "
            "DEBUG, INFO, WARNING, ERROR and CRITICAL logging levels)."
        ),
    )
    parser.add_argument(
        "-b",
        "--max-bytes",
        default=10_000_000,
        help="Output log file size in bytes (Default: %(default)s).",
    )
    parser.add_argument(
        "--no-output",
        action="store_true",
        help=(
            "Skips logging the I/O from stdin, stdout and stderr to the "
            "log file. This behavior can be overridden by setting the "
            "environment variable 'LANGXA_SKIP_LOGGING' to TRUE. If this is "
            "set, it will carry more precedence."
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_false",
        help="Suppress colored output.",
    )
