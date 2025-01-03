
from fpga_hardware import (
        FPGAOperationList,
    )
from func_hardware import (
        ALL_BITS, OperationList,
    )
from settings import (
        GHDL_TEST_SCALE, DEBUG, FILTER_UNIT_PREFIX,
    )
import func_test

from pathlib import Path
import subprocess, typing, sys, struct, math

RFLAGS = ["--assert-level=note"]
FPGA_DIR = Path("fpga").absolute()
GHDL_OUTPUT = Path("generated/ghdl_output.txt").absolute()
CLOCK_FREQUENCY_HZ = 100e6
CLOCK_PERIOD_NS = int(math.floor(1e9 / CLOCK_FREQUENCY_HZ))

def make_test_bench(in_values: typing.List[int], prefix: str) -> None:
    # generate test bench
    with open(f"generated/{prefix}_signal_generator.vhdl", "wt") as fd:
        fd.write(f"""
library ieee;
use ieee.std_logic_1164.all;


library comfilter;
use comfilter.all;
use {prefix}_settings.all;
use debug_textio.all;

entity {prefix}_signal_generator is
    port (
        done_out            : out std_logic;
        clock_out           : out std_logic;
        strobe_out          : out std_logic;
        reset_out           : out std_logic;
        input_ready_in      : in std_logic;
        restart_debug_in    : in std_logic;
        value_out           : out std_logic_vector({ALL_BITS - 1} downto 0)
    );
end {prefix}_signal_generator;

architecture structural of {prefix}_signal_generator is
    constant g : std_logic_vector(15 downto 0) := x"cccc";
    signal p : std_logic_vector(15 downto 0) := x"0000";
    signal done : std_logic := '0';
    signal clock : std_logic := '0';
    signal v, c, r : std_logic := '0';
begin
    value_out <= p({ALL_BITS - 1} downto 0);
    clock_out <= clock;
    strobe_out <= v;
    c <= clock;
    r <= input_ready_in;
    done_out <= done;

    process
        variable l : line;
    begin
        while done = '0' loop
            clock <= '1';
            wait for {CLOCK_PERIOD_NS // 2} ns;
            clock <= '0';
            if VERBOSE_DEBUG then
                write (l, String'("------"));
                writeline (output, l);
            end if;
            wait for {CLOCK_PERIOD_NS - (CLOCK_PERIOD_NS // 2)} ns;
        end loop;
        clock <= '1';
        wait for {CLOCK_PERIOD_NS // 2} ns;
        clock <= '0';
        wait;
    end process;

    process
        variable l : line;
    begin
        done <= '0';
        reset_out <= '1';
        wait for {CLOCK_PERIOD_NS * 10} ns;
        reset_out <= '0';
        wait until c = '1' and c'event;
""")
        for value in in_values:
            fd.write("""wait until r = '1' and c = '1' and c'event; """)
            fd.write(f"""p <= x"{value:04x}"; v <= '1'; """)
            fd.write("""wait until c = '1' and c'event; """)
            fd.write(f"""p <= g; v <= '0'; wait until r = '0' and c = '1' and c'event;\n""")

        fd.write(f"""
        if VERBOSE_DEBUG then
            write (l, String'("end of test data - waiting for restart_debug_in"));
            writeline (output, l);
        end if;
        wait until restart_debug_in = '1' and c = '1' and c'event;
        if VERBOSE_DEBUG then
            write (l, String'("end of test data - setting done = 1"));
            writeline (output, l);
        end if;
        done <= '1';
        wait;
    end process;
end structural;
""")

def ghdl_run_ops(ops: OperationList, in_values: typing.List[int]) -> typing.List[int]:
    prefix = FILTER_UNIT_PREFIX
    ops.generate(prefix)
    make_test_bench(in_values=in_values, prefix=prefix)
    subprocess.check_call(["ghdl", "--remove"], cwd=FPGA_DIR)
    subprocess.check_call(["ghdl", "-a", "--work=comfilter",
            "debug_textio.vhdl",
            "debug_textio-body.vhdl",
            f"../generated/{prefix}_settings.vhdl",
            f"../generated/{prefix}_control_line_decoder.vhdl",
            f"../generated/{prefix}_microcode_store.test.vhdl",
            f"../generated/{prefix}_signal_generator.vhdl",
            "shift_register.vhdl",
            "banked_shift_register.vhdl",
            "subtractor.vhdl",
            "filter_unit.vhdl",
            "ghdl_test_top_level.vhdl",
            ], cwd=FPGA_DIR)
            
    with open(GHDL_OUTPUT, "wb") as fd:
        rc = subprocess.call(["ghdl", "-r", "--work=comfilter", "ghdl_test_top_level"] + RFLAGS,
                stdin=subprocess.DEVNULL, stdout=fd, cwd=FPGA_DIR)

    out_values: typing.List[int] = []
    mask = (1 << ALL_BITS) - 1
    end_ok = False
    with open(GHDL_OUTPUT, "rt", encoding="utf-8") as fd:
        for line in fd:
            if (DEBUG > 1) or (rc != 0):
                print(line, end="")
            fields = line.split()
            if (len(fields) == 5) and (fields[0] == "Debug") and (fields[1] == "out") and (fields[3] == "="):
                out_values.append((int(fields[4]) + mask + 1) & mask)
            if (len(fields) == 2) and (fields[0] == "THE") and (fields[1] == "END"):
                end_ok = True

    if rc != 0:
        sys.exit(1)
    if not end_ok:
        print("Output does not contain 'THE END'")
        sys.exit(1)

    print(end="", flush=True)
    return out_values

def main() -> None:
    func_test.test_all(GHDL_TEST_SCALE, ghdl_run_ops, FPGAOperationList)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
