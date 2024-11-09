
import typing, struct

CLOCK_PERIOD_NS = 10
INTERSAMPLE_NS = CLOCK_PERIOD_NS * 99

def print_banner(fd: typing.IO, banner: str) -> None:
    fd.write("""write (l, String'("{}")); writeline (output, l);\n""".format(banner))

def wav_to_test_data(fd: typing.IO, wav_file_name: str) -> None:
    state_change_time: typing.List[float] = []
    print_banner(fd, "Start of {}".format(wav_file_name))
    with open(wav_file_name, "rb") as fd2:
        fd2.seek(0x2c, 0) # skip to start of data
        while True:
            data = fd2.read(2)
            if len(data) == 0:
                break
            (sample, ) = struct.unpack("<H", data)
            fd.write(f"""p <= x"{sample:04x}"; v <= '1'; """)
            fd.write(f"""wait for {CLOCK_PERIOD_NS} ns; """)
            fd.write(f"""v <= '0'; wait for {INTERSAMPLE_NS} ns;\n""")

def main() -> None:
    # generate test bench
    with open("test/generated/test_signal_generator.vhdl", "wt") as fd:
        fd.write(f"""
library ieee;
use ieee.std_logic_1164.all;

use std.textio.all;

entity test_signal_generator is
    port (
        done_out            : out std_logic;
        clock_out           : out std_logic;
        reset_out           : out std_logic;
        strobe_out          : out std_logic;
        value_out           : out std_logic_vector(15 downto 0)
    );
end test_signal_generator;

architecture structural of test_signal_generator is
    signal p : std_logic_vector(15 downto 0) := x"0000";
    signal done : std_logic := '0';
    signal clock : std_logic := '0';
    signal v : std_logic := '0';
begin
    value_out <= p;
    clock_out <= clock;
    done_out <= done;
    strobe_out <= v;

    process
    begin
        while done = '0' loop
            clock <= '1'; wait for {CLOCK_PERIOD_NS // 2} ns;
            clock <= '0'; wait for {CLOCK_PERIOD_NS - (CLOCK_PERIOD_NS // 2)} ns;
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
""")
        # read input files
        wav_to_test_data(fd, "test/generated/signal.wav")

        fd.write("""
        done <= '1';
        wait;
    end process;
end structural;
""")

if __name__ == "__main__":
    main()
