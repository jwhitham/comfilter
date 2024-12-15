
library comfilter;
use comfilter.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library comfilter;
use comfilter.all;
use comfilter.filter_unit_settings.all;

entity comfilter is
    generic (slow_clock_frequency : Real);
    port (
        fast_clock_in       : in std_logic;
        slow_clock_in       : in std_logic;
        reset_in            : in std_logic;

        -- Filter input
        audio_data_in       : in std_logic_vector (15 downto 0);
        audio_strobe_in     : in std_logic;

        -- Data output
        debug_serial_out    : out std_logic;
        data_out            : out std_logic_vector (DATA_BITS - 1 downto 0) := (others => '0');
        strobe_out          : out std_logic := '0');
end comfilter;

architecture structural of comfilter is
    signal serial_copy, serial_ready, serial_data : std_logic := '0';
begin

    ifu : entity filter_unit
        port map (clock_in => fast_clock_in,
                reset_in => reset_in,
                input_strobe_in => audio_strobe_in,
                input_data_in => audio_data_in,
                input_ready_out => open,
                restart_debug_out => open,
                serial_ready_out => serial_ready,
                serial_data_out => serial_data);

    process (fast_clock_in) is
    begin
        if fast_clock_in = '1' and fast_clock_in'event then
            if reset_in = '1' then
                serial_copy <= '1';
            elsif serial_ready = '1' then
                serial_copy <= serial_data;
            end if;
        end if;
    end process;

    debug_serial_out <= serial_copy;

    tcr : entity com_receiver
        generic map (
                baud_rate => BAUD_RATE,
                clock_frequency => slow_clock_frequency,
                num_data_bits => DATA_BITS)
        port map (
                serial_in => serial_copy,
                reset_in => reset_in,
                clock_in => slow_clock_in,
                data_out => data_out,
                strobe_out => strobe_out);

end structural;

