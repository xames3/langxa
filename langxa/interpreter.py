"""langXA code interpreter.

An interpreter is a kind of code or a program that executes other code.
When someone writes something (in any programming language), it gets
converted from the source code written by the developer into an
intermediate language which is again translated into the machine level
language and then it is executed.

An interpreter takes an interactive command and executes it. The entire
source code is compiled line by line. Compilation of the source codes
occur through the translation process.

A compiler does a lot less work than the interpreter. However, codes
are generally compiled in to a byte code which means a compiler isn't
always necessary which is in this case. The interpreter will read the
langXA code and then look at each line of code created to verify the
instructions and ensure they're formatted correctly. If there are any
errors within the program, they will appear as each line is translated.
The interpreter can execute the codes immediately through the standard
input.

The interpreter operates somewhat like the Unix shell, when called with
standard input connected to a tty device, it reads and executes commands
interactively; when called with a file name argument or with a file as
standard input, it reads and executes a script from that file.

This interpreter module allows users to actively type code in the shell
and run commands. The main goal is to re-create something like the
Python interpreter.

.. seealso::

    [1] Read `this <https://rb.gy/pwo96i>`_ Medium blog post to
    understand what an interpreter is and how it works.

    [2] To know the differences between Python Compiler and Interpreter
    read `this <https://rb.gy/h9bruv>`_.
"""

from __future__ import annotations

import itertools
import math
import os
from typing import Generator

from langxa._version import __status__
from langxa._version import __version__
from langxa.errors import Error
from langxa.lexer import Lexer
from langxa.logger import get_logger
from langxa.tokenizer import Token

__all__ = ["Interpreter"]

logger = get_logger(__name__)


class Interpreter:
    """A live interpreter session to evaluate and execute langXA's
    commands from source or stdin.

    This interpreter session works similar to the CPython's interpreter,
    following a REPL -- Read, Eval, Print and Loop way of handling code.
    """

    def __init__(self) -> None:
        """Initialize interpreter with line number 0 (default)."""
        self.ln = 0

    def capture_user_input(self) -> Generator[tuple[int, str], None, None]:
        """Continuously capture user input from stdin.

        This method continuously captures the user inputs from stdin and
        yields the input to :py:meth:`process() <process()>` method.
        This continuous interaction with the stdin blocks the I/O, so it
        ensures that if one needs to exit out of this cycle, a graceful
        quitting is expected.

        This can be done by raising the ``KeyboardInterrupt`` or by
        pressing ``CTRL + C``. By raising an ``KeyboardInterrupt`` this
        yielding is paused, and the system enters an intermittent state
        from where it can be forced out.

        However, doing so might not have clean experience as it might*
        leave traces of the application in the memory causing memory
        leaks.
        """
        # The below log message represents interpreter's successful boot
        # and provides some contextual information about it like the
        # version, development status, PID, etc.
        logger.info(
            f"Starting langXA interpreter v{__version__}-{__status__} in "
            f"shell mode with PID {os.getpid()} in {os.path.dirname(__file__)}"
        )
        # NOTE: The below control flow is purposely implemented using a
        # for loop. An infinite while loop with an incrementing counter
        # could've been used instead, but some internal tests and
        # benchmarking proved that ``itertools.count()`` was more memory
        # efficient and graceful.
        for ln in itertools.count(start=1):
            try:
                self.ln = ln
                yield ln, input(f">>> [{ln}]: ")
            except KeyboardInterrupt:
                if not self.confirm_quitting():
                    logger.warning("Clearing global state variables [cleanup]")
                    # TODO (xames3): Implement logic for cleaning global
                    # variables before breaking out of the loop.
                    break
            except EOFError:
                logger.fatal("Force shutting the interpreter [EOF]")
                # TODO (xames3): Similar global state cleaning logic should
                # be implemented here but this cleanup would be more
                # aggressive.
                break

    def confirm_quitting(self) -> int:
        """Confirm if the user wants to quit the interpreter.

        This method checks if the user wants to exit the interpreter
        session. If yes, the user is expected to press ``Y``, else the
        session will be resumed. Although this behavior can be
        overridden by pressing EOF characters (CTRL + D for POSIX and
        CTRL + Z for Win32).

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
                    f"[{'?' * int(math.log10(self.ln) + 1)}]: "
                )
                return (1, 0)[confirm in ("Y", "y")]
            except KeyboardInterrupt:
                # When the prompt is asked, the user is expected to
                # press "Y" in case of quitting, else the session will
                # be resumed. But if the user spams using CTRL + C, this
                # pass will silently ignore it and re-prompt the user.
                pass
            except EOFError:
                # On prompt if the user invokes the EOFError, this will
                # force the system to gracefully quit the active session.
                return 0

    def _compile(
        self, filename: str, input_: str
    ) -> tuple[list[Token] | None, Error | None]:
        """Compile source code or input commands.

        This method performs compilation of the source code either be it
        from a script or from the interpreter session. Compilation is
        simply a translation step. It incorporates a lexer which then
        tokenizes the inputs.

        :returns: List of detected tokens and error, if any.
        """
        tokens, error = Lexer(filename, input_).tokenize()
        if error:
            error._offset = int(math.log10(self.ln) + 1)
            return None, error
        return tokens, error

    def process_input(self) -> int:
        """Process inputs from the interpreter."""
        for ln, input_ in self.capture_user_input():
            # TODO (xames3): Implement logic for executing (exec) and
            # evaluating (eval) the input strings from the interpreter.
            # For now the current implementation just prints out the
            # input.
            if not input_.strip():  # Handle things when return is spammed.
                continue
            if input_ in ("QUIT", "EXIT", "quit", "exit"):
                return 0
            tokens, error = self._compile("<stdin>", input_)
            if error:
                print(f"ERR [{ln}]:", error.message)
            else:
                print(f"<<< [{ln}]:", tokens)
        return 0
