
library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

entity filter_unit is
    port (
        clock_in            : in std_logic := '0';
        reset_in            : in std_logic := '0';
        audio_ready_in      : in std_logic := '0';
        audio_data_in       : in std_logic_vector (15 downto 0) := '0';
        serial_ready_out    : out std_logic := '0';
        serial_data_out     : out std_logic := '0');
end filter_unit;

architecture structural of filter_unit is

    constant FRACTIONAL_BITS    : Natural := 14;
    constant NON_FRACTIONAL_BITS : Natural := 2;
    constant ALL_BITS           : Natural := FRACTIONAL_BITS + NON_FRACTIONAL_BITS;
    constant A_BITS             : Natural := (FRACTIONAL_BITS * 2) + NON_FRACTIONAL_BITS;

    signal clock                : std_logic := '0';
    signal reset                : std_logic := '0';
    signal sample_value         : std_logic_vector(14 downto 0) := (others => '0');
    signal sample_value_neg     : std_logic := '0';
    signal sample_strobe        : std_logic := '0';
    signal filter_value         : std_logic_vector(10 downto 0) := (others => '0');
    signal filter_value_neg     : std_logic := '0';
    signal filter_finish        : std_logic := '0';
    signal filter_ready         : std_logic := '0';


    signal ADD_A_TO_R           : std_logic := '0';
    signal LOAD_I0_FROM_INPUT   : std_logic := '0';
    signal REPEAT_FOR_ALL_BITS  : std_logic := '0';
    signal RESTART              : std_logic := '0';
    signal SEND_Y_TO_OUTPUT     : std_logic := '0';
    signal SET_X_IN_TO_ABS_O1_REG_OUT : std_logic := '0';
    signal SET_X_IN_TO_REG_OUT  : std_logic := '0';
    signal SET_X_IN_TO_X_AND_CLEAR_Y_BORROW : std_logic := '0';
    signal SHIFT_A_RIGHT        : std_logic := '0';
    signal SHIFT_I0_RIGHT       : std_logic := '0';
    signal SHIFT_I1_RIGHT       : std_logic := '0';
    signal SHIFT_I2_RIGHT       : std_logic := '0';
    signal SHIFT_L_RIGHT        : std_logic := '0';
    signal SHIFT_O1_RIGHT       : std_logic := '0';
    signal SHIFT_O2_RIGHT       : std_logic := '0';
    signal SHIFT_R_RIGHT        : std_logic := '0';
    signal SHIFT_X_RIGHT        : std_logic := '0';
    signal SHIFT_Y_RIGHT        : std_logic := '0';

    signal mux_select           : std_logic_vector(3 downto 0) := (others => '0');
    signal mux_strobe           : std_logic := '0';
    signal debug_strobe         : std_logic := '0';
    signal uc_code              : std_logic_vector(7 downto 0) := (others => '0');
    signal uc_addr              : std_logic_vector(8 downto 0) := (others => '0');

    signal bank_select          : std_logic := '0';
    signal o1_is_negative       : std_logic := '0';
    signal y_is_negative        : std_logic := '0';
    signal reg_out              : std_logic := '0';
    signal r_out                : std_logic := '0';
    signal y_out                : std_logic := '0';
    signal o1_out               : std_logic := '0';
    signal o2_out               : std_logic := '0';
    signal x_out                : std_logic := '0';
    signal l_out                : std_logic := '0';
    signal i0_out               : std_logic := '0';
    signal i1_out               : std_logic := '0';
    signal i2_out               : std_logic := '0';
