
library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

entity test_top_level is
end test_top_level;

architecture structural of test_top_level is

    signal clock                : std_logic := '0';
    signal reset                : std_logic := '0';
    signal sample_value         : std_logic_vector(14 downto 0) := (others => '0');
    signal sample_value_neg     : std_logic := '0';
    signal sample_strobe        : std_logic := '0';
    signal filter_value         : std_logic_vector(10 downto 0) := (others => '0');
    signal filter_value_neg     : std_logic := '0';
    signal filter_finish        : std_logic := '0';
    signal filter_ready         : std_logic := '0';

begin
    test_signal_gen : entity test_signal_generator
        port map (done_out => done,
                clock_out => clock,
                strobe_out => sample_strobe,
                value_out => sample_value,
                value_negative_out => sample_value_neg,
                reset_out => reset);

end structural;

