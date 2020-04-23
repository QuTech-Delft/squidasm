import os
import logging
from runpy import run_path

from netqasm.logging import set_log_level
from squidasm.run import run_applications

path_to_here = os.path.dirname(__file__)
alice_main = run_path(os.path.join(path_to_here, "alice.py"))['main']
bob_main = run_path(os.path.join(path_to_here, "bob.py"))['main']


def main():
    set_log_level(logging.DEBUG)
    run_applications({
        "Alice": alice_main,
        "Bob": bob_main,
    })


if __name__ == "__main__":
    main()
