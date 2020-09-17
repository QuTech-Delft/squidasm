from netqasm.sdk import EPRSocket
from squidasm.sdk import NetSquidConnection

from netqasm.logging import get_netqasm_logger

logger = get_netqasm_logger()


def main(app_config):
    epr_socket_alice = EPRSocket("alice")
    epr_socket_bob = EPRSocket("bob")

    alice = NetSquidConnection(
        app_name=app_config.app_name,
        node_name=app_config.node_name,
        log_config=app_config.log_config,
        epr_sockets=[epr_socket_alice, epr_socket_bob]
    )
    with alice:
        epr_alice = epr_socket_alice.recv()[0]
        m_alice = epr_alice.measure()

        epr_bob = epr_socket_bob.recv()[0]
        m_bob = epr_bob.measure()

    logger.info(f"charlie:  m_alice:  {m_alice}")
    logger.info(f"charlie:  m_bob:    {m_bob}")


if __name__ == "__main__":
    main()
