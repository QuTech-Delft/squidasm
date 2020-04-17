import logging

from squidasm.run import run_applications

from aliceTest import main as alice_main
from bobTest import main as bob_main


def main():
    logging.basicConfig(level=logging.INFO)
    run_applications({
        "Alice": alice_main,
        "Bob": bob_main,
    })


if __name__ == "__main__":
    main()
