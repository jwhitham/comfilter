

num_bits = 8
for in_value in range(1 << num_bits):
    expect = ((1 << num_bits) - in_value) & ((1 << num_bits) - 1)
    copy = in_value
    out_value = 0
    b = 0
    for i in range(num_bits):
        a = copy & 1
        c = 4 - b - a

        out_value = out_value >> 1
        out_value |= (c & 1) << (num_bits - 1)
        b = (c & 2) >> 1
        copy = copy >> 1
        
    print(f"-{in_value:02x} = {out_value:02x} expect {expect:02x}")
    assert out_value == expect
    assert ((out_value + in_value) & ((1 << num_bits) - 1)) == 0
