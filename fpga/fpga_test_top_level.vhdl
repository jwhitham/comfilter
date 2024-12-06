
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library work;
use work.all;
use settings.all;

entity fpga_test_top_level is
    port (
        clock_in            : in std_logic;

        test_A3             : in std_logic := '0';  -- serial input
        test_A2             : out std_logic := '0';  -- serial output
        test_A1             : out std_logic := '0';  -- state machine READY or LOAD_LOW
        test_C3             : out std_logic := '0';  -- state machine LOAD_LOW or LOAD_HIGH
        test_D3             : out std_logic := '0';  -- last serial bit from filter
        test_B1             : out std_logic := '0';  -- waiting

        -- LED outputs
        lcols_out           : out std_logic_vector (3 downto 0) := "0000";
        lrows_out           : out std_logic_vector (7 downto 0) := "00000000");
end fpga_test_top_level;

architecture structural of fpga_test_top_level is

    subtype reset_count_t is Natural range 0 to 15;
    signal reset_count          : reset_count_t := 15;
    signal reset                : std_logic := '1';

    signal serial_ready         : std_logic := '0';
    signal serial_data          : std_logic := '0';
    signal input_value          : std_logic_vector(ALL_BITS - 1 downto 0) := (others => '0');
    signal input_strobe         : std_logic := '0';
    signal input_ready          : std_logic := '0';
    signal restart_debug        : std_logic := '0';

    signal uart_data_in         : std_logic_vector (7 downto 0) := (others => '0');
    signal uart_strobe_in       : std_logic := '0';
    signal uart_data_out        : std_logic_vector (7 downto 0) := (others => '0');
    signal uart_strobe_out      : std_logic := '0';
    signal uart_ready_out       : std_logic := '0';

    signal count                : unsigned(3 downto 0) := 0;

    type test_state_t is (READY, LOAD_LOW, LOAD_HIGH, WAIT_RESULT);
    signal test_state           : test_state_t := READY;
begin
    ifu : entity filter_unit
        port map (clock_in => clock_in,
                reset_in => reset,
                input_strobe_in => input_strobe,
                input_data_in => input_value,
                input_ready_out => input_ready,
                restart_debug_out => restart_debug,
                serial_ready_out => serial_ready,
                serial_data_out => serial_data);

    u : entity uart 
        generic map (
            clock_frequency => 96.0e6,
            baud_rate => 115200.0)
        port map (
            data_in => uart_data_in,
            strobe_in => uart_strobe_in,
            data_out => uart_data_out,
            strobe_out => uart_strobe_out,
            ready_out => uart_ready_out,
            reset_in => reset,
            serial_in => test_A3,
            serial_out => test_A2,
            clock_in => clock_in);

    process (clock_in) is
    begin
        if clock_in = '1' and clock_in'event then
            uart_strobe_in <= '0';
            input_strobe <= '0';
            test_A1 <= '0';
            test_C3 <= '0';
            test_B1 <= '0';
            case test_state is
                when READY =>
                    test_A1 <= '1';
                    if uart_strobe_out = '1' then
                        lrows_out <= not uart_data_out;
                        if uart_data_out = x"54" then -- T -> begin test
                            if input_ready = '1' then
                                uart_data_in <= x"00"; -- initial state
                                test_state <= LOAD_HIGH;
                            else
                                uart_data_in <= x"66"; -- f -> fail (not ready)
                                uart_strobe_in <= '1';
                            end if;
                        else
                            uart_data_in <= uart_data_out; -- echo
                            uart_strobe_in <= '1';
                        end if;
                    end if;
                when LOAD_HIGH =>
                    test_C3 <= '1';
                    if uart_strobe_out = '1' then
                        lrows_out <= not uart_data_out;
                        input_value (15 downto 8) <= uart_data_out;
                        input_value (7 downto 0) <= uart_data_out;
                        test_state <= LOAD_LOW;
                    end if;
                when LOAD_LOW =>
                    test_A1 <= '1';
                    test_C3 <= '1';
                    if uart_strobe_out = '1' then
                        lrows_out <= not uart_data_out;
                        input_value (7 downto 0) <= uart_data_out;
                        input_strobe <= '1'; -- should start processing
                        count <= 0;
                        test_state <= WAIT_RESULT;
                    end if;
                when WAIT_RESULT =>
                    test_B1 <= '1';
                    if serial_ready = '1' then -- got a bit, shift it
                        uart_data_in (7 downto 1) <= uart_data_in (6 downto 0);
                        uart_data_in (0) <= serial_data;
                        lrows_out (7 downto 1) <= not uart_data_in (6 downto 0);
                        lrows_out (0) <= not serial_data;
                        if count /= 15 then
                            count <= count + 1;
                        end if;
                        test_D3 <= serial_data;
                    end if;
                    if restart_debug = '1' then -- rebooted
                        lrows_out <= not uart_data_in;
                        if count = 0 then
                            uart_data_in <= x"6e"; -- n -> no data
                        elsif count = 15 then
                            uart_data_in <= x"6f"; -- o -> overwhelming data
                        end if;
                        uart_strobe_in <= '1';
                        test_state <= READY;
                    end if;
                    if uart_strobe_out = '1' then -- aborted
                        lrows_out <= not uart_data_in;
                        uart_data_in <= x"61"; -- a -> aborted
                        uart_strobe_in <= '1';
                        test_state <= READY;
                    end if;
            end case;
            if reset = '1' then
                test_state <= READY;
            end if;
        end if;
    end process;

    lcols_out (0) <= '0';
    lcols_out (3 downto 1) <= (others => '1');

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

