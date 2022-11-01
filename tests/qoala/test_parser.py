from squidasm.qoala.lang.iqoala import IqoalaParser
from squidasm.qoala.runtime.config import GenericQDeviceConfig, LinkConfig
from squidasm.qoala.runtime.program import ProgramInstance
from squidasm.qoala.runtime.run import run
from squidasm.sim.stack.common import LogManager
from squidasm.sim.stack.program import ProgramMeta


def test_parse():
    program_text = """
META_START
name: alice
parameters: 
csockets: 0 -> bob
epr_sockets: 
META_END
my_value = assign_cval() : 1
remote_id = assign_cval() : 0
send_cmsg(remote_id, my_value)
received_value = recv_cmsg(remote_id)
new_value = assign_cval() : 3
my_value = add_cval_c(new_value, new_value)
vec<m> = run_subroutine(vec<my_value>) : subrt1
return_result(m)
    """

    subrt_text = """"
SUBROUTINE subrt1
    params: my_value
    returns: M0 -> m
  NETQASM_START
    set Q0 0
    rot_z Q0 {my_value} 4
    meas Q0 M0
    ret_reg M0
  NETQASM_END
    """

    parsed_program = IqoalaParser(program_text).parse()

    print(parsed_program)


if __name__ == "__main__":
    test_parse()
