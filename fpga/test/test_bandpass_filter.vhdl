
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
    signal sample_value        : std_logic_vector(14 downto 0) := (others => '0');
    signal sample_value_neg    : std_logic := '0';
    signal sample_strobe       : std_logic := '0';
    signal filter_value        : std_logic_vector(10 downto 0) := (others => '0');
    signal filter_value_neg    : std_logic := '0';
    signal filter_finish       : std_logic := '0';
    signal filter_ready        : std_logic := '0';

begin
    test_signal_gen : entity test_signal_generator
        port map (done_out => done,
                  clock_out => clock,
                  strobe_out => sample_strobe,
                  value_out => sample_value,
                  value_negative_out => sample_value_neg,
                  reset_out => reset);

    filter : entity bandpass_filter
        generic map (
            sample_width => 15,
            result_width => 11,
            frequency => 1270.0,
            filter_width => 100.0,
            sample_rate => 48000.0)
        port map (
            value_in => sample_value,
            value_negative_in => sample_value_neg,
            result_out => filter_value,
            result_negative_out => filter_value_neg,
            start_in => sample_strobe,
            reset_in => reset,
            finish_out => filter_finish,
            ready_out => filter_ready,
            clock_in => clock);


    process is
        variable l : line;
        variable active : Boolean := false;
        variable saved : std_logic_vector (14 downto 0) := (others => '0');
        variable saved_neg : std_logic := '0';
        variable counter : Integer := 0;
    begin
        wait until reset = '0';
        while done = '0' loop
            wait until clock = '1' and clock'event;
            assert not (sample_strobe = '1' and filter_finish = '1');
            if sample_strobe = '1' then
                assert not active;
                saved := sample_value;
                saved_neg := sample_value_neg;
                active := true;
                if filter_ready = '0' then
                    write (l, String'("Filter not ready!"));
                    writeline (output, l);
                    assert false;
                end if;
            end if;
            if filter_finish = '1' then
                assert active;
                write (l, Integer'(counter));
                write (l, String'(" "));
                if saved_neg = '1' then
                    write (l, String'("-"));
                end if;
                write (l, Integer'(ieee.numeric_std.to_integer(unsigned(saved))));
                write (l, String'(" "));
                if filter_value_neg = '1' then
                    write (l, String'("-"));
                end if;
                write (l, Integer'(ieee.numeric_std.to_integer(unsigned(filter_value))));
                writeline (output, l);
                active := false;
                counter := counter + 1;
            end if;
        end loop;
        write (l, String'("Reached the end"));
        writeline (output, l);
    end process;
end structural;

