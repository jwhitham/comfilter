import filtersetup
from filtersetup import (
        ControlLine, ControlLines,
        OperationList, Register, Operation, ControlOperation,
        ALL_BITS, A_BITS, R_BITS, make_fixed, make_float,
        SHIFT_CONTROL_LINE,
        multiply_accumulate, filter_step, demodulator,
        multiply_accumulate_via_regs, move_reg_to_reg,
        set_X_to_abs_O1, set_Y_to_X_minus_reg,
        move_X_to_L_if_Y_is_not_negative,
    )
from settings import FRACTIONAL_BITS, NON_FRACTIONAL_BITS, SAMPLE_RATE
import enum, math, typing, random, struct

ACCEPTABLE_ERROR = (1.0 / (1 << (FRACTIONAL_BITS - 3)))
VERY_SMALL_ERROR = (1.0 / (1 << FRACTIONAL_BITS)) * 1.01

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
    Y_SELECT = -101
    MUX_SELECT = -102
    REPEAT_COUNTER = -103

class NextStep(enum.Enum):
    NEXT = enum.auto()
    REPEAT = enum.auto()
    RESTART = enum.auto()

RegFile = typing.Dict[typing.Union[Register, SpecialRegister], int]
NUMBER_TO_REGISTER = {r.value: r for r in Register}

def execute(controls: ControlLines, inf: RegFile,
        reverse_in_values: typing.List[int],
        out_values: typing.List[int]) -> typing.Tuple[NextStep, RegFile]:
    outf = dict(inf)
    mux_select = inf[SpecialRegister.MUX_SELECT]
    reg_out = inf[NUMBER_TO_REGISTER[mux_select]] & 1

    if ControlLine.ADD_A_TO_R in controls:
        outf[Register.R] = (inf[Register.R] + inf[Register.A]) & (1 << R_BITS) - 1
    if ControlLine.BANK_SWITCH in controls:
        outf[Register.L], outf[Register.LS] = inf[Register.LS], inf[Register.L]
        outf[Register.O1], outf[Register.O1S] = inf[Register.O1S], inf[Register.O1]
        outf[Register.O2], outf[Register.O2S] = inf[Register.O2S], inf[Register.O2]
    if ControlLine.LOAD_I0_FROM_INPUT in controls:
        outf[Register.I0] = reverse_in_values.pop()
    if ControlLine.SEND_Y_TO_OUTPUT in controls:
        out_values.append(inf[Register.Y])
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
        outf[SpecialRegister.Y_SELECT] = YSelect.X_MINUS_REG_OUT.value
    if ControlLine.ASSERT_X_IS_ABS_O1 in controls:
        assert abs(make_float(inf[Register.O1])) == make_float(abs(inf[Register.X]))
    if ControlLine.ASSERT_A_HIGH_ZERO in controls:
        assert (inf[Register.A] >> ALL_BITS) == 0
    if ControlLine.ASSERT_A_LOW_ZERO in controls:
        assert (inf[Register.A] & ((1 << ALL_BITS) - 1)) == 0
    if ControlLine.ASSERT_R_ZERO in controls:
        assert inf[Register.R] == 0
    if ControlLine.ASSERT_Y_IS_X_MINUS_L in controls:
        assert inf[Register.Y] == ((inf[Register.X] - inf[Register.L]) & ((1 << ALL_BITS) - 1))
    if ControlLine.SEND_O1_TO_OUTPUT in controls:
        out_values.append(inf[Register.O1])
    if ControlLine.SEND_L_TO_OUTPUT in controls:
        out_values.append(inf[Register.L])

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
        outf[Register.X] = (inf[Register.X] | (x_in << ALL_BITS)) >> 1
    if ControlLine.SHIFT_Y_RIGHT in controls:
        # Y register has a special function input (subtract)
        if inf[SpecialRegister.Y_SELECT] == YSelect.X_MINUS_REG_OUT.value:
            y_in = 4 + (inf[Register.X] & 1) - reg_out
            if y_in & 2:
                outf[SpecialRegister.Y_SELECT] = YSelect.BORROW_X_MINUS_REG_OUT.value
        elif inf[SpecialRegister.Y_SELECT] == YSelect.BORROW_X_MINUS_REG_OUT.value:
            y_in = 3 + (inf[Register.X] & 1) - reg_out
            if not (y_in & 2):
                outf[SpecialRegister.Y_SELECT] = YSelect.X_MINUS_REG_OUT.value
        else:
            assert False
        outf[Register.Y] = (inf[Register.Y] | (y_in << ALL_BITS)) >> 1

    if ((ControlLine.SET_MUX_BIT_1 in controls)
    or (ControlLine.SET_MUX_BIT_2 in controls)
    or (ControlLine.SET_MUX_BIT_4 in controls)
    or (ControlLine.SET_MUX_BIT_8 in controls)):
        outf[SpecialRegister.MUX_SELECT] = 0
        if ControlLine.SET_MUX_BIT_1 in controls:
            outf[SpecialRegister.MUX_SELECT] |= 1
        if ControlLine.SET_MUX_BIT_2 in controls:
            outf[SpecialRegister.MUX_SELECT] |= 2
        if ControlLine.SET_MUX_BIT_4 in controls:
            outf[SpecialRegister.MUX_SELECT] |= 4
        if ControlLine.SET_MUX_BIT_8 in controls:
            outf[SpecialRegister.MUX_SELECT] |= 8

    if ControlLine.RESTART in controls:
        return (NextStep.RESTART, outf)
    elif ControlLine.REPEAT_FOR_ALL_BITS in controls:
        outf[SpecialRegister.REPEAT_COUNTER] = (inf[SpecialRegister.REPEAT_COUNTER] + 1) % ALL_BITS
        if outf[SpecialRegister.REPEAT_COUNTER] != 0:
            return (NextStep.REPEAT, outf)

    return (NextStep.NEXT, outf)

