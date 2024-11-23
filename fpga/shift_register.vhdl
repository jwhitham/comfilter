

library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

entity shift_register is
    generic (
        name        : String;
        size        : Natural);
    port (
        reg_out             : out std_logic := '0';
        negative_out        : out std_logic := '0';
        shift_right_in      : in std_logic := '0';
        reg_in              : in std_logic := '0';
        clock_in            : in std_logic := '0');
end shift_register;

architecture structural of shift_register is
    signal value : std_logic_vector(size - 1 downto 0);
begin
    process (clock_in) is
        variable l : line;
    begin
        if clock_in = '1' and clock_in'event then
            if shift_right_in = '1' then
                value(size - 1) <= reg_out;
                value(size - 2 downto 0) <= value(size - 1 downto 1);
                write (l, name);
                write (l, String'(" := "));
                write (l, Integer'(ieee.numeric_std.to_integer(signed(value)));
                writeline (output, l);
            end if;
        end if;
    end process;

    reg_out <= value(0);
    negative_out <= value(size - 1);

end structural;

