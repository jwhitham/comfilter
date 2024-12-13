
library comfilter;
use comfilter.all;

library ieee;
use ieee.std_logic_1164.all;

entity test_com_receiver is
end test_com_receiver;

architecture test_bench of test_com_receiver is

    constant baud_rate          : Real := 300.0;
    constant clock_frequency    : Real := 9600.0;
    constant one_bit_time       : Time := 1e9 ns / baud_rate;
    constant one_clock_time     : Time := 1e9 ns / clock_frequency;
    constant num_data_bits      : Natural := 40;
    signal clock                : std_logic := '0';
    signal reset                : std_logic := '0';
    signal done                 : std_logic := '0';
    signal expect_data          : std_logic := '0';
    signal strobe               : std_logic := '0';
    signal serial               : std_logic := '0';

    subtype t_data is std_logic_vector (num_data_bits - 1 downto 0);
    subtype t_crc is std_logic_vector (15 downto 0);
    signal test_pattern_1       : t_data := x"6654dbbc0a";
    signal test_pattern_2       : t_data := x"22ebd5cf7c";
    signal test_pattern_3       : t_data := x"c212151d13";
    signal crc_1                : t_crc := x"4073";
    signal crc_2                : t_crc := x"cfb1";
    signal crc_3                : t_crc := x"5a1f";
    signal data                 : t_data := (others => '0');

begin
    tcr : entity com_receiver
        generic map (
            baud_rate => baud_rate,
            clock_frequency => clock_frequency,
            num_data_bits => num_data_bits)
        port map (
            serial_in => serial,
            reset_in => reset,
            clock_in => clock,
            data_out => data,
            strobe_out => strobe);

    process is
    begin
        while done = '0' loop
            clock <= '0';
            wait for one_clock_time / 2;
            clock <= '1';
            wait for one_clock_time / 2;
        end loop;
        wait;
    end process;


    process is
    begin
        done <= '0';
        reset <= '1';
        serial <= '0';
        expect_data <= '0';
        wait for one_bit_time;
        reset <= '0';

        -- data input is low
        wait for one_bit_time * 100;

        -- begin break
        serial <= '1';
        wait for one_bit_time * 100;

        -- start bit
        serial <= '0';
        wait for one_bit_time;

        -- data bits
        for bit_index in 0 to num_data_bits - 1 loop
            serial <= test_pattern_1 (bit_index);
            wait for one_bit_time;
        end loop;

        -- crc bits
        for bit_index in 0 to 15 loop
            serial <= crc_1 (bit_index);
            wait for one_bit_time;
        end loop;

        -- Stop bit
        expect_data <= '1';
        serial <= '1';

        -- That's it! Should get some data soon
        wait for one_bit_time * 10;
        expect_data <= '0';
        wait until done = '1';
        wait;
    end process;

    process is
    begin
        -- Wait for all data to be sent to com_receiver
        loop
            wait until clock = '1' and clock'event;
            assert strobe = '0';
            exit when expect_data = '1';
        end loop;
        -- Wait for com_receiver to produce output
        loop
            wait until clock = '1' and clock'event;
            assert expect_data = '1';
            exit when strobe = '1';
        end loop;
        -- Check the output
        assert strobe = '1';
        assert data = test_pattern_1;
        -- Check that no further output is signalled
        loop
            wait until clock = '1' and clock'event;
            assert strobe = '0';
            exit when expect_data = '0';
        end loop;
        -- Finish testing
        done <= '1';
        wait;
    end process;

end architecture test_bench;
