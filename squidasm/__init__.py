from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("squidasm")
except PackageNotFoundError:
    # package is not installed
    pass
