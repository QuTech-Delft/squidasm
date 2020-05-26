from src.protocol import anonymous_transmission


def main(track_lines=True, log_subroutines_dir=None, sender=False, value=None):

    return anonymous_transmission(
        node_name='david',
        sender=sender,
        value=value,
        log_subroutines_dir=log_subroutines_dir,
        track_lines=track_lines,
    )


if __name__ == "__main__":
    main()
