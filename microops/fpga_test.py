
from fpga_hardware import (
        FPGAOperationList,
    )
from func_hardware import (
        ALL_BITS, OperationList,
    )
from settings import (
        DEBUG, SERIAL_PORT,
    )
from filter_implementation import (
        demodulator,
    )
from test_vector import (
        TestVector,
    )

from pathlib import Path
import typing, sys, struct, math
import serial


class TestError(Exception):
    pass

def sync(ser: serial.Serial) -> None:
    while True:
        # flush input
        data = ser.read(100)
        if len(data) > 10:
            raise TestError("Receiving garbage!")
            sys.exit(1)
        if len(data):
            print("Discarded:", repr(data))

        # send test
        ser.write(b"12")
        data = ser.read(2)
        if data == b"12":
            return

def main() -> None:
    print("Create demodulator")
    ops = FPGAOperationList()
    demodulator(ops)
    ops.generate()

    print("Read test vector")
    test_vector = TestVector(1 << 30)


    print("Open serial port", flush=True)
    ser = serial.serial_for_url(SERIAL_PORT, do_not_open=True, exclusive=True)
    ser.baudrate = 115200
    ser.bytesize = 8
    ser.parity = "N"
    ser.stopbits = 1
    ser.rtscts = False
    ser.timeout = 2.0

    try:
        ser.open()
    except serial.SerialException as e:
        raise TestError("Serial setup error " + str(e))
        sys.exit(1)

    print("Synchronise", flush=True)
    sync(ser)
    

    max_block_size = 100
    out_values = []
    for i in range(0, len(test_vector.in_values), max_block_size):
        print(f"Data capture {i}", flush=True)
        block = []
        block_size = min(max_block_size, len(test_vector.in_values) - i)
        for j in range(i, i + block_size):
            block.append(b"T")
            block.append(struct.pack(">H", test_vector.in_values[j]))

        ser.write(b"".join(block))
        data = ser.read(block_size)

        for value in data:
            if value == 0:
                out_values.append(0)
            elif value == 1:
                out_values.append(1)
            else:
                raise TestError(f"Received unexpected byte {value:02x}")

        if len(data) != block_size:
            raise TestError(f"Expected {block_size} bytes, received {len(data)}")


    print("Compare", flush=True)
    out_vector = test_vector.substitute_new_out_bits(out_values)
    compare_demodulator_output(test_vector, out_vector)
            

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
