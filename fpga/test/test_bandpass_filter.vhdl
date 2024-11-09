
library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

entity test_bandpass_filter is
end test_bandpass_filter;

architecture structural of test_bandpass_filter is

    signal done                : std_logic := '0';
    signal clock               : std_logic := '0';
    signal reset               : std_logic := '0';
    signal sample_value        : std_logic_vector(15 downto 0) := (others => '0');
    signal sample_strobe       : std_logic := '0';
    signal filter_value        : std_logic_vector(8 downto 0) := (others => '0');
    signal filter_finish       : std_logic := '0';
    signal filter_ready        : std_logic := '0';

begin
    test_signal_gen : entity test_signal_generator
        port map (done_out => done,
                  clock_out => clock,
                  strobe_out => sample_strobe,
                  value_out => sample_value,
                  reset_out => reset);

    filter : entity bandpass_filter
        generic map (
            sample_width => 16,
            result_width => 9,
            frequency => 21500.0,
            filter_width => 1000.0,
            sample_rate => 48000.0)
        port map (
            value_in => sample_value,
            result_out => filter_value,
            start_in => sample_strobe,
            reset_in => reset,
            finish_out => filter_finish,
            ready_out => filter_ready,
            clock_in => clock);


    process is
        variable l : line;
        variable valid : Boolean := false;
        variable saved : std_logic_vector (15 downto 0) := (others => '0');
        variable counter : Integer := 0;
    begin
        wait until reset = '0';
        while done = '0' loop
            wait until clock = '1' and clock'event;
            if sample_strobe = '1' then
                saved := sample_value;
                valid := true;
                if filter_ready = '0' then
                    write (l, String'("Filter not ready!"));
                    writeline (output, l);
                    assert false;
                end if;
            end if;
            if filter_finish = '1' then
                assert valid;
                write (l, Integer'(counter));
                write (l, String'(" "));
                write (l, Integer'(ieee.numeric_std.to_integer(signed(saved))));
                write (l, String'(" "));
                write (l, Integer'(ieee.numeric_std.to_integer(signed(filter_value))));
                writeline (output, l);
                valid := false;
                counter := counter + 1;
            end if;
        end loop;
        write (l, String'("Reached the end"));
        writeline (output, l);
    end process;
end structural;

