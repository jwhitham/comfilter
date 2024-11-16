
from filtersetup import (
        OperationList, Register, Operation, SET_REG_OUT_TABLE, SHIFT_TABLE,
        ALL_BITS, A_BITS, R_BITS, make_fixed, make_float,
        multiply_accumulate, filter_step, demodulator,
        multiply_accumulate_via_regs, move_reg_to_reg,
        set_X_to_abs_O1, set_Y_to_X_minus_reg,
        move_X_to_L_if_Y_is_not_negative_else_move_L_to_X,
    )
from settings import FRACTIONAL_BITS, NON_FRACTIONAL_BITS, SAMPLE_RATE
import enum, math, typing, random, struct

ACCEPTABLE_ERROR = (1.0 / (1 << (FRACTIONAL_BITS - 3)))
VERY_SMALL_ERROR = (1.0 / (1 << FRACTIONAL_BITS)) * 1.01

class XSelect(enum.Enum):
    PASSTHROUGH_X = enum.auto()
    PASSTHROUGH_REG_OUT = enum.auto()
    NEGATE_REG_OUT = enum.auto()
    BORROW_REG_OUT = enum.auto()

class YSelect(enum.Enum):
    X_MINUS_REG_OUT = enum.auto()
    BORROW_X_MINUS_REG_OUT = enum.auto()

def run_ops(ops: OperationList, in_values: typing.List[int], debug: bool) -> typing.List[int]:
    out_values: typing.List[int] = []
    reg_file: typing.Dict[Register, int] = {
        register: 0 for register in Register
    }
    in_index = 0
    reg_select = Register.I0
    x_select = XSelect.PASSTHROUGH_X
    y_select = YSelect.X_MINUS_REG_OUT
    while in_index < len(in_values):
        for op in ops:
            if debug:
                for (register, value) in reg_file.items():
                    print(f"{register.name} {value:04x} ", end="")
                print(f"op {op.name}")
                
            r_sign = (reg_file[Register.R] >> (R_BITS - 1)) & 1
            a_sign = (reg_file[Register.A] >> (A_BITS - 1)) & 1
            reg_out = reg_file[reg_select] & 1

            if op in SET_REG_OUT_TABLE:
                reg_select = SET_REG_OUT_TABLE[op]

            elif op == Operation.ADD_A_TO_R:
                reg_file[Register.R] += reg_file[Register.A]
                reg_file[Register.R] &= (1 << R_BITS) - 1
            elif op == Operation.SHIFT_A_RIGHT:
                reg_file[Register.A] |= reg_out << A_BITS
                reg_file[Register.A] >>= 1
            elif op == Operation.SHIFT_R_RIGHT:
                reg_file[Register.R] >>= 1
            elif op == Operation.SHIFT_X_RIGHT:
                if x_select == XSelect.PASSTHROUGH_REG_OUT:
                    x_in = reg_out
                elif x_select == XSelect.PASSTHROUGH_X:
                    x_in = reg_file[Register.X] & 1
                elif x_select == XSelect.NEGATE_REG_OUT:
                    x_in = 4 - reg_out
                    if x_in & 2:
                        x_select = XSelect.BORROW_REG_OUT
                elif x_select == XSelect.BORROW_REG_OUT:
                    x_in = 3 - reg_out
                    if not (x_in & 2):
                        x_select = XSelect.NEGATE_REG_OUT
                else:
                    assert False
                reg_file[Register.X] |= (x_in & 1) << ALL_BITS
                reg_file[Register.X] >>= 1
            elif op == Operation.SHIFT_Y_RIGHT:
                if y_select == YSelect.X_MINUS_REG_OUT:
                    y_in = 4 + (reg_file[Register.X] & 1) - reg_out
                    if y_in & 2:
                        y_select = YSelect.BORROW_X_MINUS_REG_OUT
                elif y_select == YSelect.BORROW_X_MINUS_REG_OUT:
                    y_in = 3 + (reg_file[Register.X] & 1) - reg_out
                    if not (y_in & 2):
                        y_select = YSelect.X_MINUS_REG_OUT
                else:
                    assert False
                reg_file[Register.Y] |= (y_in & 1) << ALL_BITS
                reg_file[Register.Y] >>= 1
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
            elif op == Operation.SEND_Y_SIGN_TO_OUTPUT:
                out_values.append(reg_file[Register.Y] >> (ALL_BITS - 1))
            elif op == Operation.SEND_Y_TO_OUTPUT:
                out_values.append(reg_file[Register.Y])
            elif op == Operation.SET_REG_OUT_TO_L_OR_X:
                if reg_file[Register.Y] >> (ALL_BITS - 1):
                    reg_select = Register.L # Y negative, use L
                else:
                    reg_select = Register.X # Y non-negative, use X
            elif op == Operation.SET_X_IN_TO_ABS_REG_OUT:
                if reg_file[Register.O1] >> (ALL_BITS - 1):
                    x_select = XSelect.NEGATE_REG_OUT
                else:
                    x_select = XSelect.PASSTHROUGH_REG_OUT
            elif op == Operation.SET_X_IN_TO_X:
                x_select = XSelect.PASSTHROUGH_X
            elif op == Operation.SET_Y_IN_TO_X_MINUS_REG_OUT:
                y_select = YSelect.X_MINUS_REG_OUT
            elif op == Operation.ASSERT_A_HIGH_ZERO:
                assert (reg_file[Register.A] >> ALL_BITS) == 0
            elif op == Operation.ASSERT_A_LOW_ZERO:
                assert (reg_file[Register.A] & ((1 << ALL_BITS) - 1)) == 0
            elif op == Operation.ASSERT_R_ZERO:
                assert reg_file[Register.R] == 0
            elif op == Operation.ASSERT_X_IS_ABS_O1:
                assert abs(make_float(reg_file[Register.O1])) == make_float(abs(reg_file[Register.X]))
            elif op == Operation.ASSERT_Y_IS_X_MINUS_L:
                assert reg_file[Register.Y] == ((reg_file[Register.X] - reg_file[Register.L]) & ((1 << ALL_BITS) - 1))
            elif op == Operation.RESTART:
                break
            else:
                assert False, op.name

    return out_values
        
