import inspect
import logging
import os
import subprocess

from netqasm.logging.glob import set_log_level


def _has_first_argument(function, argument):
    """Checks if a function takes a named argument as the first argument"""
    argnames = inspect.getfullargspec(function).args
    return argnames[0] == "no_output"


def main():
    set_log_level(logging.WARNING)
    path_to_here = os.path.dirname(os.path.abspath(__file__))
    for root, _folders, files in os.walk(path_to_here):
        for filename in files:
            if (
                filename.startswith("example") and filename.endswith(".py")
            ) or filename == "run.py":
                filepath = os.path.join(root, filename)
                print(f"Running example {filepath}")
                result = subprocess.run(
                    ["python3", filepath],
                    stdout=subprocess.DEVNULL,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"Example {filepath} failed!")

    print("All examples work!")


if __name__ == "__main__":
    main()
