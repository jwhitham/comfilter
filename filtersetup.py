
from settings import (UPPER_FREQUENCY,
        LOWER_FREQUENCY,
        BAUD_RATE,
        FRACTIONAL_BITS,
        NON_FRACTIONAL_BITS,
        RC_DECAY_PER_BIT,
        FILTER_WIDTH,
        SAMPLE_RATE)

SYSTEM_CLOCK_FREQUENCY = 96e6
ALL_BITS = FRACTIONAL_BITS + NON_FRACTIONAL_BITS
A_BITS = R_BITS = (FRACTIONAL_BITS * 2) + NON_FRACTIONAL_BITS

import enum, math, typing

class Register(enum.Enum):
    A = enum.auto()
    A_SIGN = enum.auto()
    ABSR = enum.auto()
    I0 = enum.auto()
    I1 = enum.auto()
    I2 = enum.auto()
    L = enum.auto()
    LS = enum.auto()
    O1 = enum.auto()
    O2 = enum.auto()
    O1S = enum.auto()
    O2S = enum.auto()
    R = enum.auto()
    ZERO = enum.auto()

class Operation(enum.Enum):
    ADD_A_TO_R = enum.auto()
    ASSERT_ABSR_IS_ABS_O1 = enum.auto()
    ASSERT_A_HIGH_ZERO = enum.auto()
    ASSERT_A_LOW_ZERO = enum.auto()
    ASSERT_R_ZERO = enum.auto()
    BANK_SWITCH = enum.auto()
    LOAD_I0_FROM_INPUT = enum.auto()
    SEND_O1_TO_OUTPUT = enum.auto()
    SEND_L_TO_OUTPUT = enum.auto()
    SEND_R_SIGN_TO_OUTPUT = enum.auto()
    SET_REG_OUT_TO_I0 = enum.auto()
    SET_REG_OUT_TO_I1 = enum.auto()
    SET_REG_OUT_TO_I2 = enum.auto()
    SET_REG_OUT_TO_O1 = enum.auto()
    SET_REG_OUT_TO_O2 = enum.auto()
    SET_REG_OUT_TO_ZERO = enum.auto()
    SET_REG_OUT_TO_A_SIGN = enum.auto()
    SET_REG_OUT_TO_R = enum.auto()
    SET_REG_OUT_TO_L_OR_ABSR = enum.auto()
    SET_REG_OUT_TO_L = enum.auto()
    SET_REG_OUT_TO_ABSR = enum.auto()
    SETUP_ABSR_INPUT = enum.auto()
    SHIFT_A_RIGHT = enum.auto()
    SHIFT_ABSR_RIGHT = enum.auto()
    SHIFT_I0_RIGHT = enum.auto()
    SHIFT_I1_RIGHT = enum.auto()
    SHIFT_I2_RIGHT = enum.auto()
    SHIFT_O1_RIGHT = enum.auto()
    SHIFT_O2_RIGHT = enum.auto()
    SHIFT_L_RIGHT = enum.auto()
    SHIFT_R_RIGHT = enum.auto()
    RESTART = enum.auto()
    DEBUG_PREFIX = enum.auto()
    EXTENDED_PREFIX = enum.auto()

SET_REG_OUT_TABLE = {
    # Operation.SET_REG_OUT_TO_A : Register.A,
    Operation.SET_REG_OUT_TO_A_SIGN : Register.A_SIGN,
    Operation.SET_REG_OUT_TO_ABSR : Register.ABSR,
    Operation.SET_REG_OUT_TO_I0 : Register.I0,
    Operation.SET_REG_OUT_TO_I1 : Register.I1,
    Operation.SET_REG_OUT_TO_I2 : Register.I2,
    Operation.SET_REG_OUT_TO_L : Register.L,
    Operation.SET_REG_OUT_TO_O1 : Register.O1,
    Operation.SET_REG_OUT_TO_O2 : Register.O2,
    Operation.SET_REG_OUT_TO_R : Register.R,
    Operation.SET_REG_OUT_TO_ZERO : Register.ZERO,
}

SHIFT_TABLE = {
    Operation.SHIFT_A_RIGHT : Register.A,
    Operation.SHIFT_ABSR_RIGHT : Register.ABSR,
    Operation.SHIFT_I0_RIGHT : Register.I0,
    Operation.SHIFT_I1_RIGHT : Register.I1,
    Operation.SHIFT_I2_RIGHT : Register.I2,
    Operation.SHIFT_L_RIGHT : Register.L,
    Operation.SHIFT_O1_RIGHT : Register.O1,
    Operation.SHIFT_O2_RIGHT : Register.O2,
    Operation.SHIFT_R_RIGHT : Register.R,
    # Operation.SHIFT_ZERO_RIGHT : Register.ZERO,
}

