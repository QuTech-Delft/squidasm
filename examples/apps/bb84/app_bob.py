import json

from qlink_interface import EPRType

from netqasm.logging import get_netqasm_logger
from netqasm.sdk import ThreadSocket as Socket
from netqasm.sdk import EPRSocket
from squidasm.sdk import NetSquidConnection

logger = get_netqasm_logger()


def sendClassicalAssured(socket, data):
    data = json.dumps(data)
    socket.send(data)
    while socket.recv() != 'ACK':
        pass


def recvClassicalAssured(socket):
    data = socket.recv()
    data = json.loads(data)
    socket.send('ACK')
    return data


def receive_bb84_states(epr_socket, socket, target, n):
    bit_flips = []
    basis_flips = []

    ent_infos = epr_socket.recv(number=n, tp=EPRType.M)
    for ent_info in ent_infos:
        bit_flips.append(ent_info.measurement_outcome)
        basis_flips.append(ent_info.measurement_basis)
    return bit_flips, basis_flips


def filter_theta(socket, x, theta):
    x_remain = []
    theta_hat = recvClassicalAssured(socket)
    sendClassicalAssured(socket, theta)
    for bit, basis, basis_hat in zip(x, theta, theta_hat):
        if basis == basis_hat:
            x_remain.append(bit)

    return x_remain


def estimate_error_rate(socket, x, num_test_bits):
    test_bits = []
    test_indices = recvClassicalAssured(socket)
    for index in test_indices:
        test_bits.append(x.pop(index))

    logger.info(f"bob test indices: {test_indices}")
    logger.info(f"bob test bits: {test_bits}")

    sendClassicalAssured(socket, test_bits)
    target_test_bits = recvClassicalAssured(socket)

    logger.info(f"bob target_test_bits: {target_test_bits}")
    num_error = 0
    for t1, t2 in zip(test_bits, target_test_bits):
        if t1 != t2:
            num_error += 1

    return (num_error / num_test_bits)


def extract_key(x, r):
    return (sum([xj*rj for xj, rj in zip(x, r)]) % 2)


def main(log_config=None, num_bits=100):
    num_test_bits = num_bits // 4

    # Socket for classical communication
    socket = Socket("bob", "alice", log_config=log_config)
    # Socket for EPR generation
    epr_socket = EPRSocket("alice")

    bob = NetSquidConnection(
        "bob",
        log_config=log_config,
        epr_sockets=[epr_socket],
    )
    with bob:
        bit_flips, basis_flips = receive_bb84_states(epr_socket, socket, "alice", num_bits)

    x = [int(b) for b in bit_flips]
    theta = [int(b) for b in basis_flips]

    logger.info(f"bob x: {x}")
    logger.info(f"bob theta: {theta}")

    sendClassicalAssured(socket, 'BB84DISTACK')
    x_remain = filter_theta(socket, x, theta)

    error_rate = estimate_error_rate(socket, x_remain, num_test_bits)
    logger.info(f"bob error_rate: {error_rate}")

    r = recvClassicalAssured(socket)
    logger.info(f"bob R: {r}")
    logger.info(f"bob raw key: {x_remain}")

    k = extract_key(x_remain, r)
    logger.info(f"bob key: {k}")

    return {
        'raw_key': x_remain,
        'key': k,
    }


if __name__ == '__main__':
    main()