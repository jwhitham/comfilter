
library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

entity test_top_level is
end test_top_level;

architecture structural of test_top_level is

    signal done                : std_logic := '0';
    signal clock               : std_logic := '0';
    signal reset               : std_logic := '0';

    signal sample_value        : std_logic_vector(15 downto 0) := (others => '0');
    signal sample_strobe       : std_logic := '0';
    signal data_strobe         : std_logic := '0';
    signal data_value          : std_logic := '0';

begin
    test_signal_gen : entity test_signal_generator
        port map (done_out => done,
                clock_out => clock,
                strobe_out => sample_strobe,
                value_out => sample_value,
                reset_out => reset);

    test_filter_unit : entity filter_unit
        port map (clock_in => clock,
                reset_in => reset,
                audio_ready_in => sample_strobe,
                audio_data_in => sample_value,
                serial_ready_out => data_strobe,
                serial_data_out => data_value);

    process is
        variable l : line;
        variable active : Boolean := false;
        variable copy : unsigned (0 downto 0) := "0";
    begin
        wait until reset = '0';
        while done = '0' loop
            wait until clock = '1' and clock'event;
            assert (data_strobe and sample_strobe) = '0';
            if sample_strobe = '1' then
                assert not active;
                active := true;
                write (l, String'("Data in := "));
                write (l, Integer'(ieee.numeric_std.to_integer(signed(sample_value))));
                writeline (output, l);
            end if;
            if data_strobe = '1' then
                assert active;
                active := false;
                write (l, String'("Data out := "));
                copy (0) := data_value;
                write (l, Integer'(ieee.numeric_std.to_integer(signed(copy))));
                writeline (output, l);
            end if;
        end loop;
        write (l, String'("Reached the end"));
        writeline (output, l);
    end process;
end structural;

