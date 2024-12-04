
from func_hardware import (
        OperationList, Register, ControlLine,
        ALL_BITS,
    )
from fpga_hardware import (
        FPGAOperationList,
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

def main() -> None:
    ops = FPGAOperationList()
    output_pattern_from_input(ops)
    ops.generate()


if __name__ == "__main__":
    main()
