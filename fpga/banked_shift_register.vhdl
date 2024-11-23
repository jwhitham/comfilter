

library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

entity banked_shift_register is
    generic (
        name        : String;
        size        : Natural);
    port (
        reg_out             : out std_logic := '0';
        negative_out        : out std_logic := '0';
        shift_right_in      : in std_logic := '0';
        bank_select_in      : in std_logic := '0';
        reg_in              : in std_logic := '0';
        clock_in            : in std_logic := '0');
end banked_shift_register;

architecture structural of banked_shift_register is
    signal reg_b0, negative_b0, shift_b0 : std_logic := '0';
    signal reg_b1, negative_b1, shift_b1 : std_logic := '0';
begin
    b0 : entity shift_register
        generic map (name => name & "0", size => size)
        port map (
            reg_out => reg_b0,
            negative_out => negative_b0,
            shift_right_in => shift_b0,
            reg_in => reg_in,
            clock_in => clock_in);

    b1 : entity shift_register
        generic map (name => name & "1", size => size)
        port map (
            reg_out => reg_b1,
            negative_out => negative_b1,
            shift_right_in => shift_b1,
            reg_in => reg_in,
            clock_in => clock_in);

    reg_out <= reg_b0 when bank_select_in = '0' else reg_b1;
    negative_out <= negative_b0 when bank_select_in = '0' else negative_b1;
    shift_b0 <= shift_right_in when bank_select_in = '0' else '0';
    shift_b1 <= shift_right_in when bank_select_in = '1' else '0';
end structural;
