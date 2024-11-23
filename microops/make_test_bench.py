
from settings import SAMPLE_RATE
from hardware import ALL_BITS
import typing, struct, math

CLOCK_FREQUENCY_HZ = 100e6

CLOCK_PERIOD_NS = int(math.floor(1e9 / CLOCK_FREQUENCY_HZ))
INTERSAMPLE_NS = (int(math.ceil((1e9 / SAMPLE_RATE) / CLOCK_PERIOD_NS) - 1.0) * CLOCK_PERIOD_NS)

def make_test_bench(in_values: typing.List[int], verbose: bool) -> None:
    # generate test bench
    with open("generated/test_signal_generator.vhdl", "wt") as fd:
        fd.write(f"""
library ieee;
use ieee.std_logic_1164.all;

use std.textio.all;

entity test_signal_generator is
    port (
        done_out            : out std_logic;
        clock_out           : out std_logic;
        strobe_out          : out std_logic;
        reset_out           : out std_logic;
        verbose_debug_out   : out std_logic;
        value_out           : out std_logic_vector({ALL_BITS - 1} downto 0)
    );
end test_signal_generator;

architecture structural of test_signal_generator is
    constant verbose : Boolean := {verbose};
    constant g : std_logic_vector(15 downto 0) := x"cccc";
    signal p : std_logic_vector(15 downto 0) := x"0000";
    signal done : std_logic := '0';
    signal clock : std_logic := '0';
    signal v : std_logic := '0';
begin
    value_out <= p({ALL_BITS - 1} downto 0);
    clock_out <= clock;
    done_out <= done;
    strobe_out <= v;
    verbose_debug_out <= '1' when verbose else '0';

    process
        variable l : line;
    begin
        while done = '0' loop
            clock <= '1';
            wait for {CLOCK_PERIOD_NS // 2} ns;
            clock <= '0';
            if verbose then
                write (l, String'("------"));
                writeline (output, l);
            end if;
            wait for {CLOCK_PERIOD_NS - (CLOCK_PERIOD_NS // 2)} ns;
        end loop;
        wait;
    end process;

    process
        variable l : line;
    begin
        done <= '0';
        reset_out <= '1';
        wait for {CLOCK_PERIOD_NS * 10} ns;
        reset_out <= '0';
        wait until clock = '1' and clock'event;
        wait until clock = '1' and clock'event;
""")
        for value in in_values:
            fd.write("""wait until clock = '1' and clock'event; """)
            fd.write(f"""p <= x"{value:04x}"; v <= '1'; """)
            fd.write("""wait until clock = '1' and clock'event; """)
            fd.write(f"""p <= g; v <= '0'; wait for {INTERSAMPLE_NS} ns;\n""")

        fd.write(f"""
        wait for {INTERSAMPLE_NS} ns;
        done <= '1';
        wait;
    end process;
end structural;
""")
