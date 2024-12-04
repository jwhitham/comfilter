
from func_hardware import (
        OperationList, Register, ControlLine, Debug, MuxCode,
        ALL_BITS,
    )
from filter_implementation import (
        make_fixed, make_float,
        multiply_accumulate, filter_step, demodulator,
        multiply_accumulate_via_regs, move_reg_to_reg,
        set_X_to_abs_O1, set_Y_to_X_minus_reg,
        move_X_to_L_if_Y_is_not_negative,
    )
from pattern_test_implementation import (
        output_pattern_from_input,
    )
from settings import (
        FRACTIONAL_BITS, NON_FRACTIONAL_BITS, MICROOPS_TEST_SCALE, DEBUG,
    )
import func_execute
import random, typing, struct, sys

ACCEPTABLE_ERROR = (1.0 / (1 << (FRACTIONAL_BITS - 4)))
VERY_SMALL_ERROR = (1.0 / (1 << FRACTIONAL_BITS)) * 1.01
RunOps = typing.Callable[[OperationList, typing.List[int]], typing.List[int]]
MakeOps = typing.Callable[[], OperationList]


def test_output_pattern_from_input(run_ops: RunOps, make_ops: MakeOps) -> None:
    print("Test pattern generator", flush=True)

    ops = make_ops()
    output_pattern_from_input(ops)
    in_values = [0x55, 0x99, 0xfe, 0x41, 0xa5]
    out_values = run_ops(ops, in_values)
    assert len(out_values) == (len(in_values) * 11)
    out_bits = [bit >> (ALL_BITS - 1) for bit in out_values]
    j = 0
    for i in range(len(in_values)):
        assert out_bits[j] == 1     # initial state
        j += 1
        assert out_bits[j] == 0     # start bit
        j += 1
        for k in range(8):
            assert out_bits[j] == ((in_values[i] >> k) & 1)     # data bit
            j += 1
        assert out_bits[j] == 1     # stop bit
        j += 1

def test_repeat_and_reset(run_ops: RunOps, make_ops: MakeOps) -> None:
    print("Test repeat and reset", flush=True)

    # The program outputs the value that was loaded before it was restarted
    # This shows up problems with RESTART
    test_case_name = [
        "RESTART is followed by a second RESTART",
        "RESTART is followed by NOP",
        "RESTART immediately follows a NOP, and is the end of the program",
        "RESTART immediately follows a repeated NOP, and is the end of the program",
        "RESTART immediately follows a register move, and is the end of the program",
        ]
    for i in range(len(test_case_name)):
        title = f"Test case {i}: {test_case_name[i]}"
        if DEBUG > 0:
            print(title)

        ops = make_ops()
        ops.comment(title)
        # If the instruction at address 0 is repeated, then we see a failure
        # with i == 0 due to too many outputs:
        ops.debug(Debug.SEND_O1_TO_OUTPUT)
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)
        move_reg_to_reg(ops, Register.I0, Register.O1)

        # If RESTART doesn't work properly when followed by 0xff, or when preceded
        # by a repeat, we'll see a failure with i >= 2
        if i == 2:
            ops.add()
        elif i == 3:
            ops.add(ControlLine.REPEAT_FOR_ALL_BITS)
        ops.add(ControlLine.RESTART)

        if i == 0:
            ops.add(ControlLine.RESTART)
        elif i == 1:
            ops.add()
        in_values = [1, 2, 3]
        out_values = run_ops(ops, in_values)
        if DEBUG > 0:
            print(out_values)
        assert out_values == [0, 1, 2]

def test_multiply_accumulate(r: random.Random, num_multiply_tests: int, run_ops: RunOps, make_ops: MakeOps) -> None:
    print("Test multiply accumulate", flush=True)
    for i in range(num_multiply_tests):
        if DEBUG > 0:
            print(f"Test multiply accumulate {i}", flush=True)
        ops = make_ops()
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
                if DEBUG > 0:
                    print(f" + {v0f:1.6f} * {v1f:1.6f} = {v0i:04x} * {v1i:04x} = {expect:1.6f}")

                v1f_list.append(v1f)
                v0i_list.append(v0i)

        via_regs = (r.randrange(0, 2) == 0)
        if via_regs:
            multiply_accumulate_via_regs(ops, v1f_list)
        else:
            multiply_accumulate(ops, v1f_list)
        ops.add(ControlLine.RESTART)
        out_values = run_ops(ops, v0i_list)
        assert len(out_values) == 1
        ri = out_values[0]
        rf = make_float(ri)
        error = abs(rf - expect)
        if DEBUG > 0:
            print(f" result {rf:1.6f} {ri:04x} expect {expect:1.6f} {make_fixed(expect):04x}")
            print(f" error {error:1.6f} ops {len(ops)} via_regs {via_regs}")
        if via_regs:
            assert error < ACCEPTABLE_ERROR
        else:
            assert error < VERY_SMALL_ERROR

