
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
ACCEPTABLE_ERROR = (1.0 / (1 << (FRACTIONAL_BITS - 3)))
VERY_SMALL_ERROR = (1.0 / (1 << FRACTIONAL_BITS))

import enum, math, typing, random, struct

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

class ABSRSelect(enum.Enum):
    PASSTHROUGH = enum.auto()
    NEGATE = enum.auto()
    BORROW = enum.auto()

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
   
OperationList = typing.List[Operation]

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

def run_ops(ops: OperationList, in_values: typing.List[int], debug: bool) -> typing.List[int]:
    out_values: typing.List[int] = []
    reg_file: typing.Dict[Register, int] = {
        register: 0 for register in Register
    }
    in_index = 0
    reg_select = Register.I0
    absr_select = ABSRSelect.PASSTHROUGH
    while in_index < len(in_values):
        for op in ops:
            if debug:
                for (register, value) in reg_file.items():
                    print(f"{register.name} {value:04x} ", end="")
                print(f"op {op.name}")
                
            r_sign = (reg_file[Register.R] >> (R_BITS - 1)) & 1
            a_sign = (reg_file[Register.A] >> (A_BITS - 1)) & 1
            reg_file[Register.A_SIGN] = a_sign
            reg_out = reg_file[reg_select] & 1

            if op == Operation.SET_REG_OUT_TO_A_SIGN:
                reg_select = Register.A_SIGN
            elif op == Operation.SET_REG_OUT_TO_L_OR_ABSR:
                # if R is negative, then ABSR > L: so, L = ABSR
                # if R is non-negative, then ABSR <= L: so, L = L
                if r_sign:
                    reg_select = Register.ABSR
                else:
                    reg_select = Register.L
            elif op in SET_REG_OUT_TABLE:
                reg_select = SET_REG_OUT_TABLE[op]

            elif op == Operation.ADD_A_TO_R:
                reg_file[Register.R] += reg_file[Register.A]
                reg_file[Register.R] &= (1 << R_BITS) - 1
            elif op == Operation.SETUP_ABSR_INPUT:
                if r_sign:
                    absr_select = ABSRSelect.NEGATE
                else:
                    absr_select = ABSRSelect.PASSTHROUGH

            elif op == Operation.SHIFT_A_RIGHT:
                reg_file[Register.A] |= reg_out << A_BITS
                reg_file[Register.A] >>= 1
            elif op == Operation.SHIFT_R_RIGHT:
                reg_file[Register.R] >>= 1
            elif op == Operation.SHIFT_ABSR_RIGHT:
                if absr_select == ABSRSelect.PASSTHROUGH:
                    absr_in = reg_out
                elif absr_select == ABSRSelect.NEGATE:
                    absr_in = 4 - reg_out
                    if absr_in & 2:
                        absr_select = ABSRSelect.BORROW
                elif absr_select == ABSRSelect.BORROW:
                    absr_in = 3 - reg_out
                    if not (absr_in & 2):
                        absr_select = ABSRSelect.NEGATE
                reg_file[Register.ABSR] |= (absr_in & 1) << ALL_BITS
                reg_file[Register.ABSR] >>= 1
            elif op in SHIFT_TABLE:
                reg_file[SHIFT_TABLE[op]] |= reg_out << ALL_BITS
                reg_file[SHIFT_TABLE[op]] >>= 1

            elif op == Operation.BANK_SWITCH:
                reg_file[Register.L], reg_file[Register.LS] = reg_file[Register.LS], reg_file[Register.L]
                reg_file[Register.O1], reg_file[Register.O1S] = reg_file[Register.O1S], reg_file[Register.O1]
                reg_file[Register.O2], reg_file[Register.O2S] = reg_file[Register.O2S], reg_file[Register.O2]

            elif op == Operation.LOAD_I0_FROM_INPUT:
                reg_file[Register.I0] = in_values[in_index]
                in_index += 1
            elif op == Operation.SEND_O1_TO_OUTPUT:
                out_values.append(reg_file[Register.O1])
            elif op == Operation.SEND_L_TO_OUTPUT:
                out_values.append(reg_file[Register.L])
            elif op == Operation.SEND_R_SIGN_TO_OUTPUT:
                pass # out_values.append(r_sign)

            elif op == Operation.ASSERT_A_HIGH_ZERO:
                assert (reg_file[Register.A] >> ALL_BITS) == 0
            elif op == Operation.ASSERT_A_LOW_ZERO:
                assert (reg_file[Register.A] & ((1 << ALL_BITS) - 1)) == 0
            elif op == Operation.ASSERT_R_ZERO:
                assert reg_file[Register.R] == 0
            elif op == Operation.ASSERT_ABSR_IS_ABS_O1:
                assert abs(make_float(reg_file[Register.O1])) == make_float(abs(reg_file[Register.ABSR]))

            else:
                assert False, op.name

    return out_values
        
