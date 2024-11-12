

SAMPLE_RATE = 48000
FRACTIONAL_BITS = 14
NON_FRACTIONAL_BITS = 2
ALL_BITS = FRACTIONAL_BITS + NON_FRACTIONAL_BITS
A_BITS = ALL_BITS * 2
R_BITS = (FRACTIONAL_BITS * 2) + NON_FRACTIONAL_BITS
UPPER_FREQUENCY = 1270
LOWER_FREQUENCY = 1070
FILTER_WIDTH = 100
ACCEPTABLE_ERROR = (1.0 / (1 << (FRACTIONAL_BITS - 3)))
VERY_SMALL_ERROR = (1.0 / (1 << FRACTIONAL_BITS))

import enum, math, typing, random

class Register(enum.Enum):
    I0 = enum.auto()
    I1 = enum.auto()
    I2 = enum.auto()
    O1 = enum.auto()
    O2 = enum.auto()
    A_SIGN = enum.auto()
    R = enum.auto()
    ZERO = enum.auto()
    ABSO = enum.auto()

class Constant(enum.Enum):
    A1 = enum.auto()
    A2 = enum.auto()
    B0 = enum.auto()
    B2 = enum.auto()

class Operation(enum.Enum):
    ADD_A_TO_R = enum.auto()
    SHIFT_A_RIGHT = enum.auto()
    SHIFT_R_RIGHT = enum.auto()
    SET_REG_OUT_TO_I0 = enum.auto()
    SET_REG_OUT_TO_I1 = enum.auto()
    SET_REG_OUT_TO_I2 = enum.auto()
    SET_REG_OUT_TO_O1 = enum.auto()
    SET_REG_OUT_TO_O2 = enum.auto()
    SET_REG_OUT_TO_ZERO = enum.auto()
    SET_REG_OUT_TO_A_SIGN = enum.auto()
    SET_REG_OUT_TO_R = enum.auto()
    SHIFT_I0_RIGHT = enum.auto()
    SHIFT_I1_RIGHT = enum.auto()
    SHIFT_I2_RIGHT = enum.auto()
    SHIFT_O1_RIGHT = enum.auto()
    SHIFT_O2_RIGHT = enum.auto()
    SHIFT_ABSO_RIGHT = enum.auto()
    SETUP_ABSO_INPUT = enum.auto()
    LOAD_I0_FROM_INPUT = enum.auto()
    SEND_O1_TO_OUTPUT = enum.auto()
    ASSERT_A_HIGH_ZERO = enum.auto()
    ASSERT_A_LOW_ZERO = enum.auto()
    ASSERT_R_ZERO = enum.auto()
   
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

def fixed_multiply(ops: OperationList, source: Register, value: float) -> None:
    ivalue = make_fixed(value)
    negative = ivalue & (1 << (ALL_BITS - 1))
    # print(f"Multiplication with value {value:1.6f} fixed encoding {ivalue:04x}")

    # Clear high A bits
    ops.append(Operation.SET_REG_OUT_TO_ZERO)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_A_RIGHT)
    ops.append(Operation.ASSERT_A_HIGH_ZERO)

    # If negative, also clear the low bits, as these will be added during shift-in
    if negative:
        for i in range(ALL_BITS):
            ops.append(Operation.SHIFT_A_RIGHT)
        ops.append(Operation.ASSERT_A_LOW_ZERO)

    # Configure source
    ops.append({
        Register.I0: Operation.SET_REG_OUT_TO_I0,
        Register.I2: Operation.SET_REG_OUT_TO_I2,
        Register.O1: Operation.SET_REG_OUT_TO_O1,
        Register.O2: Operation.SET_REG_OUT_TO_O2,
        }[source])

    # Fill the high bits of A with the register value
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_A_RIGHT)
        if negative:
            ops.append(Operation.ADD_A_TO_R)
        ops.append({
            Register.I0: Operation.SHIFT_I0_RIGHT,
            Register.I2: Operation.SHIFT_I2_RIGHT,
            Register.O1: Operation.SHIFT_O1_RIGHT,
            Register.O2: Operation.SHIFT_O2_RIGHT,
            }[source])

    ops.append(Operation.ASSERT_A_LOW_ZERO)

    # Do multiplication
    ops.append(Operation.SET_REG_OUT_TO_A_SIGN)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_A_RIGHT)
        ivalue = ivalue << 1
        if ivalue & (1 << ALL_BITS):
            ops.append(Operation.ADD_A_TO_R)

