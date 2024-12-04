
from func_hardware import (
        OperationList, Register, ControlLine,
        ALL_BITS,
    )
from fpga_hardware import (
        FPGAOperationList,
    )
from ghdl_test import (
        ghdl_run_ops,
    )
import typing

def out_bit(ops: OperationList, r: Register) -> None:
    ops.mux(r)
    ops.add(ControlLine.SET_X_IN_TO_X_AND_CLEAR_Y_BORROW)
    if r == Register.I0:
        ops.add(ControlLine.SHIFT_Y_RIGHT, ControlLine.SHIFT_I0_RIGHT)
    else:
        ops.add(ControlLine.SHIFT_Y_RIGHT)
    ops.add(ControlLine.SEND_Y_TO_OUTPUT)

def output_pattern_from_input(ops: OperationList) -> None:
    # Load new input
    ops.add(ControlLine.LOAD_I0_FROM_INPUT)

    # prepare by zeroing X register
    ops.mux(Register.ZERO)
    ops.add(ControlLine.SET_X_IN_TO_REG_OUT)
    ops.add(ControlLine.SHIFT_X_RIGHT, ControlLine.REPEAT_FOR_ALL_BITS)

    # initial serial line state is 1
    out_bit(ops, Register.ONE)

    # hold the 1 state for a while
    ops.add(ControlLine.REPEAT_FOR_ALL_BITS)

    # start bit is 0
    out_bit(ops, Register.ZERO)
    # 8 bits
    for i in range(8):
        out_bit(ops, Register.I0)
    # stop bit is 1
    out_bit(ops, Register.ONE)

    # stay in 1 state
    ops.add(ControlLine.REPEAT_FOR_ALL_BITS)
    ops.add(ControlLine.RESTART)

def test_output_pattern_from_input() -> None:
    ops = FPGAOperationList()
    output_pattern_from_input(ops)
    in_values = [0x55, 0x99, 0xfe, 0x41, 0xa5]
    out_values = ghdl_run_ops(ops, in_values)
    assert len(out_values) == (len(in_values) * 11)
    out_bits = [bit >> (ALL_BITS - 1) for bit in out_values]
    j = 0
    for i in range(len(in_values)):
        assert out_bits[j] == 1     # initial state
        j += 1
        assert out_bits[j] == 0     # start bit
        j += 1
        for k in range(8):
            assert out_bits[j] == ((in_values[i] >> k) & 1)     # data bit
            j += 1
        assert out_bits[j] == 1     # stop bit
        j += 1


def output_pattern_from_rom(ops: OperationList, pattern: typing.List[int]) -> None:
    # input is not used
    ops.add(ControlLine.LOAD_I0_FROM_INPUT)

    # prepare by zeroing X register
    ops.mux(Register.ZERO)
    ops.add(ControlLine.SET_X_IN_TO_REG_OUT)
    ops.add(ControlLine.SHIFT_X_RIGHT, ControlLine.REPEAT_FOR_ALL_BITS)

    # initial serial line state is 1
    out_bit(ops, Register.ONE)

    # hold the 1 state for a while
    ops.add(ControlLine.REPEAT_FOR_ALL_BITS)

    for data in pattern:
        # start bit is 0
        out_bit(ops, Register.ZERO)
        # 8 bits starting at LSB
        for i in range(8):
            if (data >> i) & 1:
                out_bit(ops, Register.ONE)
            else:
                out_bit(ops, Register.ZERO)
        # stop bit is 1
        out_bit(ops, Register.ONE)

    # stay in 1 state
    ops.add(ControlLine.REPEAT_FOR_ALL_BITS)
    ops.add(ControlLine.RESTART)

def main() -> None:
    test_output_pattern_from_input()
    ops = FPGAOperationList()
    output_pattern_from_rom(ops, list(b"Hello\r\n"))
    ops.generate()
    ops = FPGAOperationList()
    output_pattern_from_input(ops)
    ops.generate()


if __name__ == "__main__":
    main()
