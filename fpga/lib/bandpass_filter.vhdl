-- Configurable bandpass filter

library work;
use work.all;
use std.textio.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std."+";
use ieee.numeric_std."*";
use ieee.math_real."**";
use ieee.numeric_std."/";
use ieee.numeric_std."-";
use ieee.numeric_std.all;

entity bandpass_filter is
    generic (
        sample_width        : Natural;       -- Bit width of sample data (samples are 2s-complement)
        result_width        : Natural;       -- Output width
        frequency           : Real;          -- Centre of pass band (Hz)
        filter_width        : Real;          -- Width of pass band (Hz)
        sample_rate         : Real;          -- Sample rate to assume for calculations (Hz)
        slice_width         : Natural := 8); -- Bit width of adders and subtractors
    port (
        value_in            : in std_logic_vector (sample_width - 1 downto 0);
        result_out          : out std_logic_vector (result_width - 1 downto 0);
        start_in            : in std_logic;
        reset_in            : in std_logic;
        finish_out          : out std_logic := '0';
        ready_out           : out std_logic := '0';
        clock_in            : in std_logic
    );
end bandpass_filter;

architecture structural of bandpass_filter is

    -- Filter configuration constants as real numbers
    constant w0         : Real := 2.0 * ieee.math_real.math_pi * frequency / sample_rate;
    constant alpha      : Real := ieee.math_real.sin(w0) / (2.0 * frequency / filter_width);
    constant a0         : Real := 1.0 + alpha;
    constant b0         : Real := alpha / a0; -- b1 is always zero!
    constant b2         : Real := (-alpha) / a0;
    constant a1         : Real := (-2.0 * ieee.math_real.cos(w0)) / a0;
    constant a2         : Real := (1.0 - alpha) / a0;

    -- Fixed point conversion
    constant nonfractional_bits : Natural := 2; -- fixed point number represents [-2, +2)
    constant fractional_bits    : Natural := result_width;
    constant small_fixed_width  : Natural := nonfractional_bits + fractional_bits;
    subtype small_fixed_t is std_logic_vector (small_fixed_width - 1 downto 0);
    function to_small_fixed (n : Real) return small_fixed_t is
        variable n1 : Real := n;
        variable negate : Boolean := false;
        variable n2 : Integer := 0;
    begin
        if n1 < 0.0 then
            n1 := -n1;
            negate := true;
        end if;
        n2 := Integer (ieee.math_real.floor((n1 * (2.0 ** (Real (fractional_bits)))) + 0.5));
        if negate then
            n2 := -n2;
        end if;
        return std_logic_vector (ieee.numeric_std.to_signed (n2, small_fixed_width));
    end to_small_fixed;
    
    -- Filter configuration constants converted to fixed point
    constant a1_fixed   : small_fixed_t := to_small_fixed(a1);
    constant a2_fixed   : small_fixed_t := to_small_fixed(a2);
    constant b0_fixed   : small_fixed_t := to_small_fixed(b0);
    constant b2_fixed   : small_fixed_t := to_small_fixed(b2);

    -- Large fixed width type is the result from multiplication
    constant large_fixed_width   : Natural := small_fixed_width * 2;
    constant large_fixed_left    : Natural := large_fixed_width - nonfractional_bits - 1;
    constant large_fixed_right   : Natural := large_fixed_left + 1 - small_fixed_width;
    subtype large_fixed_t is std_logic_vector (large_fixed_width - 1 downto 0);

    -- Signals
    signal i0_b0_finish         : std_logic := '0';
    signal i0_b0_ready          : std_logic := '0';
    signal i2_b2_finish         : std_logic := '0';
    signal i2_b2_ready          : std_logic := '0';
    signal o1_a1_finish         : std_logic := '0';
    signal o1_a1_ready          : std_logic := '0';
    signal o2_a2_finish         : std_logic := '0';
    signal o2_a2_ready          : std_logic := '0';
    signal i0_b0_i2_b2_finish   : std_logic := '0';
    signal o1_a1_o2_a2_finish   : std_logic := '0';
    signal o0_finish            : std_logic := '0';

    signal i0_value             : small_fixed_t := (others => '0');
    signal i0_b0_result         : large_fixed_t := (others => '0');
    signal i2_b2_result         : large_fixed_t := (others => '0');
    signal o1_a1_result         : large_fixed_t := (others => '0');
    signal o2_a2_result         : large_fixed_t := (others => '0');
    signal i0_b0_i2_b2_result   : small_fixed_t := (others => '0');
    signal o1_a1_o2_a2_result   : small_fixed_t := (others => '0');
    signal o0_result            : small_fixed_t := (others => '0');

    -- Registers
    signal i1_value             : small_fixed_t := (others => '0');
    signal i2_value             : small_fixed_t := (others => '0');
    signal o1_value             : small_fixed_t := (others => '0');
    signal o2_value             : small_fixed_t := (others => '0');
