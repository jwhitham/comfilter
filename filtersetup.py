

SAMPLE_RATE = 48000
FRACTIONAL_BITS = 14
NONFRACTIONAL_BITS = 2
ALL_BITS = FRACTIONAL_BITS + NONFRACTIONAL_BITS
UPPER_FREQUENCY = 1270
LOWER_FREQUENCY = 1070
FILTER_WIDTH = 100

import enum, math, typing

class Register(enum.Enum):
    I0 = enum.auto()
    I1 = enum.auto()
    I2 = enum.auto()
    O0 = enum.auto()
    O1 = enum.auto()
    O2 = enum.auto()
    A_SIGN = enum.auto()
    R = enum.auto()
    ZERO = enum.auto()

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
    SET_REG_OUT_TO_O0 = enum.auto()
    SET_REG_OUT_TO_O1 = enum.auto()
    SET_REG_OUT_TO_O2 = enum.auto()
    SET_REG_OUT_TO_ZERO = enum.auto()
    SET_REG_OUT_TO_A_SIGN = enum.auto()
    SET_REG_OUT_TO_R = enum.auto()
    SHIFT_I0_RIGHT = enum.auto()
    SHIFT_I1_RIGHT = enum.auto()
    SHIFT_I2_RIGHT = enum.auto()
    SHIFT_O0_RIGHT = enum.auto()
    SHIFT_O1_RIGHT = enum.auto()
    SHIFT_O2_RIGHT = enum.auto()
    LOAD_I0_FROM_INPUT = enum.auto()
    SEND_O0_TO_OUTPUT = enum.auto()
   
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

def fixed_multiply(ops: OperationList, value: float) -> None:
    ivalue = make_fixed(value)
    print(f"Multiplication with value {value:1.6f} fixed encoding {ivalue:04x}")
    ops.append(Operation.SET_REG_OUT_TO_A_SIGN)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_A_RIGHT)
        ivalue = ivalue << 1
        if ivalue & (1 << ALL_BITS):
            ops.append(Operation.ADD_A_TO_R)

def load_A_register(ops: OperationList, source: Register) -> None:
    # Fill the low bits of A with zero
    ops.append(Operation.SET_REG_OUT_TO_ZERO)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_A_RIGHT)

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
        ops.append({
            Register.I0: Operation.SHIFT_I0_RIGHT,
            Register.I2: Operation.SHIFT_I2_RIGHT,
            Register.O1: Operation.SHIFT_O1_RIGHT,
            Register.O2: Operation.SHIFT_O2_RIGHT,
            }[source])

def clear_R(ops: OperationList) -> None:
    # R = 0
    for i in range(ALL_BITS * 2):
        ops.append(Operation.SHIFT_R_RIGHT)

def bandpass_filter(ops: OperationList, frequency: float, width: float) -> None:
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

    # R should be zero here!
    ops.append(Operation.LOAD_I0_FROM_INPUT)

    # R += i0 * b0
    load_A_register(ops, Register.I0)
    fixed_multiply(ops, b0)
    # R += i2 * b2
    load_A_register(ops, Register.I2)
    fixed_multiply(ops, b2)
    # R -= o1 * a1
    load_A_register(ops, Register.O1)
    fixed_multiply(ops, -a1)
    # R -= o2 * a2
    load_A_register(ops, Register.O2)
    fixed_multiply(ops, -a2)

    # Discard low bits of R
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_R_RIGHT)

    # Move O1 to O2
    ops.append(Operation.SET_REG_OUT_TO_O1)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_O2_RIGHT)
        ops.append(Operation.SHIFT_O1_RIGHT)

    # Move O0 to O1
    ops.append(Operation.SET_REG_OUT_TO_O0)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_O1_RIGHT)
        ops.append(Operation.SHIFT_O0_RIGHT)

    # Move high bits of R to O0
    ops.append(Operation.SET_REG_OUT_TO_R)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_R_RIGHT)
        ops.append(Operation.SHIFT_O0_RIGHT)

    # Move I1 to I2
    ops.append(Operation.SET_REG_OUT_TO_I1)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_I2_RIGHT)
        ops.append(Operation.SHIFT_I1_RIGHT)
    # Move I0 to I1
    ops.append(Operation.SET_REG_OUT_TO_I0)
    for i in range(ALL_BITS):
        ops.append(Operation.SHIFT_I1_RIGHT)
        ops.append(Operation.SHIFT_I0_RIGHT)
    # R should be zero again here!

    ops.append(Operation.SEND_O0_TO_OUTPUT)