def move_R_to_O1_and_ABSO(ops: OperationList) -> None:
    # Discard low bits of R
    for i in range(FRACTIONAL_BITS):
        ops.append(Operation.SHIFT_R_RIGHT)

    # Setup ABSO register by looking at the sign of R
    # If R is negative, input for ABSO is negated
    #ops.append(Operation.SETUP_ABSO_INPUT)

    # Move result bits of R to O1 and ABSO
    ops.append(Operation.SET_REG_OUT_TO_R)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_O1_RIGHT)
        #ops.append(Operation.SHIFT_ABSO_RIGHT)
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

    ops.append(Operation.LOAD_I0_FROM_INPUT)

    # R += i0 * b0
    fixed_multiply(ops, Register.I0, b0)
    # R += i2 * b2
    fixed_multiply(ops, Register.I2, b2)
    # R -= o1 * a1
    fixed_multiply(ops, Register.O1, -a1)
    # R -= o2 * a2
    fixed_multiply(ops, Register.O2, -a2)

    move_O1_to_O2(ops)
    move_I1_to_I2(ops)
    move_I0_to_I1(ops)
    move_R_to_O1_and_ABSO(ops)

    ops.append(Operation.SEND_O1_TO_OUTPUT)

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

def multiply_accumulate(ops: OperationList, test_values: typing.List[float]) -> None:
    # For testing: multiply-accumulate
    ops.append(Operation.ASSERT_R_ZERO)

    # Multiply and add repeatedly
    for test_value in test_values:
        ops.append(Operation.LOAD_I0_FROM_INPUT)
        fixed_multiply(ops, Register.I0, test_value)

    move_R_to_O1_and_ABSO(ops)

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
        move_R_to_O1_and_ABSO(ops)
        move_O1_to_O2(ops)
        fixed_multiply(ops, Register.O2, 1.0)

    # One output
    ops.append(Operation.SEND_O1_TO_OUTPUT)

