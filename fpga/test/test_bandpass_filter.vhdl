
library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

entity test_bandpass_filter is
end test_bandpass_filter;

architecture structural of test_bandpass_filter is

    signal done                : std_logic := '0';
    signal clock               : std_logic := '0';
    signal value_negative      : std_logic := '0';
    signal value               : std_logic_vector(14 downto 0) := (others => '0');

begin
    test_signal_gen : entity test_signal_generator
        port map (done_out => done,
                  clock_out => clock,
                  value_negative_out => value_negative,
                  value_out => value);


end structural;

