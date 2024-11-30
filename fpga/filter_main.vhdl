
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

    subtype cycle_count_t is Natural range 0 to 7;
    signal cycle                : cycle_count_t := 7;
    subtype reset_count_t is Natural range 0 to 15;
    signal reset_count          : reset_count_t := 15;
    subtype slow_count_t is Natural range 0 to 4799;
    signal slow_count           : slow_count_t := 0;
    signal clock                : std_logic := '0';
    signal clock_2              : std_logic := '0';
    signal dummy                : std_logic := '0';
    signal reset                : std_logic := '1';
    signal test_A3_copy         : std_logic := '0';
    signal test_A2_copy         : std_logic := '0';
    signal test_C3_copy         : std_logic := '0';

    signal serial_ready         : std_logic := '0';
    signal serial_data          : std_logic := '0';
    signal input_ready          : std_logic := '0';
    signal restart_debug        : std_logic := '0';
    signal data_strobe          : std_logic := '0';
    signal data_value           : std_logic := '0';
    signal serial_shift_register: std_logic_vector(7 downto 0) := (others => '0');
    signal uc_code              : std_logic_vector(7 downto 0) := (others => '0');

    signal uc_addr      : unsigned(UC_ADDR_BITS - 1 downto 0) := (others => '1');
    signal uc_enable    : std_logic := '1';

    component microcode_store is port (
            uc_data_out : out std_logic_vector (7 downto 0) := (others => '0');
            uc_addr_in  : in std_logic_vector (8 downto 0) := (others => '0');
            enable_in   : in std_logic := '0';
            clock_in    : in std_logic := '0');
    end component microcode_store;
begin
    store : microcode_store 
        port map (
                uc_data_out => uc_code,
                uc_addr_in => std_logic_vector(uc_addr),
                enable_in => uc_enable,
                clock_in => clock_2);

    uc_enable <= '1';

    process (clock_2) is
    begin
        if clock_2 = '1' and clock_2'event then
            test_A2_copy <= '0';
            test_A3_copy <= serial_shift_register(0);
            test_C3_copy <= '0';

            if cycle = 0 then
                serial_shift_register <= uc_code;
                uc_addr <= uc_addr + 1;
                test_A2_copy <= '1';
                cycle <= 7;
                if uc_addr = 0 then
                    test_C3_copy <= '1';
                end if;
            else
                cycle <= cycle - 1;
                serial_shift_register (6 downto 0) <= serial_shift_register (7 downto 1);
                serial_shift_register (7) <= '1';
            end if;
        end if;
    end process;
                    
    test_A3 <= test_A3_copy;
    test_A2 <= test_A2_copy;
    test_A1 <= serial_ready;
    test_C3 <= test_C3_copy;
    test_D3 <= reset;
    test_B1 <= clock_2;

    lcols_out (0) <= '0';
    lcols_out (3 downto 1) <= (others => '1');
    lrows_out (0) <= reset;
    lrows_out (1) <= clock_2;
    lrows_out (2) <= test_A3_copy;
    lrows_out (3) <= test_A2_copy;
    lrows_out (4) <= serial_ready;
    lrows_out (5) <= test_C3_copy;
    lrows_out (6) <= dummy;

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
                    dummy <= not dummy;
                end if;
                slow_count <= 4799;
            else
                slow_count <= slow_count - 1;
            end if;
        end if;
    end process;
end structural;

