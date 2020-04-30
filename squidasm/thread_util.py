from time import sleep


def as_completed(futures, sleep_time=0):
    futures = list(futures)
    while len(futures) > 0:
        for i, future in enumerate(futures):
            if future.ready():
                futures.pop(i)
                yield future
        if sleep_time > 0:
            sleep(sleep_time)
