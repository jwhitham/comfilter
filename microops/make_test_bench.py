
from hardware import ALL_BITS
import typing, struct, math

CLOCK_FREQUENCY_HZ = 100e6

CLOCK_PERIOD_NS = int(math.floor(1e9 / CLOCK_FREQUENCY_HZ))

def make_test_bench(in_values: typing.List[int]) -> None:
    # generate test bench
    with open("generated/test_signal_generator.vhdl", "wt") as fd:
        fd.write(f"""
library ieee;
use ieee.std_logic_1164.all;

use std.textio.all;

library work;
use work.all;
use settings.all;

entity test_signal_generator is
    port (
        done_out            : out std_logic;
        clock_out           : out std_logic;
        strobe_out          : out std_logic;
        reset_out           : out std_logic;
        input_ready_in      : in std_logic;
        restart_debug_in    : in std_logic;
        value_out           : out std_logic_vector({ALL_BITS - 1} downto 0)
    );
end test_signal_generator;

architecture structural of test_signal_generator is
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