def main() -> None:
    r = random.Random(1)
    debug = 0
    num_multiply_tests = 100
    num_filter_tests = 100
    num_compare_tests = 80000
    ops: OperationList = []
    for i in range(num_multiply_tests):
        if debug > 0:
            print(f"Test multiply accumulate {i}")
        ops = []
        expect = 0.0
        v1f_list: typing.List[float] = []
        v0i_list: typing.List[int] = []
        for j in range(r.randrange(1, 4)):
            if r.randrange(0, 2) == 0:
                v0s, v1s = 1.99, 1.0
            else:
                v0s, v1s = 1.0, 1.99
            v0i = make_fixed((r.random() * 2.0 * v0s) - v0s)
            v1i = make_fixed((r.random() * 2.0 * v1s) - v1s)
            v0f = make_float(v0i)
            v1f = make_float(v1i)
            if abs(expect + (v0f * v1f)) < 2.0:
                expect += v0f * v1f
                if debug > 0:
                    print(f" + {v0f:1.6f} * {v1f:1.6f} = {v0i:04x} * {v1i:04x} = {expect:1.6f}")

                v1f_list.append(v1f)
                v0i_list.append(v0i)

        via_regs = (r.randrange(0, 2) == 0)
        if via_regs:
            multiply_accumulate_via_regs(ops, v1f_list)
        else:
            multiply_accumulate(ops, v1f_list)
        out_values = run_ops(ops, v0i_list, debug > 1)
        assert len(out_values) == 1
        ri = out_values[0]
        rf = make_float(ri)
        error = abs(rf - expect)
        if debug > 0:
            print(f" result {rf:1.6f} error {error:1.6f} ops {len(ops)} via_regs {via_regs}")
        if via_regs:
            assert error < ACCEPTABLE_ERROR
        else:
            assert error < VERY_SMALL_ERROR

    for i in range(num_filter_tests):
        if debug > 0:
            print(f"Test filter {i}")
        ops = []
        a1 = ((r.random() * 1.2) - 0.6)
        a2 = ((r.random() * 1.2) - 0.6)
        b0 = ((r.random() * 1.2) - 0.6)
        b2 = ((r.random() * 1.2) - 0.6)
        o1 = o2 = i1 = i2 = 0.0
        inputs = []
        expect = []

        for j in range(10):
            i0i = make_fixed((r.random() * 2.0) - 1.0)
            i0 = make_float(i0i)
            inputs.append(i0i)
            o0 = i0*b0 + i2*b2 - o1*a1 - o2*a2
            if debug > 1:
                print(f" step {j} i0 = {make_fixed(i0):04x} * {make_fixed(b0):04x}", end="")
                print(f" i1 = {make_fixed(i1):04x} ", end="")
                print(f" i2 = {make_fixed(i2):04x} * {make_fixed(b2):04x}", end="")
                print(f" o1 = {make_fixed(o1):04x} * {make_fixed(-a1):04x}", end="")
                print(f" o2 = {make_fixed(o2):04x} * {make_fixed(-a2):04x}", end="")
                print(f" -> o0 = {make_fixed(o0):04x}")
            assert abs(o0) < 2.0
            ops.append(Operation.LOAD_I0_FROM_INPUT)
            filter_step(ops, a1, a2, b0, b2)
            move_I1_to_I2(ops)
            move_I0_to_I1(ops)
            ops.append(Operation.SEND_O1_TO_OUTPUT)
            expect.append(o0)
            o2 = o1
            o1 = o0
            i2 = i1
            i1 = i0

        #a0 =   1.006524e+00 a1 =  -1.967579e+00 a2 =   9.870374e-01 (double)
        #b0 =   6.481325e-03 b1 =   0.000000e+00 b2 =  -6.481325e-03 (double)
        #a0 =   1.005859e+00 a1 =  -1.966797e+00 a2 =   9.863281e-01 (fixed_t 9)
        #b0 =   5.859375e-03 b1 =   0.000000e+00 b2 =  -5.859375e-03 (fixed_t 9)

        out_values = run_ops(ops, inputs, debug > 1)
        assert len(out_values) == len(inputs)
        assert len(expect) == len(inputs)
        for j in range(len(inputs)):
            ri = out_values[j]
            rf = make_float(ri)
            i0 = make_float(inputs[j])
            error = abs(rf - expect[j])
            if debug > 0:
                print(f" step {j} input {i0:1.6f} result {rf:1.6f} expected {expect[j]:1.6f} error {error:1.6f}")
            assert error < ACCEPTABLE_ERROR

    ops = []
    demodulator(ops)

    in_values = []
    expect_out_values = []
    out_values_per_in_value = 4
    with open("test_vector", "rb") as fd:
        test_vector_format = "<I" + ("I" * out_values_per_in_value)
        test_vector_size = struct.calcsize(test_vector_format)
        test_vector_shift = 32 - (NON_FRACTIONAL_BITS + FRACTIONAL_BITS)
        test_vector_data = fd.read(test_vector_size)
        while (len(test_vector_data) == test_vector_size) and (len(in_values) < num_compare_tests):
            fields = struct.unpack(test_vector_format, test_vector_data)
            in_values.append(fields[0] >> test_vector_shift)
            for i in range(1, 5):
                expect_out_values.append(fields[i] >> test_vector_shift)
            test_vector_data = fd.read(test_vector_size)

    out_values = run_ops(ops, in_values, debug > 1)
    assert len(out_values) == len(expect_out_values)
    for i in range(len(in_values)):
        actual_upper_bandpass = out_values[(i * out_values_per_in_value) + 0]
        actual_upper_rc = out_values[(i * out_values_per_in_value) + 1]
        actual_lower_bandpass = out_values[(i * out_values_per_in_value) + 2]
        actual_lower_rc = out_values[(i * out_values_per_in_value) + 3]

        expect_upper_bandpass = expect_out_values[(i * out_values_per_in_value) + 0]
        expect_upper_rc = expect_out_values[(i * out_values_per_in_value) + 1]
        expect_lower_bandpass = expect_out_values[(i * out_values_per_in_value) + 2]
        expect_lower_rc = expect_out_values[(i * out_values_per_in_value) + 3]

        if debug > 0:
            print(f"step {i}", end="")
            print(f" in {in_values[i]:04x}", end="")
        for (name, expect, actual) in [
                    ("bh", expect_upper_bandpass, actual_upper_bandpass),
                    ("rh", expect_upper_rc, actual_upper_rc),
                    ("bl", expect_lower_bandpass, actual_lower_bandpass),
                    ("rl", expect_lower_rc, actual_lower_rc),
                ]:
            fexpect = make_float(expect)
            factual = make_float(actual)
            if debug > 0:
                print(f" e{name} {expect:04x} {fexpect:1.6f} a{name} {actual:04x} {factual:1.6f}", end="")
            error = abs(fexpect - factual)
            if debug > 0:
                print(f" x{name} {error:1.6f}")
            assert error == 0 # < ACCEPTABLE_ERROR
   
    filter_period = (1.0 / SYSTEM_CLOCK_FREQUENCY) * len(ops) * 1e6
    print(f"{len(ops)} ops, period will be {filter_period:1.2f} us")
    sample_period = (1.0 / SAMPLE_RATE) * 1e6
    print(f"sample period is {sample_period:1.2f} us per channel")
    assert filter_period < sample_period

if __name__ == "__main__":
    main()
