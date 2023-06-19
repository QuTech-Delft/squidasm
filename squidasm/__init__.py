from importlib.metadata import PackageNotFoundError, version
SUPER_HACKY_SWITCH = False

try:
    __version__ = version("squidasm")
except PackageNotFoundError:
    # package is not installed
    pass
