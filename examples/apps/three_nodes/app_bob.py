from netqasm.sdk import EPRSocket
from squidasm.sdk import NetSquidConnection

from netqasm.logging import get_netqasm_logger

logger = get_netqasm_logger()


def main(log_config=None):
    epr_socket_alice = EPRSocket("alice")
    epr_socket_charlie = EPRSocket("charlie")

    alice = NetSquidConnection(
        name="bob",
        log_config=log_config,
        epr_sockets=[epr_socket_alice, epr_socket_charlie]
    )
    with alice:
        epr_alice = epr_socket_alice.recv()[0]
        m_alice = epr_alice.measure()

        epr_charlie = epr_socket_charlie.create()[0]
        m_charlie = epr_charlie.measure()

    logger.info(f"bob:      m_alice:  {m_alice}")
    logger.info(f"bob:      m_charlie:{m_charlie}")


if __name__ == "__main__":
    main()
