import os
import logging

from netqasm.lang.parsing import parse_register
from netqasm.logging.glob import set_log_level, get_netqasm_logger
from netqasm.runtime.app_config import default_app_config

from squidasm.run import run_applications
from squidasm.communicator import SimpleCommunicator

logger = get_netqasm_logger()


def get_subroutine():
    dir_path = os.path.dirname(__file__)
    file_path = os.path.join(dir_path, 'subroutine.nqasm')
    with open(file_path, 'r') as f:
        subroutine = f.read()
    return subroutine


def main():
    set_log_level(logging.WARNING)

    subroutine = get_subroutine()

    logger.info("Application at Alice will submit the following subroutine to QDevice:")
    logger.info(subroutine)

    def run_alice():
        logger.debug("Starting Alice thread")
        communicator = SimpleCommunicator("Alice", subroutines=[subroutine])
        communicator.run(num_times=1)
        logger.debug("End Alice thread")

    def post_function(backend):
        shared_memory = backend._subroutine_handlers["Alice"]._executioner._shared_memories[0]
        zero_outcomes = shared_memory.get_register(parse_register("R1"))
        one_outcomes = shared_memory.get_register(parse_register("R2"))
        logger.info(f'zero_outcomes = {zero_outcomes}')
        logger.info(f'one_outcomes = {one_outcomes}')
        assert zero_outcomes == 0
        assert one_outcomes == 300

    run_applications([
        default_app_config("Alice", run_alice),
    ], use_app_config=False, post_function=post_function)


if __name__ == '__main__':
    main()
