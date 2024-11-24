
from hardware import OperationList
import typing

UNUSED_CODE = 0xff


class FPGAOperationList(OperationList):
    def generate(self) -> None:
        OperationList.generate(self)
        with open("generated/control_line_decoder.vhdl", "wt") as fd:
            self.dump_control_line_decoder(fd)
        with open("generated/microcode_store.vhdl", "wt") as fd:
            self.dump_lattice_rom(fd)
        with open("generated/microcode_store.test.vhdl", "wt") as fd:
            self.dump_test_rom(fd)

    def get_uc_addr_bits(self, size: int) -> int:
        uc_addr_bits = 0
        while (1 << uc_addr_bits) < size:
            uc_addr_bits += 1
        return max(9, uc_addr_bits)

    def dump_code(self, fd: typing.IO) -> None:
        fd.write("Memory map\n\n")
        for op in self.operations:
            op.dump_code(fd)
        fd.write("\n\nCode table\n\n")
        self.code_table.dump_code(fd)

    def dump_control_line_decoder(self, fd: typing.IO) -> None:
        self.code_table.dump_control_line_decoder(fd)

    def dump_lattice_rom(self, fd: typing.IO) -> None:
        memory = self.get_memory_image()
        uc_addr_bits = self.get_uc_addr_bits(len(memory))
        fd.write("""library ieee;
use ieee.std_logic_1164.all;
entity microcode_store is port (
        uc_data_out : out std_logic_vector (7 downto 0) := (others => '0');
        uc_addr_in  : in std_logic_vector ({uc_addr_bits - 1} downto 0) := (others => '0');
        enable_in   : in std_logic := '0';
        clock_in    : in std_logic := '0');
end microcode_store;
architecture structural of microcode_store is
    signal one      : std_logic := '1';
    signal unused   : std_logic_vector(8 downto 0) := (others => '0');
begin\n""")
        block_size = 512
        num_blocks = (len(memory) + block_size - 1) // block_size
        k = 0
        for block in range(num_blocks):
            fd.write("ram{block} : SB_RAM512x8 generic map (\n")
            # This assumes the left-most value in INIT_0 represents the
            # byte at address 0 in the ROM; in fact, it may be byte 31.
            for i in range(16):
                if i != 0:
                    fd.write(",\n")
                fd.write(f'INIT_{i:X} => X"')
                for j in range(32):
                    if k < len(memory):
                        fd.write(f"{memory[k]:02X}")
                    else:
                        fd.write(f"{UNUSED_CODE:02X}")
                    k += 1
                fd.write('"')
            fd.write(""")\nport map (
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
