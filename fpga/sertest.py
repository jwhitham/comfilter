

import serial
import sys

PORT = "COM3"

def sync(ser: serial.Serial) -> None:
    while True:
        # flush input
        data = ser.read(100)
        if len(data) > 10:
            print("Receiving garbage!")
            sys.exit(1)
        if len(data):
            print("Discarded:", repr(data))

        # send test
        ser.write(b"123")
        data = ser.read(4)
        if data == b"123":
            return

def main() -> None:
    ser = serial.serial_for_url(PORT, do_not_open=True, exclusive=True)
    ser.baudrate = 115200
    ser.bytesize = 8
    ser.parity = "N"
    ser.stopbits = 1
    ser.rtscts = False
    ser.timeout = 0.5

    try:
        ser.open()
    except serial.SerialException as e:
        print("Setup error", str(e))
        sys.exit(1)

    print(f"connected to {PORT}", flush=True)
    sync(ser)
    
    print("connected to FPGA", flush=True)
    ser.write(b"T\x00\x00")
    data = ser.read(1)
    if data == b"":
        print("No data received from FPGA within timeout", flush=True)
    else:
        print("Result: {:02x}".format(data[0]))

    sync(ser)

if __name__ == "__main__":
    main()
