library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity test_subtractor is
end test_subtractor;

use std.textio.all;

architecture test of test_subtractor is

    type t_test is record
        value_width : Natural;
        slice_width : Natural;
        do_addition : Boolean;
    end record;

    type t_test_table is array (Positive range <>) of t_test;

    constant test_table     : t_test_table :=
       ((4, 4, false), (4, 2, false), (4, 1, false), (4, 3, false),
        (6, 6, false), (5, 3, false), (1, 1, false), (2, 8, false),
        (4, 4, true),  (4, 2, true),  (4, 1, true),  (4, 3, true),
        (6, 6, true),  (5, 3, true),  (1, 1, true),  (2, 8, true),
        (3, 4, true),  (3, 4, false), (3, 5, true),  (3, 5, false),
        (3, 9, true),  (3, 9, false), (3, 8, true),  (3, 8, false));
    constant num_tests      : Natural := test_table'Length;

    signal clock            : std_logic := '0';
    signal done             : std_logic_vector (0 to num_tests) := (others => '0');
begin

    process
    begin
        done (0) <= '1';
        wait for 500 ns;
        while done (num_tests) /= '1' loop
            clock <= '1';
            wait for 500 ns;
            clock <= '0';
            wait for 500 ns;
        end loop;
        wait;
    end process;

    stest : for part in test_table'Range generate

        constant value_width    : Natural := test_table (part).value_width;
        constant slice_width    : Natural := test_table (part).slice_width;
        constant do_addition    : Boolean := test_table (part).do_addition;
        constant min_value      : Integer := -(2 ** (value_width - 1));
        constant max_value      : Integer := (2 ** (value_width - 1)) - 1;
        constant wrap_value     : Integer := 2 ** value_width;

        signal top_value        : std_logic_vector (value_width - 1 downto 0) := (others => '0');
        signal bottom_value     : std_logic_vector (value_width - 1 downto 0) := (others => '0');
        signal start            : std_logic := '0';
        signal reset            : std_logic := '0';
        signal finish           : std_logic := '0';
        signal overflow         : std_logic := '0';
        signal result           : std_logic_vector (value_width - 1 downto 0) := (others => '0');
    begin
        sub : entity subtractor
            generic map (value_width => value_width,
                         slice_width => slice_width,
                         do_addition => do_addition)
            port map (
                top_value_in => top_value,
                bottom_value_in => bottom_value,
                start_in => start,
                reset_in => reset,
                finish_out => finish,
                result_out => result,
                overflow_out => overflow,
                clock_in => clock);
            
        process
            variable expect : Integer;
            variable expect_overflow : std_logic;
            variable l : line;
        begin
            done (part) <= '0';
            wait until done (part - 1) = '1';

            write (l, String'("subtractor test "));
            write (l, part);
            writeline (output, l);

            reset <= '1';
            start <= '0';
            top_value <= (others => '0');
            bottom_value <= (others => '0');
            wait for 10 us;

            reset <= '0';
            wait until clock'event and clock = '1';

            outer : for top in min_value to max_value loop
                top_value <= std_logic_vector (to_signed (top, value_width));

                for bottom in min_value to max_value loop
                    bottom_value <= std_logic_vector (to_signed (bottom, value_width));
                    start <= '1';
                    wait until clock'event and clock = '1';
                    start <= '0';
                    while finish = '0' loop
                        wait until clock'event and clock = '1';
                    end loop;

                    expect_overflow := '0';
                    if do_addition then
                        expect := top + bottom;
                    else
                        expect := top - bottom;
                    end if;
                    if expect > max_value then
                        expect := expect - wrap_value;
                        expect_overflow := '1';
                    end if;
                    if expect < min_value then
                        expect := expect + wrap_value;
                        expect_overflow := '1';
                    end if;
                    if std_logic_vector (to_signed (expect, value_width)) /= result
                            or expect_overflow /= overflow then
                        if do_addition then
                            write (l, String'("Adder error. "));
                            write (l, top);
                            write (l, String'(" + "));
                        else
                            write (l, String'("Subtractor error. "));
                            write (l, top);
                            write (l, String'(" - "));
                        end if;
                        write (l, bottom);
                        write (l, String'(" should be "));
                        write (l, expect);
                        write (l, String'(" got "));
                        write (l, to_integer (signed (result)));
                        if expect_overflow /= overflow then
                            if expect_overflow = '1' then
                                write (l, String'(" overflow flag should be set"));
                            else
                                write (l, String'(" overflow flag should be clear"));
                            end if;
                        end if;
                        writeline (output, l);
                        assert False;
                        exit outer;
                    end if;
                end loop;
            end loop outer;
            done (part) <= '1';
            wait;
        end process;
    end generate stest;

end test;
