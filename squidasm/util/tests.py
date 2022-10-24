from typing import Generator


def yield_from(generator: Generator):
    try:
        while True:
            next(generator)
    except StopIteration as e:
        return e.value
