
import enum

class ABSRSelect(enum.Enum):
    PASSTHROUGH = enum.auto()
    NEGATE = enum.auto()
    BORROW = enum.auto()


num_bits = 8
for in_value in range(1 << num_bits):
    expect = ((1 << num_bits) - in_value) & ((1 << num_bits) - 1)
    copy = in_value
    out_value = 0
    if False:
        b = 0
        for i in range(num_bits):
            a = copy & 1
            c = 4 - b - a

            out_value = out_value >> 1
            out_value |= (c & 1) << (num_bits - 1)
            b = (c & 2) >> 1
            copy = copy >> 1
    else:
        absr_select = ABSRSelect.NEGATE
        for i in range(num_bits):
            reg_out = copy & 1
            copy = copy >> 1

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

            out_value = out_value >> 1
            out_value |= (absr_in & 1) << (num_bits - 1)
        
    print(f"-{in_value:02x} = {out_value:02x} expect {expect:02x}")
    assert out_value == expect
    assert ((out_value + in_value) & ((1 << num_bits) - 1)) == 0