def test_bandpass_filter(r: random.Random, num_filter_tests: int, run_ops: RunOps, make_ops: MakeOps) -> None:
    print(f"Test bandpass filter", flush=True)
    for i in range(num_filter_tests):
        if DEBUG > 0:
            print(f"Test bandpass filter {i}", flush=True)
        ops = make_ops()
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
            if DEBUG > 1:
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
            ops.debug(Debug.SEND_O1_TO_OUTPUT)
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
        out_values = run_ops(ops, inputs)
        assert len(out_values) == len(inputs)
        assert len(expect_values) == len(inputs)
        for j in range(len(inputs)):
            ri = out_values[j]
            rf = make_float(ri)
            i0 = make_float(inputs[j])
            error = abs(rf - expect_values[j])
            if DEBUG > 0:
                print(f" step {j} input {i0:1.6f} result {rf:1.6f} expected {expect_values[j]:1.6f} error {error:1.6f}")
            assert error < ACCEPTABLE_ERROR

def test_move_X_to_L_if_Y_is_not_negative(r: random.Random, num_update_tests: int, run_ops: RunOps, make_ops: MakeOps) -> None:
    print("Test move X to L if Y is not negative", flush=True)
    for i in range(num_update_tests):
        ops = make_ops()
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
        if DEBUG > 0:
            print(f" O1 = {o1i:04x} L = {li:04x} X = {xi:04x} Y = {yi:04x}", end="")

        expect_li = li
        expect_xi = xi
        expect_o1i = o1i

        if yf >= 0.0:
            expect_li = xi
            if DEBUG > 0:
                print(f" use abs(O1) =", end="")
        else:
            if DEBUG > 0:
                print(f" use L       =", end="")
        if DEBUG > 0:
            print(f" {expect_li:04x} X = {expect_xi:04x}")

        # Load input 
        inputs.append(o1i)
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)
        move_reg_to_reg(ops, Register.I0, Register.O1)
        ops.comment(f"Expect O1 = {o1i:04x}")
        inputs.append(li)
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)
        move_reg_to_reg(ops, Register.I0, Register.L)
        ops.comment(f"Expect L = {li:04x}")

        # do it
        set_X_to_abs_O1(ops)
        ops.comment(f"Expect X = {xi:04x}")
        set_Y_to_X_minus_reg(ops, Register.L)
        ops.comment(f"Expect Y = {yi:04x}")
        move_X_to_L_if_Y_is_not_negative(ops)
        ops.comment("Test outputs")
        ops.debug(Debug.SEND_L_TO_OUTPUT)
        ops.debug(Debug.SEND_O1_TO_OUTPUT)
        move_reg_to_reg(ops, Register.X, Register.O1)
        ops.debug(Debug.SEND_O1_TO_OUTPUT)
        ops.add(ControlLine.RESTART)

        # run
        out_values = run_ops(ops, inputs)
        assert len(out_values) == 3

        result_li = out_values[0]
        result_o1i = out_values[1]
        result_xi = out_values[2]
        if DEBUG > 0:
            print(f" result L = {result_li:04x} result X = {result_xi:04x}")
        assert expect_li == result_li
        assert expect_o1i == result_o1i
        assert expect_xi == result_xi

def test_set_Y_to_X_minus_reg(r: random.Random, num_update_tests: int, run_ops: RunOps, make_ops: MakeOps) -> None:
    print("Test Y = X - reg", flush=True)
    for i in range(num_update_tests):
        ops = make_ops()
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
        out_values = run_ops(ops, inputs)
        assert len(out_values) == 1
        result_yi = out_values[0]



def test_demodulator(num_compare_tests: int, run_ops: RunOps, make_ops: MakeOps) -> None:
    print(f"Test demodulator", flush=True)
    ops = make_ops()
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

    out_values = run_ops(ops, in_values)
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

        if DEBUG > 0:
            print(f"step {i} in {in_values[i]:04x}")
        for (name, expect, actual) in [
                    ("upper_bp", expect_upper_bandpass, actual_upper_bandpass),
                    ("upper_rc", expect_upper_rc, actual_upper_rc),
                    ("lower_bp", expect_lower_bandpass, actual_lower_bandpass),
                    ("lower_rc", expect_lower_rc, actual_lower_rc),
                ]:
            fexpect = make_float(expect)
            factual = make_float(actual)
            if DEBUG > 0:
                print(f" {name} expect {expect:04x} {fexpect:8.5f}", end="")
                print(f" actual {actual:04x} {factual:8.5f} ", end="")
            error = abs(fexpect - factual)
            if DEBUG > 0:
                print(f" error {error:1.6f}")
            assert error < VERY_SMALL_ERROR
        if DEBUG > 0:
            error = expect_out_bit ^ actual_out_bit
            print(f" out bit  expect {expect_out_bit} actual {actual_out_bit} error {error} Y {actual_y:04x}")
        if expect_out_bit == actual_out_bit:
            correct += 1
   
    print(f"{correct} bits out of {len(in_values)} matched expectations")
    assert correct > (len(in_values) * 0.99)



def test_all(scale: int, run_ops: RunOps, make_ops: MakeOps) -> None:
    r = random.Random(3)
    test_output_pattern_from_input(run_ops, make_ops)
    test_repeat_and_reset(run_ops, make_ops)
    test_multiply_accumulate(r, scale * 10, run_ops, make_ops)
    test_bandpass_filter(r, scale * 10, run_ops, make_ops)
    test_move_X_to_L_if_Y_is_not_negative(r, scale * 10, run_ops, make_ops)
    test_set_Y_to_X_minus_reg(r, scale * 10, run_ops, make_ops)
    test_demodulator(scale * 4000, run_ops, make_ops)

def main() -> None:
    test_all(MICROOPS_TEST_SCALE, func_execute.run_ops, OperationList)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
