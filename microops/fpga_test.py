
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

    print("Read test vector")
    expect_out_values = []
    in_values = []
    out_values_per_in_value = 5
    with open("generated/test_vector", "rb") as fd:
        test_vector_format = "<I" + ("I" * out_values_per_in_value)
        test_vector_size = struct.calcsize(test_vector_format)
        test_vector_shift = 32 - (NON_FRACTIONAL_BITS + FRACTIONAL_BITS)
        test_vector_data = fd.read(test_vector_size)
        while len(test_vector_data) == test_vector_size:
            fields = struct.unpack(test_vector_format, test_vector_data)
            in_values.append(fields[0] >> test_vector_shift)
            expect_out_values.append((fields[out_values_per_in_value] >> test_vector_shift) & 1)
            test_vector_data = fd.read(test_vector_size)

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
    for i in range(0, len(in_values), max_block_size):
        print(f"Begin test {i}", flush=True)
        block = []
        block_size = min(max_block_size, len(in_values) - i)
        for j in range(i, i + block_size):
            block.append(b"T")
            block.append(struct.pack(">H", in_value)))

        ser.write(b"".join(block)
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

            
    with open(GHDL_OUTPUT, "wb") as fd:
        rc = subprocess.call(["ghdl", "-r", "test_top_level"] + RFLAGS,
                stdin=subprocess.DEVNULL, stdout=fd, cwd=FPGA_DIR)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