begin
    test_signal_gen : entity test_signal_generator
        port map (done_out => done,
                clock_out => clock,
                strobe_out => sample_strobe,
                value_out => sample_value,
                value_negative_out => sample_value_neg,
                reset_out => reset);

    -- Control store and decoder
    test_cl_decoder : entity control_line_decoder
        port map (
                ADD_A_TO_R => ADD_A_TO_R,
                LOAD_I0_FROM_INPUT => LOAD_I0_FROM_INPUT,
                REPEAT_FOR_ALL_BITS => REPEAT_FOR_ALL_BITS,
                RESTART => RESTART,
                SEND_Y_TO_OUTPUT => SEND_Y_TO_OUTPUT,
                SET_X_IN_TO_ABS_O1_REG_OUT => SET_X_IN_TO_ABS_O1_REG_OUT,
                SET_X_IN_TO_REG_OUT => SET_X_IN_TO_REG_OUT,
                SET_X_IN_TO_X_AND_CLEAR_Y_BORROW => SET_X_IN_TO_X_AND_CLEAR_Y_BORROW,
                SHIFT_A_RIGHT => SHIFT_A_RIGHT,
                SHIFT_I0_RIGHT => SHIFT_I0_RIGHT,
                SHIFT_I1_RIGHT => SHIFT_I1_RIGHT,
                SHIFT_I2_RIGHT => SHIFT_I2_RIGHT,
                SHIFT_L_RIGHT => SHIFT_L_RIGHT,
                SHIFT_O1_RIGHT => SHIFT_O1_RIGHT,
                SHIFT_O2_RIGHT => SHIFT_O2_RIGHT,
                SHIFT_R_RIGHT => SHIFT_R_RIGHT,
                SHIFT_X_RIGHT => SHIFT_X_RIGHT,
                SHIFT_Y_RIGHT => SHIFT_Y_RIGHT,
                mux_select => mux_select,
                mux_strobe => mux_strobe,
                debug_strobe => debug_strobe,
                code_in => uc_code);
    
    test_uc_store : entity microcode_store 
        port map (
                rdata => uc_code,
                raddr => uc_addr,
                rclk => clock):

    -- Address register
    addr_register : process (clock) is
    begin
        if clock = '1' and clock'event then
            uc_addr <= uc_addr + 1;
            bit_counter <= ALL_BITS;
            if RESTART = '1' or reset_in = '1' then
                -- Reset microprogram
                uc_addr <= (others => '0');
            elsif REPEAT_FOR_ALL_BITS = '1' and bit_counter /= 0 then
                -- Stay on this instruction until the bit counter reaches 0
                bit_counter <= bit_counter - 1;
                uc_addr <= uc_addr;
            elsif LOAD_I0_FROM_INPUT = '1' and audio_ready_in = '0' then
                -- Stay on this instruction until input is received
                uc_addr <= uc_addr;
            end if;
        end if;
    end process addr_register;

    -- X register (special input via negation unit or passthrough)
    x_register : block
        type x_select_enum is (PASSTHROUGH_REG_OUT, PASSTHROUGH_X, NEGATE_REG_OUT);
        signal x_select                     : x_select_enum := PASSTHROUGH_REG_OUT;
        signal x_in_negate_reg_out, x_mux   : std_logic := '0';
    begin
        x_subtractor : entity subtractor
            port map (
                    x_in => zero,
                    y_in => reg_out,
                    b_reset_in => SET_X_IN_TO_ABS_O1_REG_OUT,
                    d_out => negate_reg_out,
                    clock_in => clock);

        x_mux <= reg_out if x_select = PASSTHROUGH_REG_OUT
            else x_out if x_select = PASSTHROUGH_X
            else negate_reg_out;

        x_register : entity shift_register
            generic map (name => "X")
            port map (
                    reg_out => x_out,
                    shift_right_in => SHIFT_X_RIGHT, size => ALL_BITS,
                    reg_in => x_mux,
                    negative_out => open,
                    clock_in => clock);

        process (clock) is
        begin
            if clock = '1' and clock'event then
                if SET_X_IN_TO_REG_OUT = '1' then
                    x_select <= PASSTHROUGH_REG_OUT;
                elsif SET_X_IN_TO_ABS_O1_REG_OUT = '1' then
                    if o1_is_negative = '1' then
                        x_select <= NEGATE_REG_OUT;
                    else
                        x_select <= PASSTHROUGH_REG_OUT;
                    end if;
                elsif SET_X_IN_TO_X_AND_CLEAR_Y_BORROW = '1' then
                    x_select <= PASSTHROUGH_X;
                end if;
            end if;
        end process;
    end block x_register;

    -- Y register (special input via subtractor)
    y_register : block
        signal y_in : std_logic := '0';
    begin
        y_subtractor : entity subtractor
            port map (
                    x_in => x_out,
                    y_in => reg_out,
                    b_reset_in => SET_X_IN_TO_X_AND_CLEAR_Y_BORROW,
                    d_out => y_in,
                    clock_in => clock);
        y_register : entity shift_register
            generic map (name => "Y", size => ALL_BITS)
            port map (
                    reg_out => y_out,
                    shift_right_in => SHIFT_Y_RIGHT,
                    reg_in => y_in,
                    negative_out => y_is_negative,
                    clock_in => clock);
    end y_register;

    -- I0 register (parallel input)
    i0_register : block
        signal i0_value : std_logic_vector(ALL_BITS - 1 downto 0) := (others => '0');
    begin
        process (clock) is
        begin
            if clock = '1' and clock'event then
                if LOAD_I0_FROM_INPUT = '1' then
                    i0_value <= audio_data_in(15 downto 16 - ALL_BITS);
                elsif SHIFT_I0_RIGHT = '1' then
                    i0_value(ALL_BITS - 1) <= reg_out;
                    i0_value(ALL_BITS - 2 downto 0) <= i0_value(ALL_BITS - 1 downto 1);
                end if;
            end if;
        end process;
        i0_out <= i0_value(0);
    end i0_register;

    -- Other registers
    i1_register : entity shift_register
        generic map (name => "I1", size => ALL_BITS)
        port map (
                reg_out => i1_out,
                shift_right_in => SHIFT_I1_RIGHT,
                reg_in => reg_out,
                negative_out => open,
                clock_in => clock);
    i2_register : entity shift_register
        generic map (name => "I2", size => ALL_BITS)
        port map (
                reg_out => i2_out,
                shift_right_in => SHIFT_I2_RIGHT,
                reg_in => reg_out,
                negative_out => open,
                clock_in => clock);
    o1_register : entity banked_shift_register
        generic map (name => "O1", size => ALL_BITS)
        port map (
                reg_out => o1_out,
                shift_right_in => SHIFT_O1_RIGHT,
                reg_in => reg_out,
                bank_select_in => bank_select,
                negative_out => o1_is_negative,
                clock_in => clock);
    o2_register : entity banked_shift_register
        generic map (name => "O2", size => ALL_BITS)
        port map (
                reg_out => o2_out,
                shift_right_in => SHIFT_O2_RIGHT,
                reg_in => reg_out,
                bank_select_in => bank_select,
                negative_out => open,
                clock_in => clock);
    l_register : entity banked_shift_register
        generic map (name => "L", size => ALL_BITS)
        port map (
                reg_out => l_out,
                shift_right_in => SHIFT_L_RIGHT,
                reg_in => reg_out,
                bank_select_in => bank_select,
                negative_out => open,
                clock_in => clock);

    -- Adder and A, R registers
    ar_registers : block
        signal a_value : std_logic_vector(A_BITS - 1 downto 0);
        signal r_value : std_logic_vector(A_BITS - 1 downto 0);
    begin
        process (clock) is
        begin
            if clock = '1' and clock'event then
                if SHIFT_A_RIGHT = '1' then
                    a_value(A_BITS - 1) <= reg_out;
                    a_value(A_BITS - 2 downto 0) <= a_value(A_BITS - 1 downto 1);
                end if;
                if ADD_A_TO_R = '1' then
                    r_value <= r_value + a_value;
                elsif SHIFT_R_RIGHT = '1' then
                    r_value(A_BITS - 1) <= '0';
                    r_value(A_BITS - 2 downto 0) <= r_value(A_BITS - 1 downto 1);
                end if;
            end if;
        end process;
        r_out <= r_value(0);
    end ar_registers;

    -- Register multiplexer
    mux : block
        signal reg_mux      : std_logic_vector(15 downto 0) := (others => '0');
        signal mux_select   : Natural range 0 to 15;
    begin
        reg_mux(0) <= '0'; -- ZERO = 0
        reg_mux(1) <= r_out; -- R = 1
        reg_mux(2) <= y_out; -- Y = 2
        reg_mux(3) <= o1_out; -- O1 = 3
        reg_mux(4) <= o2_out; -- O2 = 4
        reg_mux(5) <= x_out; -- X = 5
        reg_mux(6) <= l_out; -- L = 6
        reg_mux(7) <= i0_out; -- I0 = 7
        reg_mux(8) <= i1_out; -- I1 = 8
        reg_mux(9) <= i2_out; -- I2 = 9
        reg_out <= reg_mux(mux_select);

        process (clock) is
        begin
            if clock = '1' and clock'event then
                if mux_strobe = '1' then
                    mux_register <= conv_integer(mux_select);
                    case mux_select is
                        when x"e" =>
                            -- bank switch
                            bank_select <= not bank_select;
                        when x"f" =>
                            -- L or X
                            if y_is_negative = '1' then
                                mux_register <= 7; -- L
                            else
                                mux_register <= 6; -- X
                            end if;
                        when others =>
                            null;
                    end case;
                end if;
            end if;
        end process;
    end mux;

    -- Output
    serial_data_out <= y_is_negative;
    serial_ready_out <= SEND_Y_TO_OUTPUT;
end structural;

