from src.protocol import anonymous_transmission


def main(
    log_config=None,
    sender=False,
    receiver=False,
    phi=0.,
    theta=0.,
):

    return anonymous_transmission(
        node_name='charlie',
        log_config=log_config,
        sender=sender,
        receiver=receiver,
        phi=phi,
        theta=theta,
    )


if __name__ == "__main__":
    main()
