from netqasm.sdk import EPRSocket, Qubit, ThreadSocket
from netqasm.sdk.toolbox import set_qubit_state
from squidasm.sdk import NetSquidConnection

from squidasm.sim_util import get_qubit_state


def main(track_lines=True, log_subroutines_dir=None, app_dir=None, phi=0.0, theta=0.0):
    # socket for creating an EPR pair with Bob
    bob_epr = EPRSocket("bob")

    # socket for communicating classical messages with Bob
    class_socket = ThreadSocket("alice", "bob", comm_log_dir=log_subroutines_dir, app_dir=app_dir)

    # connect to the back-end
    alice = NetSquidConnection(
        name="alice",
        track_lines=track_lines,
        app_dir=app_dir,
        log_subroutines_dir=log_subroutines_dir,
        epr_sockets=[bob_epr]
    )

    with alice:
        # create one EPR pair with Alice
        epr = bob_epr.create(1)[0]

        # initialize control qubit of the distributed CNOT
        ctrl_qubit = Qubit(alice)
        set_qubit_state(ctrl_qubit, phi, theta)

        # perform a local CNOT with `epr` and measure `epr`
        ctrl_qubit.cnot(epr)
        epr_meas = epr.measure()

        # let back-end execute the quantum operations above
        alice.flush()

        # send the outcome to Bob
        class_socket.send(str(epr_meas))

        # wait for Bob's measurement outcome to undo potential entanglement
        # between his EPR half and the original control qubit
        bob_meas = class_socket.recv()
        if bob_meas == "1":
            ctrl_qubit.Z()

        # get the combined state of Alice's control and Bob's target
        dm = get_qubit_state(ctrl_qubit, reduced_dm=False)

        return {
            'epr_meas': int(epr_meas),
            'final_state': dm.tolist(),
        }
