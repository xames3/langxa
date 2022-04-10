"""Main entry point for langXA's interpreter.

This module allows the usage of the langXA's interpreter over the CLI.
It allows the use of ``langxa`` keyword on the CLI to trigger langXA's
interpreter session. This is similar to how Python's interpreter works.
"""

import argparse
import os
import sys
import textwrap
from typing import Final
from typing import Iterable
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Union

import langxa
from langxa._version import __doc__
from langxa._version import __status__
from langxa._version import __version__
from langxa.interpreter import process_input
from langxa.logger import init

# HACK: This patch ensures the colors are displayed on the Win32
# terminals, else the ANSI sequence would be shown. However, please note
# that it is not required to execute color command, any valid Win32
# command will work. We just need to prepare the terminal for what's
# coming.
if os.name == "nt":
    os.system("color")

# NOTE: Do not change this!
PROG: Final[str] = "langxa"
TERMINAL_WIDTH: int = 75  # Can substitute with os.get_terminal_size()

_verbosity_levels: Mapping[int, int] = {0: 30, 1: 20, 2: 10}
_logging_levels: Mapping[str, int] = {
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

_log_level = os.getenv("LANGXA_LOG_LEVEL")
_skip_logging = os.getenv("SKIP_LANGXA_LOGS")

_logs_dir: str = os.path.join(os.path.expanduser("~"), ".langxa")


def _setup_logs(override: Union[bool, str], path: str) -> Optional[str]:
    """Setup a log directory and log I/O from the stdin/out to the file.

    The I/O logs are stored in the ``$HOME`` directory for redundancies
    and maintaining history*. In case the directory is deleted or
    doesn't exist, this function will create it.

    Although if this behavior is not wanted, you can skip logging
    entirely by setting the environment variable "SKIP_LANGXA_LOGS" to
    ``TRUE``.

    :param override: Set "SKIP_LANGXA_LOGS" to True in order to
        override logging.
    :returns: Path of the log file if "SKIP_LANGXA_LOGS" is not set else
        None.
    """
    if override or override == "TRUE":
        return None
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _skip_output_log(choice: bool) -> bool:
    """Return whether to output logs to a file.

    If the choice is set at an environment variable level, it'll
    override the passed argument. If nothing is set, it'll continue to
    log output to the file.

    :param choice: Boolean flag from the passed argument.
    :returns: Status whether to log file or not.
    """
    # This ensures that only ``TRUE`` is considered as a valid choice
    # here. This is required, else any valid string would be considered
    # as True and loop might accidentally execute.
    if (_skip_logging and _skip_logging == "TRUE") or choice:
        return True
    return False


def _select_log_level(level: int) -> int:
    """Select which logging level to use.

    If the logging level is set at an environment variable level, it'll
    override the verbosity counter. If nothing is set, it'll use the
    value of verbosity for logging. Higher the counter, lower the
    logging level.

    :param level: Verbosity counter value.
    :returns: Logging level.
    """
    if _log_level:
        return _logging_levels[_log_level]
    if level > 2:
        level = 2  # Enables users to do -vv
    return _verbosity_levels[level]


class langXAHelpFormatter(argparse.RawTextHelpFormatter):
    """Custom formatter for customizing usage message and wrapping
    lines.

    This class overrides the default behavior of the ``ArgumentParser``
    class and adds custom usage message template. Also it sets a hard
    limit for wrapping the help and description strings.
    """

    # See https://stackoverflow.com/a/35848313/14316408 for customizing
    # the usage section when looking for help.
    def add_usage(
        self,
        usage: Optional[str],
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._ArgumentGroup],
        prefix: Optional[str] = None,
    ) -> None:
        """Capitalizes the usage text."""
        if prefix is None:
            prefix = "Usage:\n  "
        print()  # Useless print to display everything from a new line.
        return super().add_usage(usage, actions, groups, prefix)

    # See https://stackoverflow.com/a/35925919/14316408 for adding the
    # line wrapping logic for the description.
    def _split_lines(self, text: str, width: int) -> List[str]:
        """Unwraps the lines to width of the terminal."""
        text = self._whitespace_matcher.sub(" ", text).strip()
        return textwrap.wrap(text, TERMINAL_WIDTH)

    # See https://stackoverflow.com/a/13429281/14316408 for hiding the
    # metavar is sub-command listing.
    def _format_action(self, action: argparse.Action) -> str:
        """Hides MetaVar in command listing."""
        parts = super()._format_action(action)
        if action.nargs == argparse.PARSER:
            parts = "\n".join(parts.split("\n")[1:])
        return parts


def main(argv: Optional[Sequence] = None) -> int:
    """langXA's argument parser object."""
    argv = argv if argv is not None else sys.argv[1:]
    usage = f"{PROG} [option] ... [script]"
    version = f"{PROG} {__version__}-{__status__}"
    description = langxa.__doc__
    epilog = f"Read full documentation at: <{__doc__}>"
    title = "Options and arguments (and corresponding environment variables)"
    parser = argparse.ArgumentParser(
        prog=PROG,
        usage=usage,
        description=description,
        epilog=epilog,
        formatter_class=langXAHelpFormatter,
        add_help=False,
    )
    parser._optionals.title = title
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show help.",
    )
    # See https://stackoverflow.com/a/8521644/812183 for adding version
    # specific argument to the parser.
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=version,
        help="Show langXA's installed version and exit.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help=(
            "Increase the logging verbosity. This option is additive, and "
            "can be used twice. The logging verbosity can be overridden by "
            "setting LANGXA_LOG_LEVEL (corresponding to "
            "DEBUG, INFO, WARNING, ERROR and CRITICAL logging levels)."
        ),
    )
    parser.add_argument(
        "-l",
        "--log",
        default=os.path.join(_logs_dir, "history.log"),
        help=(
            "Path for logging and maintaining the historical log "
            "(Default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_false",
        help="Suppress colored output.",
    )
    parser.add_argument(
        "--no-output",
        action="store_true",
        help=(
            "Skips logging the I/O from stdin, stdout and stderr to the "
            "log file. This behavior can be overridden by setting "
            "SKIP_LANGXA_LOGS to TRUE. If this is set, it'll carry more "
            "precedence."
        ),
    )
    args = parser.parse_args(argv)
    level = _select_log_level(args.verbose)
    logger = init(
        name="langxa.main",
        filename=_setup_logs(_skip_output_log(args.no_output), args.log),
        level=level,
        color=args.no_color,
    )
    if level == 20:
        logger.info(
            "No active log level set, falling back to default level: INFO"
        )
    elif level == 10:
        logger.debug("Launching interpreter in DEBUG mode [logging]")
    process_input()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
