from typing import Generator


def yield_from(generator: Generator):
    try:
        while True:
            next(generator)
    except StopIteration as e:
        return e.value


def text_equal(text1, text2) -> bool:
    # allows whitespace differences
    lines1 = [line.strip() for line in text1.split("\n") if len(line) > 0]
    lines2 = [line.strip() for line in text2.split("\n") if len(line) > 0]
    for line1, line2 in zip(lines1, lines2):
        if line1 != line2:
            return False
    return True
