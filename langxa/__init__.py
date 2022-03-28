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

try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0.0"