NO_PREFIX_ENCODING_TABLE = {
    Operation.SHIFT_I0_RIGHT: 0,
    Operation.SHIFT_I1_RIGHT: 1,
    Operation.SHIFT_I2_RIGHT: 2,
    Operation.SHIFT_ABSR_RIGHT: 3,
    Operation.SHIFT_L_RIGHT: 4,
    Operation.SHIFT_O1_RIGHT: 5,
    Operation.SHIFT_O2_RIGHT: 6,
    Operation.ADD_A_TO_R: 7,
    Operation.SHIFT_R_RIGHT: 8,
    Operation.SHIFT_A_RIGHT: 9,
    Operation.SET_REG_OUT_TO_A_SIGN: 10,
    Operation.SET_REG_OUT_TO_ZERO : 11,
    Operation.SETUP_ABSR_INPUT: 12,
    Operation.SET_REG_OUT_TO_L: 13,
    Operation.DEBUG_PREFIX: 14,
    Operation.EXTENDED_PREFIX: 15
}

DEBUG_PREFIX_ENCODING_TABLE = {
    Operation.SEND_L_TO_OUTPUT: 0,
    Operation.SEND_O1_TO_OUTPUT: 1,
    Operation.ASSERT_ABSR_IS_ABS_O1: 2,
    Operation.ASSERT_A_HIGH_ZERO: 3,
    Operation.ASSERT_R_ZERO: 4,
    Operation.ASSERT_A_LOW_ZERO: 5,
}

EXTENDED_PREFIX_ENCODING_TABLE = {
    Operation.SET_REG_OUT_TO_I0: 0,
    Operation.SET_REG_OUT_TO_I1: 1,
    Operation.SET_REG_OUT_TO_I2: 2,
    Operation.SET_REG_OUT_TO_ABSR: 3,
    Operation.SET_REG_OUT_TO_O1: 5,
    Operation.SET_REG_OUT_TO_O2: 6,
    Operation.SET_REG_OUT_TO_R: 8,
    Operation.LOAD_I0_FROM_INPUT: 10,
    Operation.SEND_R_SIGN_TO_OUTPUT: 11,
    Operation.RESTART: 12,
    Operation.BANK_SWITCH: 13,
    Operation.SET_REG_OUT_TO_L_OR_ABSR: 14,
}
  
class OperationList:
    def __init__(self) -> None:
        self.encoded: typing.List[int] = []
        self.no_prefix_decoder = { value: op for (op, value) in NO_PREFIX_ENCODING_TABLE.items() }
        self.debug_prefix_decoder = { value: op for (op, value) in DEBUG_PREFIX_ENCODING_TABLE.items() }
        self.extended_prefix_decoder = { value: op for (op, value) in EXTENDED_PREFIX_ENCODING_TABLE.items() }
        self.op_count = 0

    def size(self) -> int:
        return len(self.encoded)

    def __len__(self) -> int:
        return self.op_count

    def append(self, op: Operation) -> None:
        self.op_count += 1
        if op in NO_PREFIX_ENCODING_TABLE:
            self.encoded.append(NO_PREFIX_ENCODING_TABLE[op])
        elif op in DEBUG_PREFIX_ENCODING_TABLE:
            self.encoded.append(NO_PREFIX_ENCODING_TABLE[Operation.DEBUG_PREFIX])
            self.encoded.append(DEBUG_PREFIX_ENCODING_TABLE[op])
        elif op in EXTENDED_PREFIX_ENCODING_TABLE:
            self.encoded.append(NO_PREFIX_ENCODING_TABLE[Operation.EXTENDED_PREFIX])
            self.encoded.append(EXTENDED_PREFIX_ENCODING_TABLE[op])
        else:
            raise Exception("No encoding for {op.name}")
   
    def __iter__(self) -> typing.Iterator[Operation]:
        decoder = self.no_prefix_decoder
        for enc in self.encoded:
            op = decoder[enc]
            if op == Operation.DEBUG_PREFIX:
                decoder = self.debug_prefix_decoder
            elif op == Operation.EXTENDED_PREFIX:
                decoder = self.extended_prefix_decoder
            else:
                yield op
                decoder = self.no_prefix_decoder

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

