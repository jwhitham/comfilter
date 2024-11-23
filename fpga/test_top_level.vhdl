
library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

entity test_top_level is
end test_top_level;

architecture structural of test_top_level is

    constant ALL_BITS           : Natural := 16;
    signal done                 : std_logic := '0';
    signal clock                : std_logic := '0';
    signal reset                : std_logic := '0';
    signal verbose_debug        : std_logic := '0';

    signal input_value          : std_logic_vector(ALL_BITS - 1 downto 0) := (others => '0');
    signal input_strobe         : std_logic := '0';
    signal data_strobe          : std_logic := '0';
    signal data_value           : std_logic := '0';

begin
    test_signal_gen : entity test_signal_generator
        port map (done_out => done,
                clock_out => clock,
                verbose_debug_out => verbose_debug,
                strobe_out => input_strobe,
                value_out => input_value,
                reset_out => reset);

    test_filter_unit : entity filter_unit
        port map (clock_in => clock,
                reset_in => reset,
                verbose_debug_in => verbose_debug,
                input_strobe_in => input_strobe,
                input_data_in => input_value,
                serial_ready_out => data_strobe,
                serial_data_out => data_value);

    process is
        variable l : line;
        variable active : Boolean := false;
        variable copy : unsigned (1 downto 0) := "00";
    begin
        wait until reset = '0';
        while done = '0' loop
            wait until clock = '1' and clock'event;
            assert (data_strobe and input_strobe) = '0';
            if input_strobe = '1' then
                assert not active;
                active := true;
                write (l, String'("Data in = "));
                write (l, Integer'(ieee.numeric_std.to_integer(signed(input_value))));
                writeline (output, l);
            end if;
            if data_strobe = '1' then
                assert active;
                active := false;
                write (l, String'("Data out = "));
                copy (0) := data_value;
                write (l, Integer'(ieee.numeric_std.to_integer(signed(copy))));
                writeline (output, l);
            end if;
        end loop;
        write (l, String'("Reached the end"));
        writeline (output, l);
    end process;
end structural;