begin

    -----------------------------------------------------------------------
    -- Input wires (pipeline part 1a)
    -----------------------------------------------------------------------

    process (value_in)
        variable j : Integer := Integer (sample_width);
    begin
        i0_value <= (others => value_in (sample_width - 1));
        for i in fractional_bits - 1 downto 0 loop
            j := j - 1;
            if j >= 0 then
                i0_value (i) <= value_in (j);
            end if;
        end loop;
    end process;

    -----------------------------------------------------------------------
    -- Multipliers (pipeline part 1b)
    -----------------------------------------------------------------------

    i0_b0_multiplier : entity multiplier
        generic map (
            a_width => small_fixed_width,
            b_width => small_fixed_width,
            adder_slice_width => slice_width)
        port map (
            a_value_in => i0_value,
            b_value_in => b0_fixed,
            start_in => start_in,
            reset_in => reset_in,
            finish_out => i0_b0_finish,
            ready_out => i0_b0_ready,
            result_out => i0_b0_result,
            clock_in => clock_in);
    -- No i1_b1_multiplier as b1 = 0
    i2_b2_multiplier : entity multiplier
        generic map (
            a_width => small_fixed_width,
            b_width => small_fixed_width,
            adder_slice_width => slice_width)
        port map (
            a_value_in => i2_value,
            b_value_in => b2_fixed,
            start_in => start_in,
            reset_in => reset_in,
            finish_out => i2_b2_finish,
            ready_out => i2_b2_ready,
            result_out => i2_b2_result,
            clock_in => clock_in);
    o1_a1_multiplier : entity multiplier
        generic map (
            a_width => small_fixed_width,
            b_width => small_fixed_width,
            adder_slice_width => slice_width)
        port map (
            a_value_in => o1_value,
            b_value_in => a1_fixed,
            start_in => start_in,
            reset_in => reset_in,
            finish_out => o1_a1_finish,
            ready_out => o1_a1_ready,
            result_out => o1_a1_result,
            clock_in => clock_in);
    o2_a2_multiplier : entity multiplier
        generic map (
            a_width => small_fixed_width,
            b_width => small_fixed_width,
            adder_slice_width => slice_width)
        port map (
            a_value_in => o2_value,
            b_value_in => a2_fixed,
            start_in => start_in,
            reset_in => reset_in,
            finish_out => o2_a2_finish,
            ready_out => o2_a2_ready,
            result_out => o2_a2_result,
            clock_in => clock_in);

    -- Multipliers should all finish work at the same time
    assert i0_b0_finish = i2_b2_finish;
    assert i0_b0_finish = o1_a1_finish;
    assert i0_b0_finish = o2_a2_finish;
    assert i0_b0_ready = i2_b2_ready;
    assert i0_b0_ready = o1_a1_ready;
    assert i0_b0_ready = o2_a2_ready;

    -- Ready for more data when multipliers are ready
    ready_out <= i0_b0_ready; -- TODO, wait for finish (o1, o2 registers)

    -----------------------------------------------------------------------
    -- Input storage registers (pipeline part 1c)
    -----------------------------------------------------------------------

    process (clock_in)
    begin
        if clock_in'event and clock_in = '1' then
            if start_in = '1' then
                i1_value <= i0_value;
                i2_value <= i1_value;
            end if;
        end if;
    end process;

    -----------------------------------------------------------------------
    -- Adders (pipeline part 2)
    -----------------------------------------------------------------------

    i0_b0_i2_b2_adder : entity subtractor
        generic map (
            value_width => small_fixed_width,
            slice_width => slice_width,
            do_addition => true)
        port map (
            top_value_in => i0_b0_result (large_fixed_left downto large_fixed_right),
            bottom_value_in => i2_b2_result (large_fixed_left downto large_fixed_right),
            start_in => i0_b0_finish, -- THIS IS INCORRECT
            reset_in => reset_in,
            finish_out => i0_b0_i2_b2_finish,
            overflow_out => open,
            result_out => i0_b0_i2_b2_result,
            clock_in => clock_in);
    o1_a1_o2_a2_adder : entity subtractor
        generic map (
            value_width => small_fixed_width,
            slice_width => slice_width,
            do_addition => true)
        port map (
            top_value_in => o1_a1_result (large_fixed_left downto large_fixed_right),
            bottom_value_in => o2_a2_result (large_fixed_left downto large_fixed_right),
            start_in => o1_a1_finish,
            reset_in => reset_in,
            finish_out => o1_a1_o2_a2_finish,
            overflow_out => open,
            result_out => o1_a1_o2_a2_result,
            clock_in => clock_in);

    -- Adders should finish work at the same time
    assert i0_b0_i2_b2_finish = o1_a1_o2_a2_finish;

    -----------------------------------------------------------------------
    -- Subtractor (pipeline part 3a)
    -----------------------------------------------------------------------
    -- o0 = i0*b0 + i2*b2 - o1*a1 - o2*a2

    o0_subtractor : entity subtractor
        generic map (
            value_width => small_fixed_width,
            slice_width => slice_width,
            do_addition => false)
        port map (
            top_value_in => i0_b0_i2_b2_result,
            bottom_value_in => o1_a1_o2_a2_result,
            start_in => i0_b0_i2_b2_finish,
            reset_in => reset_in,
            finish_out => o0_finish,
            overflow_out => open,
            result_out => o0_result,
            clock_in => clock_in);

    -----------------------------------------------------------------------
    -- Output wires (pipeline part 3b)
    -----------------------------------------------------------------------
    finish_out <= o0_finish;
    result_out <= o0_result (fractional_bits - 1 downto 0);

    -----------------------------------------------------------------------
    -- Output storage registers (pipeline part 4)
    -----------------------------------------------------------------------

    process (clock_in)
    begin
        if clock_in'event and clock_in = '1' then
            if o0_finish = '1' then
                o1_value <= o0_result;
                o2_value <= o1_value;
            end if;
        end if;
    end process;

end structural;
