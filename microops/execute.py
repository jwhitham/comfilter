
from hardware import (
        ControlLine, ControlLines,
        OperationList, Register, ControlOperation,
        DebugOperation, Debug, MuxOperation, MuxCode,
        SHIFT_CONTROL_LINE,
        ALL_BITS, A_BITS, R_BITS,
    )
from filtersetup import (
        make_float,
    )
import enum, typing

class XSelect(enum.Enum):
    PASSTHROUGH_X = 0
    PASSTHROUGH_REG_OUT = 1
    NEGATE_REG_OUT = 2
    BORROW_REG_OUT = 3

class YSelect(enum.Enum):
    X_MINUS_REG_OUT = 0
    BORROW_X_MINUS_REG_OUT = 1

class SpecialRegister(enum.Enum):
    X_SELECT = -100
    Y_BORROW = -101
    MUX_SELECT = -102
    REPEAT_COUNTER = -103

class NextStep(enum.Enum):
    NEXT = enum.auto()
    REPEAT = enum.auto()
    RESTART = enum.auto()

RegFile = typing.Dict[typing.Union[Register, SpecialRegister], int]
NUMBER_TO_REGISTER = {r.value: r for r in Register}

def execute_control(controls: ControlLines, inf: RegFile) -> typing.Tuple[NextStep, RegFile]:
    outf = dict(inf)
    mux_select = inf[SpecialRegister.MUX_SELECT]
    reg_out = inf[NUMBER_TO_REGISTER[mux_select]] & 1

    if ControlLine.ADD_A_TO_R in controls:
        outf[Register.R] = (inf[Register.R] + inf[Register.A]) & (1 << R_BITS) - 1
    if ControlLine.SET_X_IN_TO_X in controls:
        outf[SpecialRegister.X_SELECT] = XSelect.PASSTHROUGH_X.value
    if ControlLine.SET_X_IN_TO_REG_OUT in controls:
        outf[SpecialRegister.X_SELECT] = XSelect.PASSTHROUGH_REG_OUT.value
    if ControlLine.SET_X_IN_TO_ABS_O1_REG_OUT in controls:
        if inf[Register.O1] >> (ALL_BITS - 1):
            outf[SpecialRegister.X_SELECT] = XSelect.NEGATE_REG_OUT.value
        else:
            outf[SpecialRegister.X_SELECT] = XSelect.PASSTHROUGH_REG_OUT.value
    if ControlLine.SET_Y_IN_TO_X_MINUS_REG_OUT in controls:
        outf[SpecialRegister.Y_BORROW] = YSelect.X_MINUS_REG_OUT.value

    # Shift for generic registers
    for (reg, cl) in SHIFT_CONTROL_LINE.items():
        if cl in controls:
            outf[reg] = (inf[reg] | (reg_out << ALL_BITS)) >> 1

    # Shift for some registers is special
    if ControlLine.SHIFT_R_RIGHT in controls:
        # R register always shift in zero
        outf[Register.R] = inf[Register.R] >> 1
    if ControlLine.SHIFT_A_RIGHT in controls:
        # A register is wider
        outf[Register.A] = (inf[Register.A] | (reg_out << A_BITS)) >> 1
    if ControlLine.SHIFT_X_RIGHT in controls:
        # X register has a special function input (passthrough/abs)
        if inf[SpecialRegister.X_SELECT] == XSelect.PASSTHROUGH_REG_OUT.value:
            x_in = reg_out
        elif inf[SpecialRegister.X_SELECT] == XSelect.PASSTHROUGH_X.value:
            x_in = inf[Register.X] & 1
        elif inf[SpecialRegister.X_SELECT] == XSelect.NEGATE_REG_OUT.value:
            x_in = 4 - reg_out
            if x_in & 2:
                outf[SpecialRegister.X_SELECT] = XSelect.BORROW_REG_OUT.value
        elif inf[SpecialRegister.X_SELECT] == XSelect.BORROW_REG_OUT.value:
            x_in = 3 - reg_out
            if not (x_in & 2):
                outf[SpecialRegister.X_SELECT] = XSelect.NEGATE_REG_OUT.value
        else:
            assert False
        outf[Register.X] = (inf[Register.X] | ((x_in & 1) << ALL_BITS)) >> 1
    if ControlLine.SHIFT_Y_RIGHT in controls:
        # Y register has a special function input (subtract)
        (y_in, outf[SpecialRegister.Y_BORROW]) = subtractor(
            inf[Register.X] & 1,
            reg_out & 1,
            inf[SpecialRegister.Y_BORROW] & 1)
        outf[Register.Y] = (inf[Register.Y] | ((y_in & 1) << ALL_BITS)) >> 1
    if ControlLine.REPEAT_FOR_ALL_BITS in controls:
        outf[SpecialRegister.REPEAT_COUNTER] = (inf[SpecialRegister.REPEAT_COUNTER] + 1) % ALL_BITS
        if outf[SpecialRegister.REPEAT_COUNTER] != 0:
            return (NextStep.REPEAT, outf)

    return (NextStep.NEXT, outf)

