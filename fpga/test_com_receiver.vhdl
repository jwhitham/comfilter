
library comfilter;
use comfilter.all;
use filter_unit_settings.all;

library ieee;
use ieee.std_logic_1164.all;

entity test_com_receiver is
end test_com_receiver;

architecture test_bench of test_com_receiver is

    constant clock_frequency    : Real := 9600.0;
    constant one_bit_time       : Time := 1e9 ns / BAUD_RATE;
    constant one_clock_time     : Time := 1e9 ns / clock_frequency;
    constant num_data_bits      : Natural := 40;
    signal clock                : std_logic := '0';
    signal reset                : std_logic := '0';
    signal done                 : std_logic := '0';
    signal expect_data          : std_logic := '0';
    signal strobe               : std_logic := '0';
    signal serial               : std_logic := '0';
    signal done2                : std_logic := '0';
    signal serial2              : std_logic := '0';
    signal start2               : std_logic := '0';
    signal strobe2              : std_logic := '0';

    subtype t_data is std_logic_vector (num_data_bits - 1 downto 0);
    subtype t_crc is std_logic_vector (15 downto 0);
    signal test_pattern_1       : t_data := x"6654dbbc0a";
    signal test_pattern_2       : t_data := x"22ebd5cf7c";
    signal test_pattern_3       : t_data := x"c212151d13";
    signal crc_1                : t_crc := x"4073";
    signal crc_2                : t_crc := x"cfb1";
    signal crc_3                : t_crc := x"5a1f";
    signal data                 : t_data := (others => '0');

    subtype t_data2 is std_logic_vector (DATA_BITS - 1 downto 0);
    signal data2                : t_data2 := (others => '0');

begin
    tcr : entity com_receiver
        generic map (
            baud_rate => BAUD_RATE,
            clock_frequency => clock_frequency,
            num_data_bits => num_data_bits)
        port map (
            serial_in => serial,
            reset_in => reset,
            clock_in => clock,
            data_out => data,
            strobe_out => strobe);

    tcr2 : entity com_receiver
        generic map (
            baud_rate => baud_rate,
            clock_frequency => clock_frequency,
            num_data_bits => DATA_BITS)
        port map (
            serial_in => serial2,
            reset_in => reset,
            clock_in => clock,
            data_out => data2,
            strobe_out => strobe2);

    tcr2signal : entity test_packet_signal
        port map (
            start_in => start2,
            data_out => serial2,
            done_out => done2);

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
        variable i : Natural := 0;
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
        wait for one_bit_time;
        expect_data <= '0';

        -- start bit
        serial <= '0';
        wait for one_bit_time;

        -- data bits
        for bit_index in 0 to num_data_bits - 1 loop
            serial <= test_pattern_2 (bit_index);
            wait for one_bit_time;
        end loop;

        -- crc bits
        for bit_index in 0 to 15 loop
            serial <= crc_2 (bit_index);
            wait for one_bit_time;
        end loop;

        -- Stop bit
        expect_data <= '1';
        serial <= '1';
        wait for one_bit_time;
        expect_data <= '0';

        -- Send noisy garbage for a while
        i := 0;
        for j in 1 to (16 * num_data_bits) loop
            serial <= test_pattern_2 (i) xor test_pattern_1 (i);
            wait for one_bit_time / 16;
            i := (i + 1) mod num_data_bits;
        end loop;

        -- begin break
        serial <= '1';
        wait for one_bit_time * 30;

        -- start bit
        serial <= '0';
        wait for one_bit_time;
        expect_data <= '0';

        -- data bits
        for bit_index in 0 to num_data_bits - 1 loop
            serial <= test_pattern_3 (bit_index);
            wait for one_bit_time;
        end loop;

        -- crc bits
        for bit_index in 0 to 15 loop
            serial <= crc_3 (bit_index);
            wait for one_bit_time;
        end loop;

        -- Stop bit
        expect_data <= '1';
        serial <= '1';
        wait for one_bit_time;
        expect_data <= '0';

        -- That's it! All three test patterns should have been received now
        wait until done = '1';
        wait;
    end process;

    process is
    begin
        while done = '0' loop
            wait until clock = '1' and clock'event;
            if strobe = '1' then
                assert expect_data = '1';
                assert data = test_pattern_1 or data = test_pattern_2 or data = test_pattern_3;
            end if;
        end loop;
        wait;
    end process;

    process is
    begin
        start2 <= '0';
        -- Wait for all data to be sent to com_receiver
        wait until clock = '1' and clock'event and expect_data = '1';
        -- Wait for com_receiver to produce output
        wait until clock = '1' and clock'event and strobe = '1';
        -- Check the output
        assert data = test_pattern_1;
        -- Wait for expect_data to go to '0'
        wait until clock = '1' and clock'event and expect_data = '0';

        -- Wait for all data to be sent to com_receiver
        wait until clock = '1' and clock'event and expect_data = '1';
        -- Wait for com_receiver to produce output
        wait until clock = '1' and clock'event and strobe = '1';
        -- Check the output
        assert data = test_pattern_2;
        -- Wait for expect_data to go to '0'
        wait until clock = '1' and clock'event and expect_data = '0';

        -- Wait for all data to be sent to com_receiver
        wait until clock = '1' and clock'event and expect_data = '1';
        -- Wait for com_receiver to produce output
        wait until clock = '1' and clock'event and strobe = '1';
        -- Check the output
        assert data = test_pattern_3;
        -- Wait for expect_data to go to '0'
        wait until clock = '1' and clock'event and expect_data = '0';

        -- Finish testing (part 1)
        start2 <= '1';

        -- Wait for strobe from part 2
        assert done2 = '0';
        wait until clock = '1' and clock'event and strobe2 = '1';
        assert data2 = x"c001"; -- matches test_com_receiver.sh
        wait until clock = '1' and clock'event;
        assert strobe2 = '0';
        wait until done2 = '1';

        -- End of part 2
        done <= '1';
        wait;
    end process;

end architecture test_bench;
