
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
    signal SET_X_IN_TO_X : std_logic := '0';
    signal SET_Y_IN_TO_X_MINUS_REG_OUT : std_logic := '0';
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
                SET_X_IN_TO_X => SET_X_IN_TO_X,
                SET_Y_IN_TO_X_MINUS_REG_OUT => SET_Y_IN_TO_X_MINUS_REG_OUT,
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

    y_register : entity register
        generic map (name => "Y")
        port map (
                reg_out => Y_OUT,
                shift_right => SHIFT_Y_RIGHT,
                reg_in => Y_IN);
    process (MUX_OUT, X_OUT, Y_SELECT) is
    begin
        y_input <= 
        # Y register has a special function input (subtract)
        if inf[SpecialRegister.Y_SELECT] == YSelect.X_MINUS_REG_OUT.value:
            y_in = 4 + (inf[Register.X] & 1) - reg_out
            if y_in & 2:
                outf[SpecialRegister.Y_SELECT] = YSelect.BORROW_X_MINUS_REG_OUT.value
        elif inf[SpecialRegister.Y_SELECT] == YSelect.BORROW_X_MINUS_REG_OUT.value:
            y_in = 3 + (inf[Register.X] & 1) - reg_out
            if not (y_in & 2):
                outf[SpecialRegister.Y_SELECT] = YSelect.X_MINUS_REG_OUT.value
        else:
            assert False
        outf[Register.Y] = (inf[Register.Y] | ((y_in & 1) << ALL_BITS)) >> 1


    filter : entity top_level
        generic map (
            sample_width => 15,
            result_width => 11,
            frequency => 1270.0,
            filter_width => 100.0,
            sample_rate => 48000.0)
        port map (
            value_in => sample_value,
            value_negative_in => sample_value_neg,
            result_out => filter_value,
            result_negative_out => filter_value_neg,
            start_in => sample_strobe,
            reset_in => reset,
            finish_out => filter_finish,
            ready_out => filter_ready,
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

