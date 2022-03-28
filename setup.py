"""langXA setup.

This will install the ``langxa`` package in the python 3.6+ environment.
Before proceeding, please ensure you have a virtualenv setup & running.

See https://github.com/xames3/langxa/ for more help.
"""

try:
    import setuptools
except ImportError:
    raise RuntimeError(
        "Could not install package in the environment as setuptools is "
        "missing. Please create a new virtual environment before proceeding."
    )

import platform

MIN_PYTHON_VERSION = ("3", "6")

if platform.python_version_tuple() < MIN_PYTHON_VERSION:
    raise SystemExit(
        "Could not install langxa in the environment. It requires python "
        f"version 3.6+, you are using {platform.python_version()}"
    )

if __name__ == "__main__":
    setuptools.setup()
