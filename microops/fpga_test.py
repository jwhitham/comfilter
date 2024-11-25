
from fpga_hardware import (
        FPGAOperationList,
    )
from hardware import (
        ALL_BITS,
    )
import filtertest, make_test_bench

from pathlib import Path
import subprocess, typing, sys

RFLAGS = ["--assert-level=note"]
FPGA_DIR = Path("fpga").absolute()
GHDL_OUTPUT = Path("generated/ghdl_output.txt").absolute()

def fpga_run_ops(ops: FPGAOperationList, in_values: typing.List[int], debug: bool) -> typing.List[int]:
    ops.generate()
    make_test_bench.make_test_bench(in_values=in_values, verbose=debug)
    subprocess.check_call(["ghdl", "--remove"], cwd=FPGA_DIR)
    subprocess.check_call(["ghdl", "-a", "--work=work",
            "../generated/control_line_decoder.vhdl",
            "../generated/microcode_store.test.vhdl",
            "../generated/test_signal_generator.vhdl",
            "../generated/settings.vhdl",
            "shift_register.vhdl",
            "banked_shift_register.vhdl",
            "subtractor.vhdl",
            "filter_unit.vhdl",
            "test_top_level.vhdl",
            ], cwd=FPGA_DIR)
            
    with open(GHDL_OUTPUT, "wb") as fd:
        rc = subprocess.call(["ghdl", "-r", "test_top_level"] + RFLAGS,
                stdin=subprocess.DEVNULL, stdout=fd, cwd=FPGA_DIR)

    out_values: typing.List[int] = []
    mask = (1 << ALL_BITS) - 1
    with open(GHDL_OUTPUT, "rt", encoding="utf-8") as fd:
        for line in fd:
            if debug or (rc != 0):
                print(line, end="")
            fields = line.split()
            if (len(fields) == 5) and (fields[0] == "Debug") and (fields[1] == "out") and (fields[3] == "="):
                out_values.append((int(fields[4]) + mask + 1) & mask)

    if rc != 0:
        sys.exit(1)

    print(end="", flush=True)
    return out_values

def main() -> None:
    scale = 1
    debug = 0
    filtertest.test_all(scale, debug, fpga_run_ops, FPGAOperationList)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
