
library comfilter;
use comfilter.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library comfilter;
use comfilter.all;
use filter_unit_settings.all;

entity receiver_main is
    port (
        clock_in            : in std_logic;

        serial_out          : out std_logic := '0';
        spdif_rx_in         : in std_logic;

        -- LED outputs
        lcols_out           : out std_logic_vector (3 downto 0) := "0000";
        lrows_out           : out std_logic_vector (7 downto 0) := "00000000");
end receiver_main;

architecture structural of receiver_main is

    -- reset, sync
    subtype reset_count_t is Natural range 0 to 15;
    signal reset_count          : reset_count_t := 15;
    signal reset                : std_logic := '1';
    signal sync                 : std_logic_vector(3 downto 0) := (others => '0');
    constant enabled            : std_logic := '1';

    -- biphase mark codes, decoded
    subtype t_pulse_length is std_logic_vector (1 downto 0);
    signal raw_pulse_length     : t_pulse_length := "00";

    -- serial S/PDIF data
    signal raw_packet_data      : std_logic := '0';
    signal raw_packet_shift     : std_logic := '0';
    signal raw_packet_start     : std_logic := '0';

    -- parallel audio data
    subtype t_data is std_logic_vector (31 downto 0);
    signal raw_data             : t_data := (others => '0');

    -- filter
    signal restart_debug        : std_logic := '0';
    signal serial_ready         : std_logic := '0';
    signal serial_data          : std_logic := '0';
    signal serial_copy          : std_logic := '0';
    signal input_value          : std_logic_vector(ALL_BITS - 1 downto 0) := (others => '0');
    signal input_strobe         : std_logic := '0';
    signal input_ready          : std_logic := '0';


begin
    sync (0) <= not reset;

    dec1 : entity input_decoder
        port map (clock_in => clock_in,
                  data_in => spdif_rx_in,
                  sync_in => sync (0),
                  sync_out => sync (1),
                  enable_123_check_in => enabled,
                  single_time_out => open,
                  pulse_length_out => raw_pulse_length);

    dec2 : entity packet_decoder
        port map (clock => clock_in,
                  pulse_length_in => raw_pulse_length,
                  sync_in => sync (1),
                  sync_out => sync (2),
                  data_out => raw_packet_data,
                  start_out => raw_packet_start,
                  shift_out => raw_packet_shift);

    dec3 : entity channel_decoder 
        port map (clock => clock_in,
                  data_in => raw_packet_data,
                  shift_in => raw_packet_shift,
                  start_in => raw_packet_start,
                  sync_in => sync (2),
                  sync_out => sync (3),
                  data_out => raw_data,
                  subcode_out => open,
                  left_strobe_out => input_strobe,
                  right_strobe_out => open);

    input_value (ALL_BITS - 1 downto ALL_BITS - NON_FRACTIONAL_BITS) <= (others => raw_data (27));
    input_value (ALL_BITS - NON_FRACTIONAL_BITS - 1 downto 0) <=
        raw_data (26 downto 27 - FRACTIONAL_BITS);

    ifu : entity filter_unit
        port map (clock_in => clock_in,
                reset_in => reset,
                input_strobe_in => input_strobe,
                input_data_in => input_value,
                input_ready_out => input_ready,
                restart_debug_out => restart_debug,
                serial_ready_out => serial_ready,
                serial_data_out => serial_data);

    lrows_out (0) <= serial_copy;
    lrows_out (1) <= not input_ready;
    lrows_out (2) <= not input_strobe;
    lrows_out (3) <= not restart_debug;
    lrows_out (4) <= not serial_ready;
    lrows_out (5) <= not sync (1);
    lrows_out (6) <= not sync (2);
    lrows_out (7) <= not sync (3);
    lcols_out (0) <= not raw_data(26);
    lcols_out (3 downto 1) <= (others => '1');
    serial_out <= serial_copy;

    process (clock_in) is
    begin
        if clock_in = '1' and clock_in'event then
            if reset = '1' then
                serial_copy <= '1';
            elsif serial_ready = '1' then
                serial_copy <= serial_data;
            end if;
        end if;
    end process;

    process (clock_in) is
    begin
        if clock_in = '1' and clock_in'event then
            if reset_count = 0 then
                reset <= '0';
            else
                reset <= '1';
                reset_count <= reset_count - 1;
            end if;
        end if;
    end process;

end structural;

