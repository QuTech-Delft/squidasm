from squidasm.qoala.lang.iqoala import IqoalaParser
from squidasm.qoala.runtime.config import GenericQDeviceConfig, LinkConfig
from squidasm.qoala.runtime.program import ProgramInstance
from squidasm.qoala.runtime.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import ProgramMeta


def test_run():
    program_text = """
new_value = assign_cval() : 8
my_value = add_cval_c(new_value, new_value)
run_subroutine(vec<my_value>) :
    return M0 -> m
  NETQASM_START
    set Q0 0
    qalloc Q0
    init Q0
    rot_x Q0 {my_value} 4
    meas Q0 M0
    ret_reg M0
  NETQASM_END
return_result(m)
    """
    parsed_program = IqoalaParser(program_text).parse()
    parsed_program.meta = ProgramMeta(
        name="client", parameters={}, csockets=[], epr_sockets=[], max_qubits=1
    )

    sender_stack = StackConfig(
        name="client",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )

    prog_instance = ProgramInstance(parsed_program, {}, 1, 0.0)

    cfg = StackNetworkConfig(stacks=[sender_stack], links=[])
    result = run(cfg, programs={"client": prog_instance})
    print(result)


def test_run_two_nodes_classical():
    program_text_client = """
new_value = assign_cval() : 8
send_cmsg(new_value)
    """
    program_client = IqoalaParser(program_text_client).parse()
    program_client.meta = ProgramMeta(
        name="client", parameters={}, csockets=["server"], epr_sockets=[], max_qubits=1
    )
    client_stack = StackConfig(
        name="client",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )

    program_text_server = """
new_value = assign_cval() : 8
value = recv_cmsg()
return_result(value)
    """
    program_server = IqoalaParser(program_text_server).parse()
    program_server.meta = ProgramMeta(
        name="client", parameters={}, csockets=["client"], epr_sockets=[], max_qubits=1
    )
    server_stack = StackConfig(
        name="server",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )

    prog_server_instance = ProgramInstance(program_server, {}, 1, 0.0)
    prog_client_instance = ProgramInstance(program_client, {}, 1, 0.0)

    cfg = StackNetworkConfig(stacks=[client_stack, server_stack], links=[])
    result = run(
        cfg, programs={"client": prog_client_instance, "server": prog_server_instance}
    )
    print(result)


def test_run_two_nodes_epr():
    program_text_client = """
remote_id = assign_cval() : 1
epr_sck_id = assign_cval() : 0
run_subroutine(vec<remote_id; epr_sck_id>) :
    return M0 -> m
  NETQASM_START
    set R0 0
    set R1 1
    set R2 2
    set R3 20
    set R10 10
    set C0 {remote_id}
    set C1 {epr_sck_id}
    array R10 @0
    array R1 @1
    array R3 @2
    store R0 @1[R0]
    store R0 @2[R0]
    store R1 @2[R1]
    create_epr C0 C1 R1 R2 R0
    wait_all @0[R0:R10]
    set Q0 0
    meas Q0 M0
    qfree Q0
    ret_reg M0
  NETQASM_END
return_result(m)
    """
    program_client = IqoalaParser(program_text_client).parse()
    program_client.meta = ProgramMeta(
        name="client",
        parameters={},
        csockets=["server"],
        epr_sockets=["server"],
        max_qubits=1,
    )
    client_stack = StackConfig(
        name="client",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )

    program_text_server = """
run_subroutine(vec<>) :
    return M0 -> m
  NETQASM_START
    set R0 0
    set R1 1
    set R2 2
    set R10 10
    array R10 @0
    array R1 @1
    store R0 @1[R0]
    recv_epr R0 R0 R1 R0
    wait_all @0[R0:R10]
    set Q0 0
    meas Q0 M0
    qfree Q0
    ret_reg M0
  NETQASM_END
return_result(m)
    """
    program_server = IqoalaParser(program_text_server).parse()
    program_server.meta = ProgramMeta(
        name="client",
        parameters={},
        csockets=["client"],
        epr_sockets=["client"],
        max_qubits=1,
    )
    server_stack = StackConfig(
        name="server",
        qdevice_typ="generic",
        qdevice_cfg=GenericQDeviceConfig.perfect_config(),
    )
    link = LinkConfig(
        stack1="client",
        stack2="server",
        typ="perfect",
    )

    prog_server_instance = ProgramInstance(program_server, {}, 1, 0.0)
    prog_client_instance = ProgramInstance(program_client, {}, 1, 0.0)

    cfg = StackNetworkConfig(stacks=[client_stack, server_stack], links=[link])
    result = run(
        cfg, programs={"client": prog_client_instance, "server": prog_server_instance}
    )
    print(result)


if __name__ == "__main__":
    LogManager.set_log_level("DEBUG")
    test_run()
    test_run_two_nodes_classical()
    test_run_two_nodes_epr()