def set_output_register(ops: OperationList, source: Register) -> None:
    for (op, reg) in SET_REG_OUT_TABLE.items():
        if reg == source:
            ops.append(op)
            return

    raise ValueError(f"Register {source.name} is not in SET_REG_OUT_TABLE")

def shift_register(ops: OperationList, target: Register) -> None:
    for (op, reg) in SHIFT_TABLE.items():
        if reg == target:
            ops.append(op)
            return

    raise ValueError(f"Register {target.name} is not in SHIFT_TABLE")

def fixed_multiply(ops: OperationList, source: Register, value: float) -> None:
    ivalue = make_fixed(value)
    negative = ivalue & (1 << (ALL_BITS - 1))
    if negative:
        ivalue |= ((1 << ALL_BITS) - 1) << ALL_BITS
    # print(f"Multiplication with value {value:1.6f} fixed encoding {ivalue:04x}")

    # Clear high A bits
    ops.append(Operation.SET_REG_OUT_TO_ZERO)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_A_RIGHT)
    ops.append(Operation.ASSERT_A_HIGH_ZERO)

    # If negative, also clear the low bits, as these will be added during shift-in
    if negative:
        for i in range(A_BITS - ALL_BITS):
            ops.append(Operation.SHIFT_A_RIGHT)
        ops.append(Operation.ASSERT_A_LOW_ZERO)

    # Configure source
    set_output_register(ops, source)

    # Do multiplication
    for i in range(A_BITS):
        ops.append(Operation.SHIFT_A_RIGHT)
        ivalue = ivalue << 1
        if ivalue & (1 << A_BITS):
            ops.append(Operation.ADD_A_TO_R)
            
        if i < ALL_BITS:
            shift_register(ops, source)

        if i == (ALL_BITS - 1):
            ops.append(Operation.SET_REG_OUT_TO_A_SIGN)

def move_R_to_O1_and_ABSR(ops: OperationList) -> None:
    # Setup ABSR register by looking at the sign of R
    # If R is negative, input for ABSR is negated
    ops.append(Operation.SETUP_ABSR_INPUT)

    # Discard low bits of R
    for i in range(FRACTIONAL_BITS):
        ops.append(Operation.SHIFT_R_RIGHT)

    # Move result bits of R to O1 and ABSR
    ops.append(Operation.SET_REG_OUT_TO_R)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_O1_RIGHT)
        ops.append(Operation.SHIFT_ABSR_RIGHT)
        ops.append(Operation.SHIFT_R_RIGHT)

    # Discard high bits of R (if any)
    for i in range(R_BITS - (FRACTIONAL_BITS + ALL_BITS)):
        ops.append(Operation.SHIFT_R_RIGHT)

    # R should be zero again here!
    ops.append(Operation.ASSERT_R_ZERO)
    ops.append(Operation.ASSERT_ABSR_IS_ABS_O1)

def move_R_to_L(ops: OperationList) -> None:
    # Discard low bits of R
    for i in range(FRACTIONAL_BITS):
        ops.append(Operation.SHIFT_R_RIGHT)

    # Move result bits of R to L
    ops.append(Operation.SET_REG_OUT_TO_R)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_L_RIGHT)
        ops.append(Operation.SHIFT_R_RIGHT)

    # Discard high bits of R (if any)
    for i in range(R_BITS - (FRACTIONAL_BITS + ALL_BITS)):
        ops.append(Operation.SHIFT_R_RIGHT)

    # R should be zero again here!
    ops.append(Operation.ASSERT_R_ZERO)

def move_O1_to_O2(ops: OperationList) -> None:
    ops.append(Operation.SET_REG_OUT_TO_O1)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_O2_RIGHT)
        ops.append(Operation.SHIFT_O1_RIGHT)

def move_I1_to_I2(ops: OperationList) -> None:
    ops.append(Operation.SET_REG_OUT_TO_I1)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_I2_RIGHT)
        ops.append(Operation.SHIFT_I1_RIGHT)

def move_I0_to_I1(ops: OperationList) -> None:
    ops.append(Operation.SET_REG_OUT_TO_I0)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_I1_RIGHT)
        ops.append(Operation.SHIFT_I0_RIGHT)

