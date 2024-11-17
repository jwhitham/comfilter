
from settings import (UPPER_FREQUENCY,
        LOWER_FREQUENCY,
        BAUD_RATE,
        FRACTIONAL_BITS,
        NON_FRACTIONAL_BITS,
        RC_DECAY_PER_BIT,
        FILTER_WIDTH,
        SAMPLE_RATE)

ALL_BITS = FRACTIONAL_BITS + NON_FRACTIONAL_BITS
A_BITS = R_BITS = (FRACTIONAL_BITS * 2) + NON_FRACTIONAL_BITS

import enum, math, typing

class Register(enum.Enum):
    R = 1
    A = 2
    Y = 3
    O1 = 4
    O2 = 5
    X = 6
    L = 7
    I0 = 8
    I1 = 9
    I2 = 10
    ZERO = 11
    # Special codes
    L_OR_X = 15
    UNCHANGED = 0
    # Hidden registers
    LS = -1
    O1S = -2
    O2S = -3

class ControlLine(enum.Enum):
    ADD_A_TO_R = enum.auto()
    BANK_SWITCH = enum.auto()
    LOAD_I0_FROM_INPUT = enum.auto()
    SEND_Y_TO_OUTPUT = enum.auto()
    SET_X_IN_TO_X = enum.auto()
    SET_X_IN_TO_REG_OUT = enum.auto()
    SET_X_IN_TO_ABS_O1_REG_OUT = enum.auto()
    SET_Y_IN_TO_X_MINUS_REG_OUT = enum.auto()
    RESTART = enum.auto()
    ASSERT_X_IS_ABS_O1 = enum.auto()
    ASSERT_A_HIGH_ZERO = enum.auto()
    ASSERT_A_LOW_ZERO = enum.auto()
    ASSERT_R_ZERO = enum.auto()
    ASSERT_Y_IS_X_MINUS_L = enum.auto()
    SEND_O1_TO_OUTPUT = enum.auto()
    SEND_L_TO_OUTPUT = enum.auto()
    SHIFT_A_RIGHT = enum.auto()
    SHIFT_X_RIGHT = enum.auto()
    SHIFT_Y_RIGHT = enum.auto()
    SHIFT_I0_RIGHT = enum.auto()
    SHIFT_I1_RIGHT = enum.auto()
    SHIFT_I2_RIGHT = enum.auto()
    SHIFT_L_RIGHT = enum.auto()
    SHIFT_O1_RIGHT = enum.auto()
    SHIFT_O2_RIGHT = enum.auto()
    SHIFT_R_RIGHT = enum.auto()
    SET_MUX_BIT_1 = enum.auto()
    SET_MUX_BIT_2 = enum.auto()
    SET_MUX_BIT_4 = enum.auto()
    SET_MUX_BIT_8 = enum.auto()
    REPEAT_FOR_ALL_BITS = enum.auto()

SHIFT_CONTROL_LINE = {
    Register.A : ControlLine.SHIFT_A_RIGHT,
    Register.X : ControlLine.SHIFT_X_RIGHT,
    Register.Y : ControlLine.SHIFT_Y_RIGHT,
    Register.I0 : ControlLine.SHIFT_I0_RIGHT,
    Register.I1 : ControlLine.SHIFT_I1_RIGHT,
    Register.I2 : ControlLine.SHIFT_I2_RIGHT,
    Register.L : ControlLine.SHIFT_L_RIGHT,
    Register.O1 : ControlLine.SHIFT_O1_RIGHT,
    Register.O2 : ControlLine.SHIFT_O2_RIGHT,
    Register.R : ControlLine.SHIFT_R_RIGHT,
}

ControlLines = typing.Set[ControlLine]
ControlLineTree = typing.Union[ControlLines, ControlLine, typing.Sequence]

class Operation:
    def dump_code(self, fd: typing.IO) -> None:
        pass

class CommentOperation(Operation):
    def __init__(self, comment: str) -> None:
        Operation.__init__(self)
        self.comment = comment

    def dump_code(self, fd: typing.IO) -> None:
        fd.write(f"# {self.comment}\n")

class ControlOperation(Operation):
    def __init__(self, controls: ControlLines) -> None:
        Operation.__init__(self)
        self.controls = controls

    def dump_code(self, fd: typing.IO) -> None:
        fd.write(','.join([cl.name for cl in self.controls]))
        fd.write("\n")

