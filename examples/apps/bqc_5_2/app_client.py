from netqasm.sdk.external import Socket


def main(
    app_config={"addr": "192.168.2.215", "port": 1275, "dev": "", "debug": False},
    inputs={"alpha": 0, "beta": 0},
):
    alpha, beta, = (
        inputs["alpha"],
        inputs["beta"],
    )

    socket = Socket("client", "server")
    socket.send(str(alpha))

    m1 = int(socket.recv())
    if m1 == 1:
        beta = -beta
    socket.send(str(beta))
    return {}


if __name__ == "__main__":
    main()