def filter_step(ops: OperationList, a1: float, a2: float, b0: float, b2: float) -> None:
    # R should be zero here!
    ops.append(Operation.ASSERT_R_ZERO)

    # R += i0 * b0
    fixed_multiply(ops, Register.I0, b0)
    # R += i2 * b2
    fixed_multiply(ops, Register.I2, b2)
    # R -= o1 * a1
    fixed_multiply(ops, Register.O1, -a1)
    # R -= o2 * a2
    fixed_multiply(ops, Register.O2, -a2)

    move_O1_to_O2(ops)
    move_R_to_O1_and_ABSR(ops)

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
    ops.append(Operation.ASSERT_R_ZERO)
    fixed_multiply(ops, Register.L, decay)
    move_R_to_L(ops)
    ops.append(Operation.ASSERT_R_ZERO)

    # we'll be shifting back into ABSR, so make sure that there won't be any negation
    ops.append(Operation.SETUP_ABSR_INPUT)

    # compare L and ABSR
    fixed_multiply(ops, Register.L, 1.0)
    fixed_multiply(ops, Register.ABSR, -1.0)

    # if R is negative, then ABSR > L: so, L = ABSR
    # if R is non-negative, then ABSR <= L: so, L = L
    ops.append(Operation.SET_REG_OUT_TO_L_OR_ABSR)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_L_RIGHT)
        ops.append(Operation.SHIFT_ABSR_RIGHT)

    # clear R
    for i in range(R_BITS):
        ops.append(Operation.SHIFT_R_RIGHT)

def demodulator(ops: OperationList) -> None:
    # Load new input
    ops.append(Operation.LOAD_I0_FROM_INPUT)

    # Apply both filters
    for frequency in [UPPER_FREQUENCY, LOWER_FREQUENCY]:
        bandpass_filter(ops, frequency, FILTER_WIDTH)
        rc_filter(ops)
        ops.append(Operation.SEND_O1_TO_OUTPUT)
        ops.append(Operation.SEND_L_TO_OUTPUT)
        ops.append(Operation.BANK_SWITCH)

    # compare L and LS
    ops.append(Operation.ASSERT_R_ZERO)
    fixed_multiply(ops, Register.L, -1.0)
    ops.append(Operation.BANK_SWITCH)
    fixed_multiply(ops, Register.L, 1.0)
    ops.append(Operation.BANK_SWITCH)

    # if r_sign is 1, then the upper frequency signal is stronger
    ops.append(Operation.SEND_R_SIGN_TO_OUTPUT)

    # clear R
    for i in range(R_BITS):
        ops.append(Operation.SHIFT_R_RIGHT)

    # ready for next input
    move_I1_to_I2(ops)
    move_I0_to_I1(ops)
    ops.append(Operation.RESTART)

def multiply_accumulate(ops: OperationList, test_values: typing.List[float]) -> None:
    # For testing: multiply-accumulate
    ops.append(Operation.ASSERT_R_ZERO)

    # Multiply and add repeatedly
    for test_value in test_values:
        ops.append(Operation.LOAD_I0_FROM_INPUT)
        fixed_multiply(ops, Register.I0, test_value)

    move_R_to_O1_and_ABSR(ops)

    # One output
    ops.append(Operation.SEND_O1_TO_OUTPUT)

def multiply_accumulate_via_regs(ops: OperationList, test_values: typing.List[float]) -> None:
    # For testing: multiply-accumulate but via other registers
    ops.append(Operation.ASSERT_R_ZERO)

    # Multiply and add repeatedly
    for test_value in test_values:
        ops.append(Operation.LOAD_I0_FROM_INPUT)
        # multiply from I2, via I1
        move_I0_to_I1(ops)
        move_I1_to_I2(ops)
        fixed_multiply(ops, Register.I2, test_value)
        # move out of R then back into it, via O registers
        move_R_to_O1_and_ABSR(ops)
        move_O1_to_O2(ops)
        fixed_multiply(ops, Register.O2, 1.0)

    # One output
    ops.append(Operation.SEND_O1_TO_OUTPUT)

def main() -> None:
    ops = OperationList()
    demodulator(ops)
    counter = {op: 0 for op in Operation}
    for op in ops:
        counter[op] += 1
    with open("demodulator", "wt") as fd:
        for val in ops.encoded:
            fd.write(f"{val:x}")
    for op in Operation:
        print(f"{counter[op]:4d} {op.name}")
    print(f"{len(ops):4d} total")

    filter_period = (1.0 / SYSTEM_CLOCK_FREQUENCY) * ops.size() * 1e6
    print(f"{ops.size()} ops including prefixes, period will be {filter_period:1.2f} us")
    sample_period = (1.0 / SAMPLE_RATE) * 1e6
    print(f"sample period is {sample_period:1.2f} us per channel")
    assert filter_period < sample_period

        
if __name__ == "__main__":
    main()
