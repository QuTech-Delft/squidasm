from src.protocol import anonymous_transmission


def main(
    track_lines=True,
    log_subroutines_dir=None,
    sender=False,
    receiver=False,
    phi=0.,
    theta=0.,
):

    return anonymous_transmission(
        node_name='bob',
        log_subroutines_dir=log_subroutines_dir,
        track_lines=track_lines,
        sender=sender,
        receiver=receiver,
        phi=phi,
        theta=theta,
    )


if __name__ == "__main__":
    main()
