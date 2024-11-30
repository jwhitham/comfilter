
from hardware import (
            OperationList, CodeTable, ControlLine,
            ALL_BITS, A_BITS
        )
from settings import (
            FRACTIONAL_BITS, NON_FRACTIONAL_BITS, DEBUG,
        )
import typing

UNUSED_CODE = 0xff

class FPGACodeTable(CodeTable):
    def dump_control_line_decoder(self, fd: typing.IO) -> None:
        fd.write("""
library ieee;
use ieee.std_logic_1164.all;

entity control_line_decoder is port (
""")
        lines = list(ControlLine)
        lines.sort(key = lambda cl: cl.name)
        lines.remove(ControlLine.NOTHING)
        for cl in lines:
            fd.write(f"{cl.name} : out std_logic := '0';\n")
        fd.write("""
mux_select          : out std_logic_vector(3 downto 0);
mux_strobe          : out std_logic;
debug_strobe        : out std_logic;
enable_in           : in std_logic;
code_in             : in std_logic_vector(7 downto 0));
end control_line_decoder;
architecture structural of control_line_decoder is
    signal control_line_enable : std_logic;
begin
    control_line_enable <= enable_in and not code_in(7);
    mux_strobe <= enable_in and code_in(7) and not code_in(6);
    debug_strobe <= enable_in and code_in(7) and code_in(6);
    mux_select <= code_in(3 downto 0);
    REPEAT_FOR_ALL_BITS <= code_in(6) and control_line_enable;
    SHIFT_A_RIGHT <= code_in(5) and control_line_enable;
""")
        lines.remove(ControlLine.REPEAT_FOR_ALL_BITS)
        lines.remove(ControlLine.SHIFT_A_RIGHT)
        fd.write("""
process (code_in, control_line_enable) is begin
""")
        for cl in lines:
            fd.write(f"{cl.name} <= '0';\n")
        fd.write("case code_in (4 downto 0) is\n")
        for (value, key) in sorted((value, key) for (key, value) in self.table.items()):
            fd.write(f'when "{value:05b}" =>\n')
            if key == "":
                fd.write("  null;\n")
            else:
                for name in key.split(","):
                    fd.write(f"  {name} <= control_line_enable;\n")
        fd.write("""when others => RESTART <= control_line_enable;
end case;
end process;
end structural;
""")


class FPGAOperationList(OperationList):
    def make_code_table(self) -> CodeTable:
        return FPGACodeTable()

    def generate(self) -> None:
        OperationList.generate(self)
        with open("generated/control_line_decoder.vhdl", "wt") as fd:
            self.dump_control_line_decoder(fd)
        with open("generated/microcode_store.v", "wt") as fd:
            self.dump_lattice_rom(fd)
        with open("generated/microcode_store.test.vhdl", "wt") as fd:
            self.dump_test_rom(fd)
        with open("generated/settings.vhdl", "wt") as fd:
            self.dump_settings(fd)

    def get_uc_addr_bits(self, size: int) -> int:
        uc_addr_bits = 0
        while (1 << uc_addr_bits) < size:
            uc_addr_bits += 1
        return max(9, uc_addr_bits)

    def dump_settings(self, fd: typing.IO) -> None:
        memory = self.get_memory_image()
        uc_addr_bits = self.get_uc_addr_bits(len(memory))
        fd.write(f"""package settings is
constant FRACTIONAL_BITS : Natural := {FRACTIONAL_BITS};
constant NON_FRACTIONAL_BITS : Natural := {NON_FRACTIONAL_BITS};
constant UC_ADDR_BITS : Natural := {uc_addr_bits};
constant ALL_BITS : Natural := {ALL_BITS};
constant A_BITS : Natural := {A_BITS};
constant VERBOSE_DEBUG : Boolean := {DEBUG > 1};

end package settings;\n""")

    def dump_control_line_decoder(self, fd: typing.IO) -> None:
        self.code_table.dump_control_line_decoder(fd)

    def dump_lattice_rom(self, fd: typing.IO) -> None:
        memory = self.get_memory_image()
        uc_addr_bits = self.get_uc_addr_bits(len(memory))
        fd.write(f"""
module microcode_store (uc_data_out, uc_addr_in, enable_in, clock_in);
    input clock_in;
    input enable_in;
    input [{uc_addr_bits - 1}:0] uc_addr_in;
    output [7:0] uc_data_out;

    wire one = 1'b1;
    wire unused [8:0] = 9'b0;\n""")

        block_size = 512
        num_blocks = (len(memory) + block_size - 1) // block_size
        for block in range(num_blocks):
            fd.write(f"wire uc_data_{block} [7:0];\n")

        row_size = 32
        k = 0
        for block in range(num_blocks):
            fd.write(f"""SB_RAM512x8 ram{block} (
.RDATA(uc_data_{block}[7:0]),
.RADDR(uc_addr_in[8:0]),
.RCLK(clock_in),
.RCLKE(one),
.RE(enable_in),
.WADDR(unused[8:0]),
.WCLK(clock_in),
.WCLKE(unused[0]),
.WDATA(unused[7:0]),
.WE(unused[0]));\n""")
            # The right-most value in INIT_0 represents the byte at address 0 in the ROM
            for i in range(16):
                fd.write(f"defparam ram{block}.INIT_{i:X} = 256'h")
                k += row_size
                for j in range(row_size):
                    k -= 1
                    if k < len(memory):
                        fd.write(f"{memory[k]:02X}")
                    else:
                        fd.write(f"{UNUSED_CODE:02X}")
                k += row_size
                fd.write(";\n")
        high_bits = uc_addr_bits - 9
        if high_bits <= 0:
            fd.write(f"assign uc_data_out[7:0] = uc_data_0[7:0];\n")
        else:
            fd.write(f"always @(uc_addr_in")
            for block in range(num_blocks):
                fd.write(f", uc_data_{block}")

            fd.write(f") begin\ncase(uc_addr_in[{uc_addr_bits - 1}:9])\n")
            fmt_string = "{}'b{:0" + str(high_bits) + 'b} : uc_data_out [7:0] = uc_data_{} [7:0];\n'
            for block in range(1 << high_bits):
                block = min(block, num_blocks - 1)
                fd.write(fmt_string.format(high_bits, block, block))
            fd.write("endcase\nend\n")
        fd.write("endmodule\n")

    def dump_test_rom(self, fd: typing.IO) -> None:
        memory = self.get_memory_image()
        uc_addr_bits = self.get_uc_addr_bits(len(memory))
        fd.write(f"""
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity microcode_store is port (
        uc_data_out : out std_logic_vector (7 downto 0) := (others => '0');
        uc_addr_in  : in std_logic_vector ({uc_addr_bits - 1} downto 0) := (others => '0');
        enable_in   : in std_logic := '0';
        clock_in    : in std_logic := '0');
end microcode_store;
architecture behavioural of microcode_store is
    subtype t_word is std_logic_vector (7 downto 0);
    type t_storage is array (0 to {(1 << uc_addr_bits) - 1}) of t_word;
    signal storage : t_storage := (
""")
        for (address, code) in enumerate(memory):
            fd.write(f'{address} => "{code:08b}",\n')
        fd.write(f'others => x"{UNUSED_CODE:02x}");\n')
        fd.write("""
begin
    process (clock_in)
    begin
        if clock_in'event and clock_in = '1' then
            if enable_in = '1' then
                uc_data_out <= storage (to_integer (unsigned (uc_addr_in)));
            end if;
        end if;
    end process;
end architecture behavioural;
""")