def run_ops(ops: OperationList, in_values: typing.List[int], debug: bool) -> typing.List[int]:
    reg_select = Register.I0
    a_value = 0
    r_value = 0
    i0_value = 0
    i1_value = 0
    i2_value = 0
    o1_value = 0
    o2_value = 0
    neg_value = 0
    out_values = []
    in_index = 0
    while in_index < len(in_values):
        for op in ops:
            if debug:
                for (name, value) in [
                            ("A", a_value),
                            ("R", r_value),
                        ]:
                    print(f"{name} {value:08x} ", end="")
                for (name, value) in [
                            ("I0", i0_value),
                            ("I1", i1_value),
                            ("I2", i2_value),
                            ("O1", o1_value),
                            ("O2", o2_value),
                        ]:
                    print(f"{name} {value:04x} ", end="")
                print(f"neg {neg_value:x} ", end="")
                print(f"op: {op.name}")
                
            reg_out = {
                    Register.I0: i0_value,
                    Register.I1: i1_value,
                    Register.I2: i2_value,
                    Register.O1: o1_value,
                    Register.O2: o2_value,
                    Register.A_SIGN: a_value >> (A_BITS - 1),
                    Register.R: r_value,
                    Register.ZERO: 0,
                    }[reg_select] & 1
            if op == Operation.ADD_A_TO_R:
                r_value += a_value
                r_value &= (1 << R_BITS) - 1
            elif op == Operation.SHIFT_A_RIGHT:
                a_value |= reg_out << A_BITS
                a_value = a_value >> 1
            elif op == Operation.SHIFT_R_RIGHT:
                r_value = r_value >> 1
            elif op == Operation.SET_REG_OUT_TO_I0:
                reg_select = Register.I0
            elif op == Operation.SET_REG_OUT_TO_I1:
                reg_select = Register.I1
            elif op == Operation.SET_REG_OUT_TO_I2:
                reg_select = Register.I2
            elif op == Operation.SET_REG_OUT_TO_O1:
                reg_select = Register.O1
            elif op == Operation.SET_REG_OUT_TO_O2:
                reg_select = Register.O2
            elif op == Operation.SET_REG_OUT_TO_ZERO:
                reg_select = Register.ZERO
            elif op == Operation.SET_REG_OUT_TO_A_SIGN:
                reg_select = Register.A_SIGN
            elif op == Operation.SET_REG_OUT_TO_R:
                reg_select = Register.R
            elif op == Operation.SHIFT_I0_RIGHT:
                i0_value |= reg_out << ALL_BITS
                i0_value = i0_value >> 1
            elif op == Operation.SHIFT_I1_RIGHT:
                i1_value |= reg_out << ALL_BITS
                i1_value = i1_value >> 1
            elif op == Operation.SHIFT_I2_RIGHT:
                i2_value |= reg_out << ALL_BITS
                i2_value = i2_value >> 1
            elif op == Operation.SHIFT_O1_RIGHT:
                o1_value |= reg_out << ALL_BITS
                o1_value = o1_value >> 1
            elif op == Operation.SHIFT_O2_RIGHT:
                o2_value |= reg_out << ALL_BITS
                o2_value = o2_value >> 1
            elif op == Operation.LOAD_I0_FROM_INPUT:
                i0_value = in_values[in_index]
                in_index += 1
            elif op == Operation.SEND_O1_TO_OUTPUT:
                out_values.append(o1_value)
            elif op == Operation.ASSERT_A_HIGH_ZERO:
                assert (a_value >> ALL_BITS) == 0
            elif op == Operation.ASSERT_A_LOW_ZERO:
                assert (a_value & ((1 << ALL_BITS) - 1)) == 0
            elif op == Operation.ASSERT_R_ZERO:
                assert r_value == 0
            else:
                assert False

    return out_values
        
def main() -> None:
    r = random.Random(1)
    debug = 0
    ops: OperationList = []
    for i in range(100):
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
                    print(f" + {v0f:1.6f} * {v1f:1.6f} = {expect:1.6f}")
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

    for i in range(100):
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
            filter_step(ops, a1, a2, b0, b2)
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

    print(f"filter for {UPPER_FREQUENCY} Hz")
    ops = []
    bandpass_filter(ops, UPPER_FREQUENCY, FILTER_WIDTH)
    in_values = []
    expect_out_values = []
    count = 0
    trigger = False
    test_size = 1000
    with open("debug_2", "rt", encoding="utf-8") as fd:
        for line in fd:
            fields = line.split()
            in_values.append(make_fixed(float(fields[1])))
            expect_out_values.append(make_fixed(float(fields[2])))
            if in_values[-1] != 0:
                trigger = True
            if trigger:
                count += 1
                if count > test_size:
                    break

    in_values = in_values[-count:]
    expect_out_values = expect_out_values[-count:]
    out_values = run_ops(ops, in_values, debug > 1)
    for i in range(len(in_values)):
        if debug > 0:
            print(f"step {i}", end="")
            for (name, value) in [
                        ("in", in_values[i]),
                        ("exp", expect_out_values[i]),
                        ("out", out_values[i]),
                    ]:
                fvalue = make_float(value)
                print(f" {name} {value:04x} {fvalue:1.6f} ", end="")
        error = abs(make_float(expect_out_values[i]) - make_float(out_values[i]))
        if debug > 0:
            print(f" error {error:1.6f}")
        assert error < ACCEPTABLE_ERROR
    print(f"Test: error {error:1.6f}")

if __name__ == "__main__":
    main()
