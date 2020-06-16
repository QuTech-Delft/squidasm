from netqasm.sdk import EPRSocket
from squidasm.sdk import NetSquidConnection

from netqasm.logging import get_netqasm_logger

logger = get_netqasm_logger()


def main(track_lines=True, app_dir=None, log_subroutines_dir=None, phi=0., theta=0.):
    epr_socket_alice = EPRSocket("alice")
    epr_socket_charlie = EPRSocket("charlie")

    alice = NetSquidConnection(
        name="bob",
        track_lines=track_lines,
        app_dir=app_dir,
        log_subroutines_dir=log_subroutines_dir,
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
