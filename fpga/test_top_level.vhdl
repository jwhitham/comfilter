
library work;
use work.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use std.textio.all;

entity test_top_level is
end test_top_level;

architecture structural of test_top_level is

    signal done                : std_logic := '0';
    signal clock               : std_logic := '0';
    signal reset               : std_logic := '0';
    signal sample_value        : std_logic_vector(14 downto 0) := (others => '0');
    signal sample_value_neg    : std_logic := '0';
    signal sample_strobe       : std_logic := '0';
    signal filter_value        : std_logic_vector(10 downto 0) := (others => '0');
    signal filter_value_neg    : std_logic := '0';
    signal filter_finish       : std_logic := '0';
    signal filter_ready        : std_logic := '0';

    signal ADD_A_TO_R : std_logic := '0';
    signal REPEAT_FOR_ALL_BITS : std_logic := '0';
    signal SET_X_IN_TO_ABS_O1_REG_OUT : std_logic := '0';
    signal SET_X_IN_TO_REG_OUT : std_logic := '0';
    signal SET_X_IN_TO_X_AND_CLEAR_Y_BORROW : std_logic := '0';
    signal SHIFT_A_RIGHT : std_logic := '0';
    signal SHIFT_I0_RIGHT : std_logic := '0';
    signal SHIFT_I1_RIGHT : std_logic := '0';
    signal SHIFT_I2_RIGHT : std_logic := '0';
    signal SHIFT_L_RIGHT : std_logic := '0';
    signal SHIFT_O1_RIGHT : std_logic := '0';
    signal SHIFT_O2_RIGHT : std_logic := '0';
    signal SHIFT_R_RIGHT : std_logic := '0';
    signal SHIFT_X_RIGHT : std_logic := '0';
    signal SHIFT_Y_RIGHT : std_logic := '0';

    signal mux_select       : std_logic_vector(3 downto 0);
    signal mux_strobe       : std_logic;
    signal debug_strobe     : std_logic;
    signal uc_code          : std_logic_vector(7 downto 0);
    signal uc_addr          : std_logic_vector (8 downto 0);

    signal ZERO_OUT       : std_logic;
    signal R_OUT          : std_logic;
    signal A_OUT          : std_logic;
    signal Y_OUT          : std_logic;
    signal O1_OUT         : std_logic;
    signal O2_OUT         : std_logic;
    signal X_OUT          : std_logic;
    signal L_OUT          : std_logic;
    signal I0_OUT         : std_logic;
    signal I1_OUT         : std_logic;
    signal I2_OUT         : std_logic;
    signal RESTART_OUT    : std_logic;
    signal L_OR_X_OUT     : std_logic;
    signal BANK_SWITCH_OUT : std_logic;
    signal LOAD_I0_FROM_INPUT_OUT : std_logic;
    signal SEND_Y_TO_OUTPUT_OUT : std_logic;

    signal mux_in           : std_logic_vector(15 downto 0);
begin
    test_signal_gen : entity test_signal_generator
        port map (done_out => done,
                clock_out => clock,
                strobe_out => sample_strobe,
                value_out => sample_value,
                value_negative_out => sample_value_neg,
                reset_out => reset);

    test_cl_decoder : entity control_line_decoder
        port map (
                ADD_A_TO_R => ADD_A_TO_R,
                REPEAT_FOR_ALL_BITS => REPEAT_FOR_ALL_BITS,
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

    -- X register components
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
                    shift_right_in => SHIFT_X_RIGHT,
                    reg_in => x_mux,
                    parallel_out => open,
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

    -- Y register components
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
            generic map (name => "Y")
            port map (
                    reg_out => y_out,
                    shift_right_in => SHIFT_Y_RIGHT,
                    reg_in => y_in,
                    parallel_out => open,
                    clock_in => clock);
    end y_register;

    -- I0 register
    i0_register : declare
    begin
        process (clock) is
        begin
            if clock = '1' and clock'event then
                if LOAD_I0_FROM_INPUT = '1' then
                    i0_value
                end if;
            end if;
        end process;

    -- Other registers
    i1_register : entity shift_register
        generic map (name => "I1")
        port map (
                reg_out => i1_out,
                shift_right_in => SHIFT_I1_RIGHT,
                reg_in => reg_out,
                parallel_out => open,
                clock_in => clock);
    i2_register : entity shift_register
        generic map (name => "I2")
        port map (
                reg_out => i2_out,
                shift_right_in => SHIFT_I2_RIGHT,
                reg_in => reg_out,
                parallel_out => open,
                clock_in => clock);
    o1_register : entity shift_register
        generic map (name => "O1")
        port map (
                reg_out => o1_out,
                shift_right_in => SHIFT_O1_RIGHT,
                reg_in => reg_out,
                parallel_out => open,
                clock_in => clock);
    o2_register : entity shift_register
        generic map (name => "O2")
        port map (
                reg_out => o2_out,
                shift_right_in => SHIFT_O2_RIGHT,
                reg_in => reg_out,
                parallel_out => open,
                clock_in => clock);


    process is
        variable l : line;
        variable active : Boolean := false;
        variable saved : std_logic_vector (14 downto 0) := (others => '0');
        variable saved_neg : std_logic := '0';
        variable counter : Integer := 0;
    begin
        wait until reset = '0';
        while done = '0' loop
            wait until clock = '1' and clock'event;
            assert not (sample_strobe = '1' and filter_finish = '1');
            if sample_strobe = '1' then
                assert not active;
                saved := sample_value;
                saved_neg := sample_value_neg;
                active := true;
                if filter_ready = '0' then
                    write (l, String'("Filter not ready!"));
                    writeline (output, l);
                    assert false;
                end if;
            end if;
            if filter_finish = '1' then
                assert active;
                write (l, Integer'(counter));
                write (l, String'(" "));
                if saved_neg = '1' then
                    write (l, String'("-"));
                end if;
                write (l, Integer'(ieee.numeric_std.to_integer(unsigned(saved))));
                write (l, String'(" "));
                if filter_value_neg = '1' then
                    write (l, String'("-"));
                end if;
                write (l, Integer'(ieee.numeric_std.to_integer(unsigned(filter_value))));
                writeline (output, l);
                active := false;
                counter := counter + 1;
            end if;
        end loop;
        write (l, String'("Reached the end"));
        writeline (output, l);
    end process;
end structural;

