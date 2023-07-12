import logging
from typing import List, Optional, Union

import netsquid as ns


class SimTimeFilter(logging.Filter):
    def filter(self, record):
        record.simtime = ns.sim_time()
        return True


class LogManager:
    """
    Class for setting up and obtaining a logger that has been setup for SquidASM use.
    Logger for SquidASM has a default format that includes the time inside the simulation for each message.
    """

    STACK_LOGGER = "Stack"
    _LOGGER_HAS_BEEN_SETUP = False

    # TODO possibly choose a different name than stack logger

    @classmethod
    def _setup_stack_logger(cls) -> None:
        logger = logging.getLogger(cls.STACK_LOGGER)
        formatter = logging.Formatter(
            "%(levelname)s:%(simtime)s ns:%(name)s:%(message)s"
        )
        syslog = logging.StreamHandler()
        syslog.setFormatter(formatter)
        syslog.addFilter(SimTimeFilter())
        logger.addHandler(syslog)
        logger.propagate = False
        cls._LOGGER_HAS_BEEN_SETUP = True

    @classmethod
    def get_stack_logger(cls, sub_logger: Optional[str] = None) -> logging.Logger:
        """Obtain the SquidASM logger.

        :param sub_logger: If used, it will return a child logger of the main SquidASM logger
        :return: The SquidASM logger
        """
        if not cls._LOGGER_HAS_BEEN_SETUP:
            cls._setup_stack_logger()
        logger = logging.getLogger(cls.STACK_LOGGER)
        if sub_logger is None:
            return logger
        else:
            return logger.getChild(sub_logger)

    @classmethod
    def set_log_level(cls, level: Union[int, str]) -> None:
        """
        Sets the log level of the SquidASM logger.
        """
        logger = cls.get_stack_logger()
        logger.setLevel(level)

    @classmethod
    def get_log_level(cls) -> int:
        """Get the log level of the SquidASM logger."""
        return cls.get_stack_logger().level

    @classmethod
    def disable_console_logging(cls):
        """Disables logging to console"""
        logger = cls.get_stack_logger()
        logger.handlers = [handler for handler in logger.handlers if not isinstance(handler, logging.StreamHandler)]

    @classmethod
    def log_to_file(cls, path: str) -> None:
        """Sets up sending the logs to an output file. Does not affect other log output methods.

        :param path: Location of output file. Overwrites existing file.
        """
        fileHandler = logging.FileHandler(path, mode="w")
        formatter = logging.Formatter(
            "%(levelname)s:%(simtime)s ns:%(name)s:%(message)s"
        )
        fileHandler.setFormatter(formatter)
        fileHandler.addFilter(SimTimeFilter())
        cls.get_stack_logger().addHandler(fileHandler)
