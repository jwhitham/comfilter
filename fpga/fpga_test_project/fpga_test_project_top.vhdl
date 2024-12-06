
library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;

entity fpga_test_project_top is
    port (
        clk12MHz            : in std_logic;

        test_A3             : in std_logic := '0';
        test_A2             : out std_logic := '0';
        test_A1             : out std_logic := '0';
        test_C3             : out std_logic := '0';
        test_D3             : out std_logic := '0';
        test_B1             : out std_logic := '0';

        lcol1               : out std_logic := '0';
        lcol2               : out std_logic := '0';
        lcol3               : out std_logic := '0';
        lcol4               : out std_logic := '0';
        led1                : out std_logic := '0';
        led2                : out std_logic := '0';
        led3                : out std_logic := '0';
        led4                : out std_logic := '0';
        led5                : out std_logic := '0';
        led6                : out std_logic := '0';
        led7                : out std_logic := '0';
        led8                : out std_logic := '0');
end fpga_test_project_top;

architecture structural of fpga_test_project_top is

    signal lcols            : std_logic_vector (3 downto 0) := "0000";
    signal lrows            : std_logic_vector (7 downto 0) := "00000000";
    signal clock            : std_logic := '0';

begin
    pll : entity fpga_test_project_pll
        port map (
              REFERENCECLK => clk12MHz,
              RESET => '1',
              PLLOUTCORE => open,
              PLLOUTGLOBAL => clock);
    fp : entity fpga_test_top_level
        port map (
            clock_in => clock,

            test_A3 => test_A3,
            test_A2 => test_A2,
            test_A1 => test_A1,
            test_C3 => test_C3,
            test_D3 => test_D3,
            test_B1 => test_B1,

            lcols_out => lcols,
            lrows_out => lrows);

    led1 <= lrows (7);
    led2 <= lrows (6);
    led3 <= lrows (5);
    led4 <= lrows (4);
    led5 <= lrows (3);
    led6 <= lrows (2);
    led7 <= lrows (1);
    led8 <= lrows (0);
    lcol1 <= lcols (3);
    lcol2 <= lcols (2);
    lcol3 <= lcols (1);
    lcol4 <= lcols (0);

end structural;

