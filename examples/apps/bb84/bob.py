import json
import random

from squidasm.sdk import NetSquidConnection, NetSquidSocket


def sendClassicalAssured(socket, data):
    data = json.dumps(data)
    socket.send(data)
    while bytes(socket.recv()) != b'ACK':
        pass


def recvClassicalAssured(socket):
    data = list(socket.recv())
    data = json.loads(data)
    socket.send(b'ACK')
    return data


def receive_bb84_states(conn, socket, target, n):

    # bit_flips = conn.new_array([random.randint(0, 1) for _ in range(n)])
    basis_flips = conn.new_array(n, init_values=[random.randint(0, 1) for _ in range(n)])
    outcomes = conn.new_array(n)
    loop_register = "R0"

    def post_recv(q):
        pass

    q = conn.recvEPR(target, number=n)[0]

    def body(conn):
        with basis_flips.get_future_index(loop_register).if_eq(1):
            q.H()
        q.measure(array=outcomes, index=loop_register)

    conn.loop(body, stop=n, loop_register=loop_register)

    # while len(x) < n:
    #     q = cqc.recvQubit(target)
    #     basisflip = random.randint(0, 1)
    #     if basisflip:
    #         q.H()

    #     theta.append(basisflip)
    #     x.append(q.measure())
    #     sendClassicalAssured(socket, list(b'ACK'))

    return outcomes, basis_flips


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

    print("Bob test indices: ", test_indices)
    print("Bob test bits: ", test_bits)

    sendClassicalAssured(socket, test_bits)
    target_test_bits = recvClassicalAssured(socket)

    print("Bob target_test_bits: ", target_test_bits)
    num_error = 0
    for t1, t2 in zip(test_bits, target_test_bits):
        if t1 != t2:
            num_error += 1

    return (num_error / num_test_bits)


def extract_key(x, r):
    return (sum([xj*rj for xj, rj in zip(x, r)]) % 2)


def main():
    numbits = 100
    num_test_bits = numbits // 4

    socket = NetSquidSocket("Bob", "Alice")

    # socket.recv()
    # socket.send('ack')
    # print("bob starting")
    # return

    with NetSquidConnection("Bob") as Bob:
        x, theta = receive_bb84_states(Bob, socket, "Alice", numbits)
        Bob.flush(block=False)
        socket.send('fin')
        Bob.block()
    x = list(x)
    theta = list(theta)

    print("Bob x: ", x)
    print("Bob theta: ", theta)
    return

    sendClassicalAssured(socket, list(b'BB84DISTACK'))
    x_remain = filter_theta(socket, x, theta)
    print("Bob x_remain: ", x_remain)

    error_rate = estimate_error_rate(socket, x_remain, num_test_bits)
    print("Bob error_rate: ", error_rate)

    r = recvClassicalAssured(socket)
    print("Bob R: ", r)
    print("Bob key bits: ", x_remain)

    k = extract_key(x_remain, r)
    print("Bob k: ", k)


if __name__ == '__main__':
    main()
