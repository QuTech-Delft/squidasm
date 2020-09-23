import os
from runpy import run_path

from squidasm.run import run_applications
from squidasm.run.app_config import default_app_config

path_to_here = os.path.dirname(__file__)
alice_main = run_path(os.path.join(path_to_here, "app_alice.py"))['main']
bob_main = run_path(os.path.join(path_to_here, "app_bob.py"))['main']


def main():
    run_applications([
        default_app_config("alice", alice_main),
        default_app_config("bob", bob_main)
    ])


if __name__ == "__main__":
    main()
