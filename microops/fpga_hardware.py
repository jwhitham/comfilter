
from func_hardware import (
            OperationList, CodeTable, ControlLine,
            ALL_BITS, A_BITS
        )
from settings import (
            FRACTIONAL_BITS, NON_FRACTIONAL_BITS, DEBUG, DATA_BITS,
        )
import typing

UNUSED_CODE = 0xff

class FPGACodeTable(CodeTable):
    def dump_control_line_decoder(self, fd: typing.IO, prefix: str) -> None:
        fd.write(f"""
library ieee;
use ieee.std_logic_1164.all;

entity {prefix}_control_line_decoder is port (
""")
        lines = list(ControlLine)
        lines.sort(key = lambda cl: cl.name)
        lines.remove(ControlLine.NOTHING)
        for cl in lines:
            fd.write(f"{cl.name} : out std_logic := '0';\n")
        fd.write(f"""
mux_select          : out std_logic_vector(3 downto 0);
mux_strobe          : out std_logic;
debug_strobe        : out std_logic;
enable_in           : in std_logic;
code_in             : in std_logic_vector(7 downto 0));
end {prefix}_control_line_decoder;
architecture structural of {prefix}_control_line_decoder is
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

    def generate(self, prefix: str) -> None:
        OperationList.generate(self, prefix)
        with open(f"generated/{prefix}_control_line_decoder.vhdl", "wt") as fd:
            self.dump_control_line_decoder(fd, prefix)
        with open(f"generated/{prefix}_microcode_store.vhdl", "wt") as fd:
            self.dump_lattice_rom(fd, prefix)
        with open(f"generated/{prefix}_microcode_store.test.vhdl", "wt") as fd:
            self.dump_test_rom(fd, prefix)
        with open(f"generated/{prefix}_settings.vhdl", "wt") as fd:
            self.dump_settings(fd, prefix)

    def get_uc_addr_bits(self, size: int) -> int:
        uc_addr_bits = 0
        while (1 << uc_addr_bits) < size:
            uc_addr_bits += 1
        return max(9, uc_addr_bits)

    def dump_settings(self, fd: typing.IO, prefix: str) -> None:
        memory = self.get_memory_image()
        uc_addr_bits = self.get_uc_addr_bits(len(memory))
        fd.write(f"""package {prefix}_settings is
constant FRACTIONAL_BITS : Natural := {FRACTIONAL_BITS};
constant NON_FRACTIONAL_BITS : Natural := {NON_FRACTIONAL_BITS};
constant UC_ADDR_BITS : Natural := {uc_addr_bits};
constant ALL_BITS : Natural := {ALL_BITS};
constant A_BITS : Natural := {A_BITS};
constant VERBOSE_DEBUG : Boolean := {DEBUG > 1};
constant DATA_BITS : Natural := {DATA_BITS};

end package {prefix}_settings;\n""")

    def dump_control_line_decoder(self, fd: typing.IO, prefix: str) -> None:
        self.code_table.dump_control_line_decoder(fd, prefix)

    def dump_lattice_rom(self, fd: typing.IO, prefix: str) -> None:
        memory = self.get_memory_image()
        uc_addr_bits = self.get_uc_addr_bits(len(memory))
        fd.write(f"""library ieee;
use ieee.std_logic_1164.all;
entity {prefix}_microcode_store is port (
        uc_data_out : out std_logic_vector (7 downto 0) := (others => '0');
        uc_addr_in  : in std_logic_vector ({uc_addr_bits - 1} downto 0) := (others => '0');
        enable_in   : in std_logic := '0';
        clock_in    : in std_logic := '0');
end {prefix}_microcode_store;
architecture structural of {prefix}_microcode_store is
    signal one      : std_logic := '1';
    signal unused   : std_logic_vector(8 downto 0) := (others => '0');

    component SB_RAM512x8 is
        generic (
            INIT_0 : std_logic_vector(255 downto 0);
            INIT_1 : std_logic_vector(255 downto 0);
            INIT_2 : std_logic_vector(255 downto 0);
            INIT_3 : std_logic_vector(255 downto 0);
            INIT_4 : std_logic_vector(255 downto 0);
            INIT_5 : std_logic_vector(255 downto 0);
            INIT_6 : std_logic_vector(255 downto 0);
            INIT_7 : std_logic_vector(255 downto 0);
            INIT_8 : std_logic_vector(255 downto 0);
            INIT_9 : std_logic_vector(255 downto 0);
            INIT_A : std_logic_vector(255 downto 0);
            INIT_B : std_logic_vector(255 downto 0);
            INIT_C : std_logic_vector(255 downto 0);
            INIT_D : std_logic_vector(255 downto 0);
            INIT_E : std_logic_vector(255 downto 0);
            INIT_F : std_logic_vector(255 downto 0));
        port (
            RDATA       : out std_logic_vector (7 downto 0);
            RADDR       : in std_logic_vector (8 downto 0);
            WADDR       : in std_logic_vector (8 downto 0);
            WDATA       : in std_logic_vector (7 downto 0);
            RCLKE       : in std_logic;
            RCLK        : in std_logic;
            RE          : in std_logic;
            WCLKE       : in std_logic;
            WCLK        : in std_logic;
            WE          : in std_logic);
    end component SB_RAM512x8;
""")

        block_size = 512
        num_blocks = (len(memory) + block_size - 1) // block_size
        for block in range(num_blocks):
            fd.write(f"signal uc_data_{block} : std_logic_vector(7 downto 0) := (others => '0');\n")
        fd.write(f"begin\n")

        row_size = 32
        k = 0
        for block in range(num_blocks):
            fd.write(f"ram{block} : SB_RAM512x8 generic map (\n")
            # The right-most value in INIT_0 represents the byte at address 0 in the ROM
            for i in range(16):
                if i != 0:
                    fd.write(",\n")
                fd.write(f'INIT_{i:X} => X"')
                k += row_size
                for j in range(row_size):
                    k -= 1
                    if k < len(memory):
                        fd.write(f"{memory[k]:02X}")
                    else:
                        fd.write(f"{UNUSED_CODE:02X}")
                k += row_size
                fd.write('"')
            fd.write(f""")\nport map (
RDATA => uc_data_{block},
RADDR => uc_addr_in(8 downto 0),
RCLK => clock_in,
RCLKE => one,
RE => enable_in,
WADDR => unused(8 downto 0),
WDATA => unused(7 downto 0),
WCLK => clock_in,
WCLKE => unused(0),
WE => unused(0));\n""")
        if uc_addr_bits <= 9:
            fd.write("uc_data_out <= uc_data_0;\n")
        else:
            fd.write("uc_data_out <=\n")
            for block in range(num_blocks):
                fd.write(f"uc_data_{block} when conv_integer("
                        f"uc_addr_in(uc_addr_bits - 1 downto 9)) = {block} else\n")
            fd.write(f"x\"{UNUSED_CODE:02x}\";\n")
        fd.write("end structural;\n")

    def dump_test_rom(self, fd: typing.IO, prefix: str) -> None:
        memory = self.get_memory_image()
        uc_addr_bits = self.get_uc_addr_bits(len(memory))
        fd.write(f"""
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity {prefix}_microcode_store is port (
        uc_data_out : out std_logic_vector (7 downto 0) := (others => '0');
        uc_addr_in  : in std_logic_vector ({uc_addr_bits - 1} downto 0) := (others => '0');
        enable_in   : in std_logic := '0';
        clock_in    : in std_logic := '0');
end {prefix}_microcode_store;
architecture behavioural of {prefix}_microcode_store is
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
