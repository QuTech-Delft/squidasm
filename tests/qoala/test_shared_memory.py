from squidasm.qoala.sim.memory import SharedMemory


def test_register_setup():
    mem = SharedMemory(0)
    print(mem._registers)

    mem.set_reg_value("R0", 42)
    print(mem.get_reg_value("R0"))

    print(mem._registers)


if __name__ == "__main__":
    test_register_setup()
