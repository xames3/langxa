"""Handlers for logging langXA.

These handlers are supposed to be used with the ``langxa._main`` module.
They basically extend the normal usage implied by it. We could've used
the builtin logging handlers but they don't allow to write the stdin
input.

The handler implemented in this module allows us to write the stdin,
stdout and stderr (basically anything that can be printed out) to an
output file.
"""

import fnmatch
import logging
import os
import sys
from functools import cached_property
from typing import IO
from typing import Any
from typing import List
from typing import Optional
from typing import Union

__all__ = ["FileHandler", "RotatingFileHandler", "StreamHandler"]


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