def test_multiply_accumulate(r: random.Random, debug: int, num_multiply_tests: int) -> None:
    debug = 0
    print(f"Test multiply accumulate")
    for i in range(num_multiply_tests):
        if debug > 0:
            print(f"Test multiply accumulate {i}")
        ops = OperationList()
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

def test_bandpass_filter(r: random.Random, debug: int, num_filter_tests: int) -> None:
    print(f"Test bandpass filter")
    for i in range(num_filter_tests):
        if debug > 0:
            print(f"Test bandpass filter {i}")
        ops = OperationList()
        a1 = ((r.random() * 1.2) - 0.6)
        a2 = ((r.random() * 1.2) - 0.6)
        b0 = ((r.random() * 1.2) - 0.6)
        b2 = ((r.random() * 1.2) - 0.6)
        o1 = o2 = i1 = i2 = 0.0
        inputs = []
        expect_values = []

        for j in range(10):
            # Find suitable i0 value that keeps o0 in range
            o0 = 99.0
            attempts_left = 5
            while abs(o0) >= 1.99:
                assert attempts_left > 0
                i0i = make_fixed((r.random() * 2.0) - 1.0)
                i0 = make_float(i0i)
                o0 = i0*b0 + i2*b2 - o1*a1 - o2*a2
                attempts_left -= 1
                
            inputs.append(i0i)
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
            move_reg_to_reg(ops, Register.I1, Register.I2)
            move_reg_to_reg(ops, Register.I0, Register.I1)
            ops.append(Operation.SEND_O1_TO_OUTPUT)
            expect_values.append(o0)
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
        assert len(expect_values) == len(inputs)
        for j in range(len(inputs)):
            ri = out_values[j]
            rf = make_float(ri)
            i0 = make_float(inputs[j])
            error = abs(rf - expect_values[j])
            if debug > 0:
                print(f" step {j} input {i0:1.6f} result {rf:1.6f} expected {expect_values[j]:1.6f} error {error:1.6f}")
            assert error < ACCEPTABLE_ERROR

def test_move_X_to_L_if_Y_is_not_negative(r: random.Random, debug: int, num_update_tests: int) -> None:
    print(f"Test update of L")
    for i in range(num_update_tests):
        ops = OperationList()
        inputs = []
        expect_values = []

        # Generate test values - must keep yf in range
        # O1 should be -1.0 .. 1.0 but might be slightly outside
        # L should be 0.0 .. 1.0 but might be slightly greater
        yf = 99.0
        attempts_left = 5
        while abs(yf) >= 1.99:
            assert attempts_left > 0
            o1i = make_fixed((r.random() * 2.2) - 1.1)
            li = make_fixed(r.random() * 1.1)

            # Calculate expected result
            xf = abs(make_float(o1i))
            yf = xf - make_float(li)
            attempts_left -= 1

        xi = make_fixed(xf)
        yi = make_fixed(yf)
        if debug > 0:
            print(f" O1 = {o1i:04x} L = {li:04x} X = {xi:04x} Y = {yi:04x}", end="")

        expect_li = li
        expect_xi = xi
        expect_o1i = o1i

        if yf >= 0.0:
            expect_li = xi
            expect_xi = li
            if debug > 0:
                print(f" use abs(O1) =", end="")
        else:
            if debug > 0:
                print(f" use L       =", end="")
        if debug > 0:
            print(f" {expect_li:04x} X = {expect_xi:04x}", end="")

        # Load input 
        inputs.append(o1i)
        ops.append(Operation.LOAD_I0_FROM_INPUT)
        move_reg_to_reg(ops, Register.I0, Register.O1)
        inputs.append(li)
        ops.append(Operation.LOAD_I0_FROM_INPUT)
        move_reg_to_reg(ops, Register.I0, Register.L)

        # do it
        set_X_to_abs_O1(ops)
        set_Y_to_X_minus_reg(ops, Register.L)
        move_X_to_L_if_Y_is_not_negative_else_move_L_to_X(ops)
        ops.append(Operation.SEND_L_TO_OUTPUT)
        ops.append(Operation.SEND_O1_TO_OUTPUT)
        move_reg_to_reg(ops, Register.X, Register.O1)
        ops.append(Operation.SEND_O1_TO_OUTPUT)

        # run
        out_values = run_ops(ops, inputs, debug > 1)
        assert len(out_values) == 3

        result_li = out_values[0]
        result_o1i = out_values[1]
        result_xi = out_values[2]
        if debug > 0:
            print(f" result L = {result_li:04x} result X = {result_xi:04x}")
        assert expect_li == result_li
        assert expect_o1i == result_o1i
        assert expect_xi == result_xi

