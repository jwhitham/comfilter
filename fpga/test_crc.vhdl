library comfilter;
use comfilter.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use debug_textio.all;

entity test_crc is
end entity test_crc;

architecture test_bench of test_crc is


    signal clock        : std_logic := '0';
    signal reset        : std_logic := '0';
    signal strobe       : std_logic := '0';
    signal data         : std_logic := '0';
    signal crc16_value  : std_logic_vector (15 downto 0) := (others => '0');
    signal crc32_value  : std_logic_vector (31 downto 0) := (others => '0');
    signal done         : std_logic := '0';
begin
    subject32 : entity crc
        port map (
            clock_in => clock,
            reset_in => reset,
            strobe_in => strobe,
            data_in => data,
            crc_out => crc32_value);

    subject16 : entity crc
        generic map (
            bit_width => 16,
            polynomial => 16#8005#,
            flip => false)
        port map (
            clock_in => clock,
            reset_in => reset,
            strobe_in => strobe,
            data_in => data,
            crc_out => crc16_value);

    process is
    begin
        while done = '0' loop
            clock <= '0';
            wait for 1 us;
            clock <= '1';
            wait for 1 us;
        end loop;
        wait;
    end process;

    process is
        variable copy_value : std_logic_vector(15 downto 0);
    begin
        -- initial state
        done <= '0';
        reset <= '1';
        strobe <= '0';
        data <= '0';
        wait until clock = '1' and clock'event;
        wait until clock = '1' and clock'event;
        reset <= '0';
        assert crc16_value = x"0000";
        assert crc32_value = x"00000000";

        -- data: ASCII characters '1' to '9'
        for byte_value in 16#31# to 16#39# loop
            for bit_index in 0 to 7 loop
                if ((byte_value / (2 ** bit_index)) mod 2) = 1 then
                    data <= '1';
                else
                    data <= '0';
                end if;
                strobe <= '1';
                wait until clock = '1' and clock'event;
            end loop;
        end loop;

        -- test the output
        strobe <= '0';
        wait until clock = '1' and clock'event;
        
        assert crc32_value = x"CBF43926";
        assert crc16_value = x"BB3D";

        -- test the output after appending the CRC
        copy_value := crc16_value;
        for bit_index in 0 to 15 loop
            data <= copy_value (bit_index);
            strobe <= '1';
            wait until clock = '1' and clock'event;
        end loop;

        -- test the output (should be 0)
        strobe <= '0';
        wait until clock = '1' and clock'event;
        assert crc16_value = x"0000";

        done <= '1';
        wait;
    end process;

end test_bench;