class OperationList:
    def __init__(self) -> None:
        self.operations: typing.List[Operation] = []

    def __len__(self) -> int:
        return len(self.operations)

    def __getitem__(self, index: int) -> Operation:
        return self.operations[index]

    def add(self, *controls_tree: ControlLineTree) -> None:
        control_lines: ControlLines = set()

        def collector(cl: ControlLineTree) -> None:
            if isinstance(cl, ControlLine):
                control_lines.add(cl)
            elif isinstance(cl, list) or isinstance(cl, tuple) or isinstance(cl, set):
                for cl2 in cl:
                    collector(cl2)
            else:
                raise ValueError("Unknown ControlLine type")

        collector(controls_tree)
        self.operations.append(ControlOperation(control_lines))
   
    def comment(self, text: str) -> None:
        self.operations.append(CommentOperation(text))
   
    def __iter__(self) -> typing.Iterator[Operation]:
        for op in self.operations:
            yield op

    def dump_code(self, fd: typing.IO) -> None:
        for op in self.operations:
            op.dump_code(fd)
   
def make_fixed(value: float) -> int:
    assert abs(value) < 2.0
    ivalue = int(math.floor((value * (1 << FRACTIONAL_BITS)) + 0.5))
    if ivalue < 0:
        ivalue += 1 << ALL_BITS
    assert 0 <= ivalue < (1 << ALL_BITS)
    return ivalue

def make_float(ivalue: int) -> float:
    assert 0 <= ivalue < (1 << ALL_BITS)
    if ivalue >= (1 << (ALL_BITS - 1)):
        ivalue -= 1 << ALL_BITS
    return ivalue / float(1 << FRACTIONAL_BITS)

def get_mux_lines(source: Register) -> typing.Sequence[ControlLine]:
    if not isinstance(source, Register):
        raise ValueError("Unknown Register type")
   
    value = source.value
    if (value < 0) or (value > 15):
        raise ValueError(f"Non-selectable register {source.name}")

    control_lines = []
    if value & 1:
        control_lines.append(ControlLine.SET_MUX_BIT_1)
    if value & 2:
        control_lines.append(ControlLine.SET_MUX_BIT_2)
    if value & 4:
        control_lines.append(ControlLine.SET_MUX_BIT_4)
    if value & 8:
        control_lines.append(ControlLine.SET_MUX_BIT_8)
    return control_lines

def get_shift_line(target: Register) -> ControlLine:
    if not isinstance(target, Register):
        raise ValueError("Unknown Register type")
    return SHIFT_CONTROL_LINE[target]

def fixed_multiply(ops: OperationList, source: Register, value: float) -> None:
    ivalue = make_fixed(value)
    negative = ivalue & (1 << (ALL_BITS - 1))
    if negative:
        ivalue |= ((1 << ALL_BITS) - 1) << ALL_BITS
    # print(f"Multiplication with value {value:1.6f} fixed encoding {ivalue:04x}")

    # Clear high A bits
    ops.comment(f"Multiply {source.name} and {value:1.6f}")
    ops.add(ControlLine.SHIFT_A_RIGHT, ControlLine.REPEAT_FOR_ALL_BITS,
            get_mux_lines(Register.ZERO))

    # If negative, also clear the low bits, as these will be added during shift-in
    if negative:
        ops.add(ControlLine.SHIFT_A_RIGHT, ControlLine.REPEAT_FOR_ALL_BITS)

    ops.add(ControlLine.ASSERT_A_HIGH_ZERO)
    if negative:
        ops.add(ControlLine.ASSERT_A_LOW_ZERO)

    # Configure source
    ops.add(get_mux_lines(source))

    # Do multiplication
    for i in range(A_BITS):
        ops.add(ControlLine.SHIFT_A_RIGHT)

        ivalue = ivalue << 1
        if ivalue & (1 << A_BITS):
            ops.add(ControlLine.ADD_A_TO_R)
        
        # Don't shift ALL_BITS - leave the input register at the last bit (the sign)
        if i < (ALL_BITS - 1):
            ops.add(get_shift_line(source))

    # Final bit shifted
    ops.add(get_shift_line(source))