def run_ops(ops: OperationList, in_values: typing.List[int], debug: bool) -> typing.List[int]:
    reg_file: RegFile = {}
    for r in Register:
        reg_file[r] = 0
    for sr in SpecialRegister:
        reg_file[sr] = 0
    op_index = 0
    out_values: typing.List[int] = []
    reverse_in_values = list(reversed(in_values))
    while op_index < len(ops):
        op = ops[op_index]
        if isinstance(op, ControlOperation):
            if debug:
                print(f"  op: {op_index} {op}")
            previous_reg_file = reg_file
            (next_step, reg_file) = execute(op.controls, previous_reg_file, reverse_in_values, out_values)
            if debug:
                for r in reg_file.keys():
                    if reg_file[r] != previous_reg_file[r]:
                        print(f"   reg {r.name}: {previous_reg_file[r]:08x} -> {reg_file[r]:08x}")

            if next_step == NextStep.RESTART:
                if len(reverse_in_values) == 0:
                    return out_values
                else:
                    op_index = 0
            elif next_step == NextStep.NEXT:
                op_index += 1
        else:
            if debug:
                print(f"  {op}")
            op_index += 1

    # Gone over the end of the program
    raise Exception("Program must end in RESTART")
        
def test_multiply_accumulate(r: random.Random, debug: int, num_multiply_tests: int) -> None:
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
        ops.add(ControlLine.RESTART)
        out_values = run_ops(ops, v0i_list, debug > 1)
        assert len(out_values) == 1
        ri = out_values[0]
        rf = make_float(ri)
        error = abs(rf - expect)
        if debug > 0:
            print(f" result {rf:1.6f} {ri:04x} expect {expect:1.6f} {make_fixed(expect):04x}")
            print(f" error {error:1.6f} ops {len(ops)} via_regs {via_regs}")
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
            ops.add(ControlLine.LOAD_I0_FROM_INPUT)
            filter_step(ops, a1, a2, b0, b2)
            move_reg_to_reg(ops, Register.I1, Register.I2)
            move_reg_to_reg(ops, Register.I0, Register.I1)
            ops.add(ControlLine.SEND_O1_TO_OUTPUT)
            expect_values.append(o0)
            o2 = o1
            o1 = o0
            i2 = i1
            i1 = i0

        #a0 =   1.006524e+00 a1 =  -1.967579e+00 a2 =   9.870374e-01 (double)
        #b0 =   6.481325e-03 b1 =   0.000000e+00 b2 =  -6.481325e-03 (double)
        #a0 =   1.005859e+00 a1 =  -1.966797e+00 a2 =   9.863281e-01 (fixed_t 9)
        #b0 =   5.859375e-03 b1 =   0.000000e+00 b2 =  -5.859375e-03 (fixed_t 9)

        ops.add(ControlLine.RESTART)
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
            if debug > 0:
                print(f" use abs(O1) =", end="")
        else:
            if debug > 0:
                print(f" use L       =", end="")
        if debug > 0:
            print(f" {expect_li:04x} X = {expect_xi:04x}")

        # Load input 
        inputs.append(o1i)
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)
        move_reg_to_reg(ops, Register.I0, Register.O1)
        inputs.append(li)
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)
        move_reg_to_reg(ops, Register.I0, Register.L)

        # do it
        set_X_to_abs_O1(ops)
        set_Y_to_X_minus_reg(ops, Register.L)
        move_X_to_L_if_Y_is_not_negative(ops)
        ops.add(ControlLine.SEND_L_TO_OUTPUT)
        ops.add(ControlLine.SEND_O1_TO_OUTPUT)
        move_reg_to_reg(ops, Register.X, Register.O1)
        ops.add(ControlLine.SEND_O1_TO_OUTPUT)
        ops.add(ControlLine.RESTART)

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

        # Generate test values
        xi = r.randrange(0, 1 << ALL_BITS)
        i0i = r.randrange(0, 1 << ALL_BITS)

        # Calculate expected result
        expect_yi = (xi - i0i) & ((1 << ALL_BITS) - 1)
        expect_bit = (expect_yi >> (ALL_BITS - 1))

        # Load input 
        inputs.append(xi)
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)
        move_reg_to_reg(ops, Register.I0, Register.X)
        inputs.append(i0i)
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)

        # Operation: Y = X - I0
        set_Y_to_X_minus_reg(ops, Register.I0)
        ops.add(ControlLine.SEND_Y_TO_OUTPUT)
        ops.add(ControlLine.RESTART)

        # run
        out_values = run_ops(ops, inputs, debug > 1)
        assert len(out_values) == 1
        result_yi = out_values[0]



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
        actual_y = out_values[(i * out_values_per_in_value) + 4]
        actual_out_bit = actual_y >> (ALL_BITS - 1)

        expect_upper_bandpass = expect_out_values[(i * out_values_per_in_value) + 0]
        expect_upper_rc = expect_out_values[(i * out_values_per_in_value) + 1]
        expect_lower_bandpass = expect_out_values[(i * out_values_per_in_value) + 2]
        expect_lower_rc = expect_out_values[(i * out_values_per_in_value) + 3]
        expect_out_bit = expect_out_values[(i * out_values_per_in_value) + 4] & 1

        if debug > 0:
            print(f"step {i} in {in_values[i]:04x}")
        for (name, expect, actual) in [
                    ("upper_bp", expect_upper_bandpass, actual_upper_bandpass),
                    ("upper_rc", expect_upper_rc, actual_upper_rc),
                    ("lower_bp", expect_lower_bandpass, actual_lower_bandpass),
                    ("lower_rc", expect_lower_rc, actual_lower_rc),
                ]:
            fexpect = make_float(expect)
            factual = make_float(actual)
            if debug > 0:
                print(f" {name} expect {expect:04x} {fexpect:8.5f}", end="")
                print(f" actual {actual:04x} {factual:8.5f} ", end="")
            error = abs(fexpect - factual)
            if debug > 0:
                print(f" error {error:1.6f}")
            assert error < VERY_SMALL_ERROR
        if debug > 0:
            error = expect_out_bit ^ actual_out_bit
            print(f" out bit  expect {expect_out_bit} actual {actual_out_bit} error {error} Y {actual_y:04x}")
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
    test_demodulator(debug, 100000)

if __name__ == "__main__":
    main()
