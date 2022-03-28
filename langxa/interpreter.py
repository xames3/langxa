"""langXA code interpreter.

This interpreter module allows users to actively type code in the shell
and run commands. The main goal is to re-create something like the
Python interpreter.
"""

import itertools
import math
import os
from typing import Generator
from typing import Tuple

from langxa._version import __status__
from langxa._version import __version__
from langxa.logger import get_logger

logger = get_logger(__name__)


def _confirm_quitting_interpreter(idx: int) -> int:
    """Confirm if the user wants to quit the interpreter.

    This function checks if the user wants to exit the interpreter
    session. If yes, the user is expected to press ``Y``, else the
    session will be resumed. Although this behavior can be overridden by
    pressing EOF characters (CTRL + D for POSIX and CTRL + Z for Win32).

    :param idx: Input index. This index is required to match the number
        of ``?`` symbols with number of input lines.
    :returns: Status code of the exit response.
    """
    quit_cmd = f"CTRL + {('D', 'Z')[os.name == 'nt']}"
    while 1:
        try:
            # See https://stackoverflow.com/a/2189827/14316408 for
            # calculating the length of the digits.
            confirm = input(
                "Are you sure you want to exit the interpreter? "
                f"Press Y to quit and {quit_cmd} to force quit\n... "
                f"[{'?' * int(math.log10(idx) + 1)}]: "
            )
            return (1, 0)[confirm in ("Y", "y")]
        except KeyboardInterrupt:
            # When the prompt is asked, the user is expected to press
            # "Y" in case of quitting, else the session will be resumed.
            # But if the user spams using CTRL + C, this pass will
            # silently ignore it and re-prompt the user.
            pass
        except EOFError:
            # On prompt if the user invokes the EOFError, this will
            # force the system to gracefully quit the active session.
            return 0


def _capture_user_input() -> Generator[Tuple[int, str], None, None]:
    """Continuously capture user input from stdin.

    This function continuously captures the user inputs from stdin and
    yields the input to ``langxa.interpreter.process()`` function. This
    continuous interaction with the stdin blocks the I/O, so ensure that
    if one needs to exit out of this cycle, s/he should quit the session
    gracefully.

    This can be done using the ``KeyboardInterrupt`` or ``CTRL + C``.
    By raising an ``KeyboardInterrupt`` this yielding is paused, and the
    system enters an intermittent state from where it can be forced out.

    However, doing so might not have clean experience as it might* leave
    traces of the application in the memory causing memory leaks.
    """
    # The below log message represents interpreter's successful boot and
    # provides some contextual information about it like the version,
    # development status, PID, etc.
    logger.info(
        f"Starting langXA interpreter v{__version__}-{__status__} in shell "
        f"mode with PID {os.getpid()} in {os.path.dirname(__file__)}"
    )
    # NOTE: The below control flow is purposely implemented using a for
    # loop. An infinite while loop with an incrementing counter could've
    # been used instead, but some internal tests and benchmarking proved
    # that ``itertools.count()`` was more memory efficient and graceful.
    for idx in itertools.count(start=1):
        try:
            yield idx, input(f">>> [{idx}]: ")
        except KeyboardInterrupt:
            if not _confirm_quitting_interpreter(idx):
                logger.warning("Clearing global state variables [cleanup]")
                # TODO (xames3): Implement logic for cleaning global
                # variables before breaking out of the loop.
                break
        except EOFError:
            logger.fatal("Force shutting the interpreter")
            # TODO (xames3): Similar global state cleaning logic should
            # be implemented here but this cleanup would be more
            # aggressive.
            break


def process() -> int:
    """Process inputs from the interpreter."""
    for idx, input_ in _capture_user_input():
        # TODO (xames3): Implement logic for executing (exec) and
        # evaluating (eval) the input strings from the interpreter. For
        # now the current implementation just prints out the input.
        print(f"<<< [{idx}]:", input_)
    return 0