def move_R_to_reg(ops: OperationList, target: Register) -> None:
    # Discard low bits of R
    for i in range(FRACTIONAL_BITS):
        ops.add(ControlLine.SHIFT_R_RIGHT, ControlLine.REPEAT_FOR_ALL_BITS)

    # Move result bits of R to target
    for i in range(ALL_BITS):
        ops.add(ControlLine.SHIFT_R_RIGHT, get_shift_line(target),
                get_mux_lines(Register.R))

    # Discard high bits of R (if any)
    for i in range(R_BITS - (FRACTIONAL_BITS + ALL_BITS)):
        ops.add(ControlLine.SHIFT_R_RIGHT)

    # R should be zero again here!
    ops.add(ControlLine.ASSERT_R_ZERO)

def move_reg_to_reg(ops: OperationList, source: Register, target: Register) -> None:
    ops.comment(f"Move {source.name} to {target.name}")

    if source == Register.R:
        move_R_to_reg(ops, target)
        return

    ops.add(get_shift_line(target), get_shift_line(source), ControlLine.REPEAT_FOR_ALL_BITS,
            ControlLine.SET_X_IN_TO_REG_OUT, get_mux_lines(source))

def filter_step(ops: OperationList, a1: float, a2: float, b0: float, b2: float) -> None:
    # R should be zero here!
    ops.add(ControlLine.ASSERT_R_ZERO)

    # R += i0 * b0
    fixed_multiply(ops, Register.I0, b0)
    # R += i2 * b2
    fixed_multiply(ops, Register.I2, b2)
    # R -= o1 * a1
    fixed_multiply(ops, Register.O1, -a1)
    # R -= o2 * a2
    fixed_multiply(ops, Register.O2, -a2)

    move_reg_to_reg(ops, Register.O1, Register.O2)
    move_reg_to_reg(ops, Register.R, Register.O1)

def compute_bandpass_filter(frequency: float, width: float) -> typing.Tuple[float, float, float, float]:
    # Compute filter parameters
    w0 = (2.0 * math.pi * frequency) / SAMPLE_RATE
    alpha = math.sin(w0) / (2.0 * (frequency / width))
    b0 =   alpha
    b2 =  -alpha
    a0 =   1.0 + alpha
    a1 =  -2.0 * math.cos(w0)
    a2 =   1.0 - alpha
    b2 /= a0
    b0 /= a0
    a2 /= a0
    a1 /= a0
    return (a1, a2, b0, b2)

def bandpass_filter(ops: OperationList, frequency: float, width: float) -> None:
    ops.comment(f"Bandpass filter for {frequency:1.0f} Hz")
    filter_step(ops, *compute_bandpass_filter(frequency, width))

def rc_filter(ops: OperationList) -> None:
    bit_samples = SAMPLE_RATE / BAUD_RATE
    # This is the time constant, like k = 1 / RC for a capacitor discharging
    # Note: Level is y = exp(-kt) at time t, assuming level was 1.0 at time 0
    # The level should be reduced from 1.0 to RC_DECAY_PER_BIT during each bit
    time_constant = math.log(RC_DECAY_PER_BIT) / -bit_samples
    # Each transition from t to t+1 is a multiplication by exp(-k)
    decay = math.exp(-time_constant)

    # decay L register
    ops.comment("Decay L register")
    ops.add(ControlLine.ASSERT_R_ZERO)
    fixed_multiply(ops, Register.L, decay)
    move_reg_to_reg(ops, Register.R, Register.L)
    ops.add(ControlLine.ASSERT_R_ZERO)

    ops.comment("Max L register")
    # do:
    #   if abs(O1) >= L: L = abs(O1)
    set_X_to_abs_O1(ops)
    set_Y_to_X_minus_reg(ops, Register.L)
    ops.add(ControlLine.ASSERT_X_IS_ABS_O1)
    ops.add(ControlLine.ASSERT_Y_IS_X_MINUS_L)
    move_X_to_L_if_Y_is_not_negative(ops)

    ops.add(ControlLine.ASSERT_X_IS_ABS_O1)
    ops.add(ControlLine.ASSERT_R_ZERO)

def set_X_to_abs_O1(ops: OperationList) -> None:
    # Operation: X = abs(O1)
    ops.add(ControlLine.SET_X_IN_TO_ABS_O1_REG_OUT, get_mux_lines(Register.O1))
    ops.add(ControlLine.SHIFT_X_RIGHT, ControlLine.SHIFT_O1_RIGHT, ControlLine.REPEAT_FOR_ALL_BITS)

    ops.add(ControlLine.ASSERT_X_IS_ABS_O1)

