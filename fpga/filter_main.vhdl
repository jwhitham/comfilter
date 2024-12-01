
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

library work;
use work.all;
use settings.all;

entity filter_main is
    port (
        clock_in            : in std_logic;

        test_A3             : out std_logic := '0';
        test_A2             : out std_logic := '0';
        test_A1             : out std_logic := '0';
        test_C3             : out std_logic := '0';
        test_D3             : out std_logic := '0';
        test_B1             : out std_logic := '0';

        -- LED outputs
        lcols_out           : out std_logic_vector (3 downto 0) := "0000";
        lrows_out           : out std_logic_vector (7 downto 0) := "00000000");
end filter_main;

architecture structural of filter_main is


    -- 4800 = 10kHz -> 2500 baud
    -- 1250 = 38.4kHz -> 9600 baud
    constant divider_period     : Natural := 1250;

    subtype reset_count_t is Natural range 0 to 15;
    signal reset_count          : reset_count_t := 15;
    subtype slow_count_t is Natural range 0 to divider_period - 1;
    signal slow_count           : slow_count_t := 0;
    signal clock_div            : std_logic := '0';
    signal clock_2              : std_logic := '0';
    signal reset                : std_logic := '1';
    signal test_A3_copy         : std_logic := '0';
    signal test_A2_copy         : std_logic := '0';
    signal test_C3_copy         : std_logic := '0';

    signal serial_ready         : std_logic := '0';
    signal serial_data          : std_logic := '0';
    signal input_value          : std_logic_vector(ALL_BITS - 1 downto 0) := (others => '0');
    signal input_strobe         : std_logic := '0';
    signal input_ready          : std_logic := '0';
    signal restart_debug        : std_logic := '0';
    signal data_strobe          : std_logic := '0';
    signal data_value           : std_logic := '0';
    signal i0_debug             : std_logic := '0';

    constant byte_array_size    : Natural := 8;
    subtype byte_t is std_logic_vector(7 downto 0);
    subtype byte_index_t is Natural range 0 to byte_array_size - 1;
    type byte_array_t is array (byte_index_t) of byte_t;
    signal input_index          : byte_index_t := 0;

    component SB_GB
        port (USER_SIGNAL_TO_GLOBAL_BUFFER:in std_logic;
                GLOBAL_BUFFER_OUTPUT:out std_logic);
    end component;

    constant input_rom : byte_array_t :=
        (0 => x"48",
         1 => x"65",
         2 => x"6c",
         3 => x"6c",
         4 => x"6f",
         5 => x"21",
         6 => x"0d",
         7 => x"0a");

begin
    ifu : entity filter_unit
        port map (clock_in => clock_div,
                reset_in => reset,
                input_strobe_in => input_strobe,
                input_data_in => input_value,
                input_ready_out => test_A3_copy,
                i0_debug_out => i0_debug,
                restart_debug_out => test_A2_copy,
                serial_ready_out => serial_ready,
                serial_data_out => serial_data);

    test_A3 <= test_A3_copy;
    test_A2 <= test_A2_copy;
    test_C3 <= test_C3_copy;

    test_A1 <= serial_ready;
    test_D3 <= i0_debug;
    test_B1 <= clock_div;
    lcols_out (0) <= '0';
    lcols_out (3 downto 1) <= (others => '1');
    lrows_out (0) <= not reset;
    lrows_out (1) <= not clock_div;
    lrows_out (2) <= not test_A3_copy;
    lrows_out (3) <= not test_A2_copy;
    lrows_out (4) <= not serial_ready;
    lrows_out (5) <= not test_C3_copy;
    lrows_out (6) <= not i0_debug;

    process (clock_div) is
    begin
        if clock_div = '1' and clock_div'event then
            if serial_ready = '1' then
                test_C3_copy <= serial_data;
            end if;
        end if;
    end process;

    process (clock_div) is
    begin
        if clock_div = '1' and clock_div'event then
            if test_A2_copy = '1' then
                if input_index = byte_array_size - 1 then
                    input_index <= 0;
                else
                    input_index <= input_index + 1;
                end if;
            end if;
        end if;
    end process;

    input_value(7 downto 0) <= input_rom (input_index);
    input_value(ALL_BITS - 1 downto 8) <= (others => '1');
    input_strobe <= '1';

    clock_buffer : SB_GB
        port map (
            USER_SIGNAL_TO_GLOBAL_BUFFER => clock_2, 
            GLOBAL_BUFFER_OUTPUT => clock_div);

    process (clock_in) is
    begin
        if clock_in = '1' and clock_in'event then
            if slow_count = 0 then
                clock_2 <= not clock_2;
                if clock_2 = '0' then
                    if reset_count = 0 then
                        reset <= '0';
                    else
                        reset <= '1';
                        reset_count <= reset_count - 1;
                    end if;
                end if;
                slow_count <= divider_period - 1;
            else
                slow_count <= slow_count - 1;
            end if;
        end if;
    end process;
end structural;