def test_set_Y_to_X_minus_reg(r: random.Random, debug: int, num_update_tests: int) -> None:
    print(f"Test update of Y")
    for i in range(num_update_tests):
        ops = OperationList()
        inputs = []
        expect_values = []

        # Generate test values - must keep yf in range
        # X, L should be 0.0 .. 1.0 but might be slightly outside
        yf = 99.0
        attempts_left = 5
        while abs(yf) >= 1.99:
            assert attempts_left > 0
            xi = make_fixed(r.random() * 1.1)
            li = make_fixed(r.random() * 1.1)

            # Calculate expected result
            xf = make_float(xi)
            lf = make_float(li)
            yf = xf - lf
            attempts_left -= 1

        # Load input 
        expect = make_fixed(yf)
        inputs.append(xi)
        ops.append(Operation.LOAD_I0_FROM_INPUT)
        move_reg_to_reg(ops, Register.I0, Register.X)
        inputs.append(li)
        ops.append(Operation.LOAD_I0_FROM_INPUT)

        # Operation: Y = X - I0
        set_Y_to_X_minus_reg(ops, Register.I0)
        ops.append(Operation.SEND_Y_SIGN_TO_OUTPUT)
        ops.append(Operation.SEND_Y_TO_OUTPUT)

        # run
        out_values = run_ops(ops, inputs, debug > 1)
        assert len(out_values) == 2

        result = out_values[0]
        if yf < 0.0:
            assert result == 1
        else:
            assert result == 0

        result = out_values[1]
        assert result == expect



def test_demodulator(debug: int, num_compare_tests: int) -> None:
    print(f"Test demodulator")
    ops = OperationList()
    demodulator(ops)
    in_values: typing.List[int] = []
    expect_out_values = []
    out_values_per_in_value = 5
    with open("generated/test_vector", "rb") as fd:
        test_vector_format = "<I" + ("I" * out_values_per_in_value)
        test_vector_size = struct.calcsize(test_vector_format)
        test_vector_shift = 32 - (NON_FRACTIONAL_BITS + FRACTIONAL_BITS)
        test_vector_data = fd.read(test_vector_size)
        while (len(test_vector_data) == test_vector_size) and (len(in_values) < num_compare_tests):
            fields = struct.unpack(test_vector_format, test_vector_data)
            in_values.append(fields[0] >> test_vector_shift)
            for i in range(out_values_per_in_value):
                expect_out_values.append(fields[i + 1] >> test_vector_shift)
            test_vector_data = fd.read(test_vector_size)

    out_values = run_ops(ops, in_values, debug > 1)
    assert len(out_values) == len(expect_out_values)
    correct = 0
    for i in range(len(in_values)):
        actual_upper_bandpass = out_values[(i * out_values_per_in_value) + 0]
        actual_upper_rc = out_values[(i * out_values_per_in_value) + 1]
        actual_lower_bandpass = out_values[(i * out_values_per_in_value) + 2]
        actual_lower_rc = out_values[(i * out_values_per_in_value) + 3]
        actual_out_bit = out_values[(i * out_values_per_in_value) + 4]

        expect_upper_bandpass = expect_out_values[(i * out_values_per_in_value) + 0]
        expect_upper_rc = expect_out_values[(i * out_values_per_in_value) + 1]
        expect_lower_bandpass = expect_out_values[(i * out_values_per_in_value) + 2]
        expect_lower_rc = expect_out_values[(i * out_values_per_in_value) + 3]
        expect_out_bit = expect_out_values[(i * out_values_per_in_value) + 4] & 1

        if debug > 0:
            print(f"step {i} in {in_values[i]:04x}")
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
            assert error < VERY_SMALL_ERROR
        if expect_out_bit == actual_out_bit:
            correct += 1
   
    print(f"{correct} bits out of {len(in_values)} matched expectations")
    assert correct > (len(in_values) * 0.99)

def main() -> None:
    debug = 0
    r = random.Random(2)
    test_multiply_accumulate(r, debug, 100)
    test_bandpass_filter(r, debug, 100)
    test_move_X_to_L_if_Y_is_not_negative(r, debug, 100)
    test_set_Y_to_X_minus_reg(r, debug, 100)
    test_demodulator(debug, 100)

if __name__ == "__main__":
    main()
