
from hardware import (
        OperationList, Register, ControlLine,
        ALL_BITS,
    )
from fpga_hardware import (
        FPGAOperationList,
    )
from fpga_test import (
        fpga_run_ops,
    )
import typing

NUM_TEST_BITS = 10

def output_pattern_from_input(ops: OperationList) -> None:
    # Load new input
    ops.add(ControlLine.LOAD_I0_FROM_INPUT)

    for i in range(NUM_TEST_BITS):
        # output LSB[I0] and shift I0 right
        ops.mux(Register.I0)
        ops.add(ControlLine.SET_X_IN_TO_X_AND_CLEAR_Y_BORROW)
        ops.add(ControlLine.SHIFT_Y_RIGHT, ControlLine.SHIFT_I0_RIGHT)
        ops.add(ControlLine.SEND_Y_TO_OUTPUT)

    ops.add(ControlLine.RESTART)

def test_output_pattern_from_input() -> None:
    ops = FPGAOperationList()
    output_pattern_from_input(ops)
    in_values = [0x155, 0x299, 0x0fe]
    out_values = fpga_run_ops(ops, in_values)
    assert len(out_values) == (len(in_values) * NUM_TEST_BITS)
    for i in range(len(in_values)):
        for j in range(NUM_TEST_BITS):
            actual = out_values[j + (i * NUM_TEST_BITS)] >> (ALL_BITS - 1)
            expect = (in_values[i] >> j) & 1
            assert actual == expect

def output_pattern_from_rom(ops: OperationList, pattern: typing.List[int]) -> None:
    ops.add(ControlLine.LOAD_I0_FROM_INPUT)
    for data in pattern:
        for i in range(NUM_TEST_BITS):
            if (data >> i) & 1:
                ops.mux(Register.ONE)
            else:
                ops.mux(Register.ZERO)
            ops.add(ControlLine.SET_X_IN_TO_X_AND_CLEAR_Y_BORROW)
            ops.add(ControlLine.SHIFT_Y_RIGHT)
            ops.add(ControlLine.SEND_Y_TO_OUTPUT)

    ops.add(ControlLine.RESTART)

def test_output_pattern_from_rom() -> None:
    ops = FPGAOperationList()
    pattern = [0x155, 0x299, 0x0fe]
    output_pattern_from_rom(ops, pattern)
    out_values = fpga_run_ops(ops, [1])
    assert len(out_values) == (len(pattern) * NUM_TEST_BITS)
    for i in range(len(pattern)):
        for j in range(NUM_TEST_BITS):
            actual = out_values[j + (i * NUM_TEST_BITS)] >> (ALL_BITS - 1)
            expect = (pattern[i] >> j) & 1
            assert actual == expect

class CounterROMTest(FPGAOperationList):
    def get_memory_image(self) -> bytes:
        return bytes([x & 0xff for x in range(512)])

def main() -> None:
    ops = FPGAOperationList()
    output_pattern_from_rom(ops, [0x155, 0x299, 0x0fe])
    ops.generate()
    test_output_pattern_from_input()
    test_output_pattern_from_rom()
    CounterROMTest().generate()


if __name__ == "__main__":
    main()
