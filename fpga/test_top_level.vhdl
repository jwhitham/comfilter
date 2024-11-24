
library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;
use settings.all;

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
    signal input_ready          : std_logic := '0';
    signal restart_debug        : std_logic := '0';
    signal data_strobe          : std_logic := '0';
    signal data_value           : std_logic := '0';

begin
    test_signal_gen : entity test_signal_generator
        port map (done_out => done,
                clock_out => clock,
                verbose_debug_out => verbose_debug,
                input_ready_in => input_ready,
                restart_debug_in => restart_debug,
                strobe_out => input_strobe,
                value_out => input_value,
                reset_out => reset);

    test_filter_unit : entity filter_unit
        port map (clock_in => clock,
                reset_in => reset,
                verbose_debug_in => verbose_debug,
                input_strobe_in => input_strobe,
                input_data_in => input_value,
                input_ready_out => input_ready,
                restart_debug_out => restart_debug,
                serial_ready_out => data_strobe,
                serial_data_out => data_value);

    process is
        variable l : line;
        variable copy : unsigned (1 downto 0) := "00";
        variable time_between_restarts : Natural := 0;
        variable time_between_inputs   : Natural := 0;
        constant deadline              : Natural := 2000;

        procedure print_times is
        begin
            write (l, String'("Time since last restart = "));
            write (l, time_between_restarts);
            writeline (output, l);
            write (l, String'("Time since last input = "));
            write (l, time_between_inputs);
            writeline (output, l);
        end print_times;
    begin
        wait until reset = '0';
        while done = '0' loop
            wait until clock = '1' and clock'event;
            assert (data_strobe and input_strobe) = '0';
            time_between_inputs := time_between_inputs + 1;
            time_between_restarts := time_between_restarts + 1;
            if input_ready = '1' and input_strobe = '1' then
                write (l, String'("DATA IN "));
                write (l, Integer'(ieee.numeric_std.to_integer(signed(input_value))));
                writeline (output, l);
                print_times;
                time_between_inputs := 0;
            end if;
            if input_ready = '0' and input_strobe = '1' then
                write (l, String'("ERROR - INPUT LOST "));
                write (l, Integer'(ieee.numeric_std.to_integer(signed(input_value))));
                writeline (output, l);
                print_times;
                write (l, String'("Data sent when filter was not ready for input"));
                writeline (output, l);
                assert False;
            end if;
            if time_between_inputs > deadline then
                write (l, String'("ERROR - DEADLINE MISS"));
                writeline (output, l);
                print_times;
                if input_ready = '1' then
                    write (l, String'("Deadline miss as test signal generator did not provide data"));
                    writeline (output, l);
                    assert False;
                else
                    write (l, String'("Deadline miss as filter did not become ready for input"));
                    writeline (output, l);
                    assert False;
                end if;
            end if;
            if data_strobe = '1' then
                write (l, String'("DATA OUT "));
                copy (0) := data_value;
                write (l, Integer'(ieee.numeric_std.to_integer(signed(copy))));
                writeline (output, l);
            end if;
            if restart_debug = '1' then
                write (l, String'("RESTART"));
                writeline (output, l);
                print_times;
                time_between_restarts := 0;
            end if;
        end loop;
        write (l, String'("Reached the end"));
        writeline (output, l);
    end process;
end structural;