def set_Y_to_X_minus_reg(ops: OperationList, source: Register) -> None:
    # Operation: Y = X - reg
    ops.add(ControlLine.SET_X_IN_TO_X, ControlLine.SET_Y_IN_TO_X_MINUS_REG_OUT,
            get_mux_lines(source))
    ops.add(ControlLine.SHIFT_X_RIGHT, ControlLine.SHIFT_Y_RIGHT,
            get_shift_line(source), ControlLine.REPEAT_FOR_ALL_BITS)

def move_X_to_L_if_Y_is_not_negative(ops: OperationList) -> None:
    # if Y is non-negative, then X >= L: so, set L = X
    # if Y is negative, then X < L: so, set X = X
    ops.add(ControlLine.SHIFT_L_RIGHT, ControlLine.SHIFT_X_RIGHT,
            ControlLine.REPEAT_FOR_ALL_BITS,
            get_mux_lines(Register.L_OR_X), ControlLine.SET_X_IN_TO_X)

def demodulator(ops: OperationList) -> None:
    # Load new input
    ops.add(ControlLine.LOAD_I0_FROM_INPUT)

    # Apply both filters
    # Use first bank for O1, O2, L
    bandpass_filter(ops, UPPER_FREQUENCY, FILTER_WIDTH)
    rc_filter(ops)
    ops.add(ControlLine.SEND_O1_TO_OUTPUT, ControlLine.SEND_L_TO_OUTPUT)

    # Use second bank for O1S, O2S, LS
    ops.add(ControlLine.BANK_SWITCH)
    bandpass_filter(ops, LOWER_FREQUENCY, FILTER_WIDTH)
    rc_filter(ops)
    ops.add(ControlLine.SEND_O1_TO_OUTPUT, ControlLine.SEND_L_TO_OUTPUT)

    # Operation: X = LS
    move_reg_to_reg(ops, Register.L, Register.X)

    # Back to first bank
    ops.add(ControlLine.BANK_SWITCH)

    # Operation: Y = X - L
    set_Y_to_X_minus_reg(ops, Register.L)
    ops.add(ControlLine.ASSERT_Y_IS_X_MINUS_L)

    # if Y is non-negative, then LS >= L: so, lower frequency signal is stronger
    # if Y is negative, then LS < L: so, upper frequency signal is stronger
    ops.add(ControlLine.SEND_Y_TO_OUTPUT)

    # ready for next input
    move_reg_to_reg(ops, Register.I1, Register.I2)
    move_reg_to_reg(ops, Register.I0, Register.I1)
    ops.add(ControlLine.RESTART)

def multiply_accumulate(ops: OperationList, test_values: typing.List[float]) -> None:
    # For testing: multiply-accumulate
    ops.add(ControlLine.ASSERT_R_ZERO)

    # Multiply and add repeatedly
    for test_value in test_values:
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)
        fixed_multiply(ops, Register.I0, test_value)

    move_reg_to_reg(ops, Register.R, Register.O1)

    # One output
    ops.add(ControlLine.SEND_O1_TO_OUTPUT)

def multiply_accumulate_via_regs(ops: OperationList, test_values: typing.List[float]) -> None:
    # For testing: multiply-accumulate but via other registers
    ops.add(ControlLine.ASSERT_R_ZERO)

    # Multiply and add repeatedly
    for test_value in test_values:
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)
        # multiply from I2, via I1
        move_reg_to_reg(ops, Register.I0, Register.I1)
        move_reg_to_reg(ops, Register.I1, Register.I2)
        fixed_multiply(ops, Register.I2, test_value)
        # move out of R then back into it, via O registers
        move_reg_to_reg(ops, Register.R, Register.O1)
        move_reg_to_reg(ops, Register.O1, Register.O2)
        fixed_multiply(ops, Register.O2, 1.0)

    # One output
    ops.add(ControlLine.SEND_O1_TO_OUTPUT)

def main() -> None:
    ops = OperationList()
    demodulator(ops)
    with open("generated/demodulator", "wt") as fd:
        ops.dump_code(fd)
    #with open("generated/map", "wt") as fd:
    #    ops.dump_map(fd)
    #with open("generated/frequency", "wt") as fd:
    #    ops.dump_frequency(fd)

        
if __name__ == "__main__":
    main()
