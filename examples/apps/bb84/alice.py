import json
import random
# from time import sleep

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


def distribute_bb84_states(conn, socket, target, n):
    bit_flips = conn.new_array(n, [random.randint(0, 1) for _ in range(n)])
    basis_flips = conn.new_array(n, init_values=[random.randint(0, 1) for _ in range(n)])
    outcomes = conn.new_array(n)
    loop_register = "R0"

    def body(conn):
        q = conn.createEPR(target)[0]
        with bit_flips.get_future_index(loop_register).if_eq(1):
            q.X()
        with basis_flips.get_future_index(loop_register).if_eq(1):
            q.H()
        q.measure(array=outcomes, index=loop_register)

    conn.loop(body, stop=n, loop_register=loop_register)
    # while len(x) < n:
    #     q = conn.createEPR(target)
    #     bitflip = random.randint(0, 1)
    #     if bitflip:
    #         q.X()
    #     basisflip = random.randint(0, 1)
    #     if basisflip:
    #         q.H()

    #     x.append(q.measure())
    #     theta.append(basisflip)

    #     recvClassicalAssured(socket)

    return outcomes, basis_flips


def filter_theta(socket, x, theta):
    x_remain = []
    sendClassicalAssured(socket, theta)
    theta_hat = recvClassicalAssured(socket)
    for bit, basis, basis_hat in zip(x, theta, theta_hat):
        if basis == basis_hat:
            x_remain.append(bit)

    return x_remain


def estimate_error_rate(socket, x, num_test_bits):
    test_bits = []
    test_indices = []

    while len(test_indices) < num_test_bits and len(x) > 0:
        index = random.randint(0, len(x) - 1)
        test_bits.append(x.pop(index))
        test_indices.append(index)

    print("Alice finding {} test bits".format(num_test_bits))
    print("Alice test indices: ", test_indices)
    print("Alice test bits: ", test_bits)

    sendClassicalAssured(socket, test_indices)
    target_test_bits = recvClassicalAssured(socket)
    sendClassicalAssured(socket, test_bits)
    print("Alice target_test_bits: ", target_test_bits)

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

    socket = NetSquidSocket("Alice", "Bob")

    # socket.send('start')
    # socket.recv()
    # print("alice starting")
    # return

    # sleep(0.1)

    socket.recv()

    with NetSquidConnection("Alice") as Alice:
        x, theta = distribute_bb84_states(Alice, socket, "Bob", numbits)
    x = list(x)
    theta = list(theta)

    print("Alice x: ", x)
    print("Alice theta: ", theta)
    socket.send("fin")
    return

    m = bytes(recvClassicalAssured(socket))
    if m != b'BB84DISTACK':
        print(m)
        raise RuntimeError("Failure to distributed BB84 states")

    x_remain = filter_theta(socket, x, theta)
    print("Alice x_remain: ", x_remain)

    error_rate = estimate_error_rate(socket, x_remain, num_test_bits)
    print("Alice error rate: ", error_rate)

    if error_rate > 1:
        raise RuntimeError("Error rate of {}, aborting protocol")

    r = [random.randint(0, 1) for _ in x_remain]
    sendClassicalAssured(socket, r)
    k = extract_key(x_remain, r)

    print("Alice R: ", r)
    print("Alice key_bits: ", x_remain)
    print("Alice k: ", k)


if __name__ == '__main__':
    main()
