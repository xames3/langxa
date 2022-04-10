"""Logging module to capture and control the langXA's output logs.

The module provides the necessary abstractions for overriding the
standard logging capabilities provided by default. This is done by
monkey patching the objects from the ``logging`` module.

This module is also responsible for rendering colors on the terminal
for foreshadowing the severity of the logging levels. Besides this, we
tend to capture all the inputs and outputs (stdin, stdout and stderr)
from the terminal.

With that, the module also provides a couple of handlers which basically
extend the normal usage of the this module. We could've used the builtin
logging handlers but they don't allow to write the stdin input.

The handler implemented in this module allows us to write the stdin,
stdout and stderr (basically anything that can be printed out) to an
output file.
"""

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
from typing import List
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Union

__all__ = [
    "FileHandler",
    "ISO8601",
    "RotatingFileHandler",
    "StreamHandler",
    "get_logger",
    "init",
]

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


class Handler:
    """Handler class which dispatches logging events to streams.

    This is the base handler class which acts as a placeholder to define
    the handler interface. Using this handler class, one can extend the
    default behavior of the handlers present in the ``logging`` module.

    :param handler: Handler instance which will output to a stream.
    :param formatter: Formatter instace to use for formatting.
    :param level: Logging level of the logged event, defaults to None.
    """

    def __init__(
        self,
        handler: logging.Handler,
        formatter: logging.Formatter,
        level: Optional[Union[int, str]] = None,
    ) -> None:
        """Initialize the Handler class with default level."""
        self.handler = handler
        # Setting a formatter is technically not required, but this
        # handler deals with things which output something, either to
        # the TTY or to an output file. So providing a formatter makes
        # more sense here.
        self.handler.setFormatter(formatter)
        if level is None:
            level = logging.INFO
            # NOTE: Level is optional, if nothing is passed it'll
            # default to the ``logging.INFO``.
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
    def siblings(self) -> List[str]:
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
    :param mode: Mode in which the file needs to be opened, defaults to
        append ``a`` mode.
    :param max_bytes: Maximum size in bytes after which the rollover
        should happen, defaults to 10 MB.
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

    .. seealso::

        [1] logging.handlers.RotatingFileHandler()
    """

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        max_bytes: int = 10000000,
        encoding: Optional[str] = None,
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


class TTYInspector(logging.StreamHandler):
    """A StreamHandler derivative which inspects if the output stream
    is a TTY or not.

    .. seealso::

        [1] logging.StreamHandler.format()
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
    :param level: Logging level of the logged event, defaults to None.

    .. note::

        This class does not close the stream, as ``sys.stdout`` or
        ``sys.stderr`` may be used.

    .. seealso::

        [1] langxa.logger._main.Handler()
    """

    def __init__(
        self,
        stream: Optional[IO[str]],
        formatter: logging.Formatter,
        level: Optional[Union[int, str]] = None,
    ) -> None:
        """Initialize StreamHandler with a TTYInpsector stream."""
        super().__init__(TTYInspector(stream), formatter, level)


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