def subtractor(x_in: int, y_in: int, b_in) -> typing.Tuple[int, int]:
    d_out = x_in ^ y_in ^ b_in
    b_out = int(x_in < (y_in + b_in))
    return (d_out, b_out)

def execute_mux(source: MuxCode, inf: RegFile,
        reverse_in_values: typing.List[int],
        out_values: typing.List[int]) -> typing.Tuple[NextStep, RegFile]:
    outf = dict(inf)
    if source == MuxCode.L_OR_X:
        if inf[Register.Y] >> (ALL_BITS - 1):
            outf[SpecialRegister.MUX_SELECT] = Register.L.value # Y negative, use L
        else:
            outf[SpecialRegister.MUX_SELECT] = Register.X.value # Y non-negative, use X
    elif source == MuxCode.RESTART:
        return (NextStep.RESTART, outf)
    elif source == MuxCode.BANK_SWITCH:
        outf[Register.L], outf[Register.LS] = inf[Register.LS], inf[Register.L]
        outf[Register.O1], outf[Register.O1S] = inf[Register.O1S], inf[Register.O1]
        outf[Register.O2], outf[Register.O2S] = inf[Register.O2S], inf[Register.O2]
    elif source == MuxCode.LOAD_I0_FROM_INPUT:
        outf[Register.I0] = reverse_in_values.pop()
    elif source == MuxCode.SEND_Y_TO_OUTPUT:
        out_values.append(inf[Register.Y])
    else:
        assert source.value in NUMBER_TO_REGISTER, source.value
        outf[SpecialRegister.MUX_SELECT] = source.value

    return (NextStep.NEXT, outf)

def execute_debug(debug: Debug, inf: RegFile,
        out_values: typing.List[int]) -> None:
    if debug == Debug.ASSERT_X_IS_ABS_O1:
        assert abs(make_float(inf[Register.O1])) == make_float(inf[Register.X])
    if debug == Debug.ASSERT_A_HIGH_ZERO:
        assert (inf[Register.A] >> ALL_BITS) == 0
    if debug == Debug.ASSERT_A_LOW_ZERO:
        assert (inf[Register.A] & ((1 << ALL_BITS) - 1)) == 0
    if debug == Debug.ASSERT_R_ZERO:
        assert inf[Register.R] == 0
    if debug == Debug.ASSERT_Y_IS_X_MINUS_L:
        assert inf[Register.Y] == ((inf[Register.X] - inf[Register.L]) & ((1 << ALL_BITS) - 1))
    if debug == Debug.SEND_O1_TO_OUTPUT:
        out_values.append(inf[Register.O1])
    if debug == Debug.SEND_L_TO_OUTPUT:
        out_values.append(inf[Register.L])

def run_ops(ops: OperationList, in_values: typing.List[int], debug: bool) -> typing.List[int]:
    reg_file: RegFile = {}
    for gr in Register:
        reg_file[gr] = 0
    for sr in SpecialRegister:
        reg_file[sr] = 0
    op_index = 0
    out_values: typing.List[int] = []
    reverse_in_values = list(reversed(in_values))
    while op_index < len(ops):
        op = ops[op_index]
        next_step = NextStep.NEXT
        if isinstance(op, ControlOperation):
            if debug:
                print(f"  op: {op_index} {op}")
            previous_reg_file = reg_file
            (next_step, reg_file) = execute_control(op.controls, previous_reg_file)
            if debug:
                for r in reg_file.keys():
                    if reg_file[r] != previous_reg_file[r]:
                        print(f"   reg {r.name}: {previous_reg_file[r]:08x} -> {reg_file[r]:08x}")

        elif isinstance(op, MuxOperation):
            if debug:
                print(f"  op: {op_index} {op}")
            previous_reg_file = reg_file
            (next_step, reg_file) = execute_mux(op.source, previous_reg_file, reverse_in_values, out_values)
        elif isinstance(op, DebugOperation):
            if debug:
                print(f" {op}")
            execute_debug(op.debug, reg_file, out_values)
        else:
            if debug:
                print(f" {op}")

        if next_step == NextStep.RESTART:
            if len(reverse_in_values) == 0:
                return out_values
            else:
                op_index = 0
        elif next_step == NextStep.NEXT:
            op_index += 1

    # Gone over the end of the program
    raise Exception("Program must end in RESTART")
