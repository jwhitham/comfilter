
from settings import (
        UPPER_FREQUENCY,
        LOWER_FREQUENCY,
        BAUD_RATE,
        FRACTIONAL_BITS,
        RC_DECAY_PER_BIT,
        FILTER_WIDTH,
        SAMPLE_RATE,
    )
from hardware import (
        get_shift_line, get_mux_lines,
        OperationList, Register, ControlLine,
        ALL_BITS, A_BITS, R_BITS,
    )

import enum, math, typing

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
    if negative:
        ivalue |= ((1 << ALL_BITS) - 1) << ALL_BITS
    # print(f"Multiplication with value {value:1.6f} fixed encoding {ivalue:04x}")

    # Clear high A bits
    ops.comment(f"Multiplication begins: {source.name} * {value:1.6f} ({ivalue:04x})")
    ops.add(get_mux_lines(Register.ZERO))
    ops.add(ControlLine.SHIFT_A_RIGHT, ControlLine.REPEAT_FOR_ALL_BITS)

    # If negative, also clear the low bits, as these will be added during shift-in
    if negative:
        ops.add(ControlLine.SHIFT_A_RIGHT, ControlLine.REPEAT_FOR_ALL_BITS)

    ops.add(ControlLine.ASSERT_A_HIGH_ZERO)
    if negative:
        ops.add(ControlLine.ASSERT_A_LOW_ZERO)

    # Configure source
    ops.add(get_mux_lines(source))

    ops.add(ControlLine.SHIFT_A_RIGHT)

    # Do the first part of the multiplication, shifting data in from the source register
    # Leave the final source register bit in place (sign extend)
    for i in range(ALL_BITS - 1):
        ivalue = ivalue << 1
        if ivalue & (1 << A_BITS):
            ops.add(ControlLine.ADD_A_TO_R, get_shift_line(source))
        else:
            ops.add(get_shift_line(source))

        ops.add(ControlLine.SHIFT_A_RIGHT)

    # Do the second part of the multiplication, now that everything from the source register is present
    for i in range(A_BITS - (ALL_BITS - 1)):
        ivalue = ivalue << 1
        if ivalue & (1 << A_BITS):
            ops.add(ControlLine.ADD_A_TO_R, ControlLine.SHIFT_A_RIGHT)
        else:
            ops.add(ControlLine.SHIFT_A_RIGHT)


    # Final bit shifted
    ops.add(get_shift_line(source))

    ops.comment(f"Multiplication complete: {source.name} * {value:1.6f}")

def move_R_to_reg(ops: OperationList, target: Register) -> None:
    # Discard low bits of R
    for i in range(FRACTIONAL_BITS):
        ops.add(ControlLine.SHIFT_R_RIGHT, get_mux_lines(Register.R))

    # Move result bits of R to target
    ops.add(ControlLine.SHIFT_R_RIGHT, get_shift_line(target),
            ControlLine.REPEAT_FOR_ALL_BITS)

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

    ops.add(get_mux_lines(source))
    ops.add(get_shift_line(target), get_shift_line(source), ControlLine.REPEAT_FOR_ALL_BITS,
            ControlLine.SET_X_IN_TO_REG_OUT)

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
    ops.comment("set X = abs(O1)")
    ops.add(ControlLine.SET_X_IN_TO_ABS_O1_REG_OUT, get_mux_lines(Register.O1))
    ops.add(ControlLine.SHIFT_X_RIGHT, ControlLine.SHIFT_O1_RIGHT, ControlLine.REPEAT_FOR_ALL_BITS)

    ops.add(ControlLine.ASSERT_X_IS_ABS_O1)

def set_Y_to_X_minus_reg(ops: OperationList, source: Register) -> None:
    # Operation: Y = X - reg
    ops.comment(f"set Y = X - {source.name}")
    ops.add(ControlLine.SET_X_IN_TO_X, ControlLine.SET_Y_IN_TO_X_MINUS_REG_OUT,
            get_mux_lines(source))
    ops.add(ControlLine.SHIFT_X_RIGHT, ControlLine.SHIFT_Y_RIGHT,
            get_shift_line(source), ControlLine.REPEAT_FOR_ALL_BITS)

def move_X_to_L_if_Y_is_not_negative(ops: OperationList) -> None:
    # if Y is non-negative, then X >= L: so, set L = X = X
    # if Y is negative, then X < L: so, set X = X
    ops.comment("if Y >= 0 then set L = X")
    ops.add(ControlLine.SET_MUX_L_OR_X)
    ops.add(ControlLine.SHIFT_L_RIGHT, ControlLine.SHIFT_X_RIGHT,
            ControlLine.REPEAT_FOR_ALL_BITS, ControlLine.SET_X_IN_TO_X)

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
    ops.comment(f"Begin multiply_accumulate with {test_values}")
    ops.add(ControlLine.ASSERT_R_ZERO)

    # Multiply and add repeatedly
    for test_value in test_values:
        ops.add(ControlLine.LOAD_I0_FROM_INPUT)
        fixed_multiply(ops, Register.I0, test_value)

    ops.comment("Output from multiply_accumulate")
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