def run_ops(ops: OperationList, in_values: typing.List[int], debug: bool) -> typing.List[int]:
    reg_select = Register.I0
    a_value = 0
    r_value = 0
    i0_value = 0
    i1_value = 0
    i2_value = 0
    o0_value = 0
    o1_value = 0
    o2_value = 0
    out_values = []
    while len(out_values) < len(in_values):
        for op in ops:
            if debug:
                for (name, value) in [
                            ("A", a_value),
                            ("R", r_value),
                        ]:
                    print(f"{name} {value:06x} ", end="")
                for (name, value) in [
                            ("I0", i0_value),
                            ("I1", i1_value),
                            ("I2", i2_value),
                            ("O0", o0_value),
                            ("O1", o1_value),
                            ("O2", o2_value),
                        ]:
                    print(f"{name} {value:04x} ", end="")
                print(f"op: {op.name}")
                
            reg_out = {
                    Register.I0: i0_value,
                    Register.I1: i1_value,
                    Register.I2: i2_value,
                    Register.O0: o0_value,
                    Register.O1: o1_value,
                    Register.O2: o2_value,
                    Register.A_SIGN: a_value >> ((ALL_BITS * 2) - 1),
                    Register.R: r_value,
                    Register.ZERO: 0,
                    }[reg_select] & 1
            if op == Operation.ADD_A_TO_R:
                r_value += a_value
                r_value &= (1 << (ALL_BITS * 2)) - 1
            elif op == Operation.SHIFT_A_RIGHT:
                a_value |= reg_out << (ALL_BITS * 2)
                a_value = a_value >> 1
            elif op == Operation.SHIFT_R_RIGHT:
                r_value = r_value >> 1
            elif op == Operation.SET_REG_OUT_TO_I0:
                reg_select = Register.I0
            elif op == Operation.SET_REG_OUT_TO_I1:
                reg_select = Register.I1
            elif op == Operation.SET_REG_OUT_TO_I2:
                reg_select = Register.I2
            elif op == Operation.SET_REG_OUT_TO_O0:
                reg_select = Register.O0
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
            elif op == Operation.SHIFT_O0_RIGHT:
                o0_value |= reg_out << ALL_BITS
                o0_value = o0_value >> 1
            elif op == Operation.SHIFT_O1_RIGHT:
                o1_value |= reg_out << ALL_BITS
                o1_value = o1_value >> 1
            elif op == Operation.SHIFT_O2_RIGHT:
                o2_value |= reg_out << ALL_BITS
                o2_value = o2_value >> 1
            elif op == Operation.LOAD_I0_FROM_INPUT:
                i0_value = in_values[len(out_values)]
            elif op == Operation.SEND_O0_TO_OUTPUT:
                out_values.append(o0_value)
            else:
                assert False

    return out_values
        
def main() -> None:
    ops: OperationList = []
    bandpass_filter(ops, UPPER_FREQUENCY, FILTER_WIDTH)
    in_values = []
    expect_out_values = []
    count = 0
    with open("sigdec.txt", "rt", encoding="utf-8") as fd:
        for line in fd:
            fields = line.split()
            in_values.append(make_fixed(float(fields[1])))
            expect_out_values.append(make_fixed(float(fields[2])))
            if in_values[-1] != 0:
                count += 1
                if count > 20:
                    break

    count += 5
    in_values = in_values[-count:]
    expect_out_values = expect_out_values[-count:]
    out_values = run_ops(ops, in_values, False)
    for i in range(len(in_values)):
        for (name, value) in [
                    ("in", in_values[i]),
                    ("exp", expect_out_values[i]),
                    ("out", out_values[i]),
                ]:
            fvalue = make_float(value)
            print(f"{name} {value:04x} {fvalue:1.6f} ", end="")
        print("")

if __name__ == "__main__":
    main()
