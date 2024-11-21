
from settings import (
        FRACTIONAL_BITS,
        NON_FRACTIONAL_BITS,
    )
import enum, typing

ALL_BITS = FRACTIONAL_BITS + NON_FRACTIONAL_BITS
A_BITS = R_BITS = (FRACTIONAL_BITS * 2) + NON_FRACTIONAL_BITS
MICROCODE_STORE_SIZE = 0x200

class MuxCode(enum.Enum):
    ZERO = 0
    R = 1
    A = 2
    Y = 3
    O1 = 4
    O2 = 5
    X = 6
    L = 7
    I0 = 8
    I1 = 9
    I2 = 10
    RESTART = 11
    L_OR_X = 12
    BANK_SWITCH = 13
    LOAD_I0_FROM_INPUT = 14
    SEND_Y_TO_OUTPUT = 15

class Register(enum.Enum):
    ZERO = MuxCode.ZERO.value
    R = MuxCode.R.value
    A = MuxCode.A.value
    Y = MuxCode.Y.value
    O1 = MuxCode.O1.value
    O2 = MuxCode.O2.value
    X = MuxCode.X.value
    L = MuxCode.L.value
    I0 = MuxCode.I0.value
    I1 = MuxCode.I1.value
    I2 = MuxCode.I2.value
    # Hidden registers
    LS = -1
    O1S = -2
    O2S = -3

class ControlLine(enum.Enum):
    ADD_A_TO_R = enum.auto()
    SET_X_IN_TO_X_AND_CLEAR_Y_BORROW = enum.auto()
    SET_X_IN_TO_REG_OUT = enum.auto()
    SET_X_IN_TO_ABS_O1_REG_OUT = enum.auto()
    SHIFT_A_RIGHT = enum.auto()
    SHIFT_X_RIGHT = enum.auto()
    SHIFT_Y_RIGHT = enum.auto()
    SHIFT_I0_RIGHT = enum.auto()
    SHIFT_I1_RIGHT = enum.auto()
    SHIFT_I2_RIGHT = enum.auto()
    SHIFT_L_RIGHT = enum.auto()
    SHIFT_O1_RIGHT = enum.auto()
    SHIFT_O2_RIGHT = enum.auto()
    SHIFT_R_RIGHT = enum.auto()
    REPEAT_FOR_ALL_BITS = enum.auto()
    NOTHING = enum.auto()

class Debug(enum.Enum):
    ASSERT_X_IS_ABS_O1 = 1
    ASSERT_A_HIGH_ZERO = 2
    ASSERT_A_LOW_ZERO = 3
    ASSERT_R_ZERO = 4
    ASSERT_Y_IS_X_MINUS_L = 5
    SEND_O1_TO_OUTPUT = 6
    SEND_L_TO_OUTPUT = 7

SHIFT_CONTROL_LINE = {
    Register.A : ControlLine.SHIFT_A_RIGHT,
    Register.X : ControlLine.SHIFT_X_RIGHT,
    Register.Y : ControlLine.SHIFT_Y_RIGHT,
    Register.I0 : ControlLine.SHIFT_I0_RIGHT,
    Register.I1 : ControlLine.SHIFT_I1_RIGHT,
    Register.I2 : ControlLine.SHIFT_I2_RIGHT,
    Register.L : ControlLine.SHIFT_L_RIGHT,
    Register.O1 : ControlLine.SHIFT_O1_RIGHT,
    Register.O2 : ControlLine.SHIFT_O2_RIGHT,
    Register.R : ControlLine.SHIFT_R_RIGHT,
}

ControlLines = typing.Set[ControlLine]
ControlLineTree = typing.Union[ControlLines, ControlLine, typing.Sequence]

class CodeTable:
    def __init__(self) -> None:
        self.table: typing.Dict[str, int] = {}

    def encode(self, controls: ControlLines) -> None:
        controls = set(controls)
        flag = 0
        if ControlLine.REPEAT_FOR_ALL_BITS in controls:
            flag |= 0x40
            controls.discard(ControlLine.REPEAT_FOR_ALL_BITS)
        if ControlLine.SHIFT_A_RIGHT in controls:
            flag |= 0x20
            controls.discard(ControlLine.SHIFT_A_RIGHT)
        key = ','.join(sorted(c.name for c in controls))
        if key not in self.table:
            self.table[key] = len(self.table)
            if self.table[key] >= 0x20:
                raise ValueError("Too many codes are required")
        return self.table[key] | flag

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
code_in             : in std_logic_vector(7 downto 0));
end control_line_decoder;
architecture structural of control_line_decoder is
    signal enable : std_logic;
begin
    enable <= not code_in(7);
    mux_strobe <= code_in(7) and not code_in(6);
    debug_strobe <= code_in(7) and code_in(6);
    mux_select <= code_in(3 downto 0);
    REPEAT_FOR_ALL_BITS <= code_in(6) and enable;
    SHIFT_A_RIGHT <= code_in(5) and enable;
""")
        lines.remove(ControlLine.REPEAT_FOR_ALL_BITS)
        lines.remove(ControlLine.SHIFT_A_RIGHT)
        fd.write("""
process (code_in, enable) is begin
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
                    fd.write(f"  {name} <= enable;\n")
        fd.write("""when others => null;
end case;
end process;
end structural;
""")

    def dump_code(self, fd: typing.IO) -> None:
        for (value, key) in sorted((value, key) for (key, value) in self.table.items()):
            fd.write(f"{value:02x} {key}\n")

class Operation:
    def __init__(self, address) -> None:
        self.address = address

    def __str__(self) -> str:
        return "<base>"

    def dump_code(self, fd: typing.IO) -> None:
        if self.encode() is None:
            fd.write(f'        # {self}\n')
        else:
            fd.write(f'{self.address:03x}  {self.encode():02x} {self}\n')

    def encode(self) -> typing.Optional[int]:
        return None

class CommentOperation(Operation):
    def __init__(self, comment: str, address: int) -> None:
        Operation.__init__(self, address)
        self.comment = comment

    def __str__(self) -> str:
        return self.comment

class ControlOperation(Operation):
    def __init__(self, controls: ControlLines,
                code_table: CodeTable, address: int) -> None:
        Operation.__init__(self, address)
        self.controls = controls
        self.code_table = code_table

    def __str__(self) -> str:
        return ','.join(sorted([cl.name for cl in self.controls]))

    def encode(self) -> typing.Optional[int]:
        return self.code_table.encode(self.controls)

class DebugOperation(Operation):
    def __init__(self, debug: Debug, address: int) -> None:
        Operation.__init__(self, address)
        self.debug = debug

    def __str__(self) -> str:
        return self.debug.name

    def encode(self) -> typing.Optional[int]:
        return 0xc0 | self.debug.value

class MuxOperation(Operation):
    def __init__(self, source: MuxCode, address: int) -> None:
        Operation.__init__(self, address)
        self.source = source

    def __str__(self) -> str:
        return f"SET MUX {self.source.name}"

    def encode(self) -> typing.Optional[int]:
        return 0x80 | self.source.value

class OperationList:
    def __init__(self) -> None:
        self.operations: typing.List[Operation] = []
        self.code_table = CodeTable()
        self.address = 0

    def __len__(self) -> int:
        return len(self.operations)

    def __getitem__(self, index: int) -> Operation:
        return self.operations[index]

    def add(self, *controls_tree: ControlLineTree) -> None:
        control_lines: ControlLines = set()

        def collector(cl: ControlLineTree) -> None:
            if isinstance(cl, ControlLine):
                control_lines.add(cl)
            elif isinstance(cl, list) or isinstance(cl, tuple) or isinstance(cl, set):
                for cl2 in cl:
                    collector(cl2)
            else:
                raise ValueError("Unknown ControlLine type")

        collector(controls_tree)
        self.operations.append(ControlOperation(control_lines, self.code_table, self.address))
        self.address += 1
   
    def debug(self, debug: Debug) -> None:
        self.operations.append(DebugOperation(debug, self.address))
        self.address += 1
   
    def comment(self, text: str) -> None:
        self.operations.append(CommentOperation(text, self.address))
   
    def mux(self, source: typing.Union[MuxCode, Register]) -> None:
        if isinstance(source, Register):
            source = MuxCode(source.value)

        if not isinstance(source, MuxCode):
            raise ValueError("Unknown Register or MuxCode")
       
        self.operations.append(MuxOperation(source, self.address))
        self.address += 1

    def __iter__(self) -> typing.Iterator[Operation]:
        for op in self.operations:
            yield op

    def finalise(self) -> None:
        pass

    def get_memory_image(self) -> bytes:
        memory: typing.List[int] = []
        for op in self.operations:
            code = op.encode()
            if code is not None:
                memory.append(code)
        while len(memory) < MICROCODE_STORE_SIZE:
            memory.append(0xff)
        assert len(memory) == MICROCODE_STORE_SIZE

        return bytes(memory)

    def dump_code(self, fd: typing.IO) -> None:
        fd.write("Memory map\n\n")
        for op in self.operations:
            op.dump_code(fd)
        fd.write("\n\nCode table\n\n")
        self.code_table.dump_code(fd)

    def dump_control_line_decoder(self, fd: typing.IO) -> None:
        self.code_table.dump_control_line_decoder(fd)

    def dump_lattice_rom(self, fd: typing.IO) -> None:
        fd.write("""
library ieee;
use ieee.std_logic_1164.all;

entity microcode_store is port (
        rdata       : out std_logic_vector (7 downto 0) := (others => '0');
        raddr       : in std_logic_vector (8 downto 0);
        rclk        : in std_logic);
end microcode_store;
architecture structural of microcode_store is
    signal one      : std_logic := '1';
    signal unused   : std_logic_vector(8 downto 0) := (others => '0');
begin

ram512x8_inst : SB_RAM512x8
generic map (
""")
        memory = self.get_memory_image()
        # This assumes the left-most value in INIT_0 represents the
        # byte at address 0 in the ROM; in fact, it may be byte 31.
        k = 0
        for i in range(16):
            if i != 0:
                fd.write(",\n")
            fd.write(f'INIT_{i:X} => X"')
            for j in range(32):
                fd.write(f"{memory[k]:02X}")
                k += 1
            fd.write('"')
        fd.write(""")
port map (
RDATA => rdata,
RADDR => raddr,
RCLK => rclk,
RCLKE => one,
RE => one,
WADDR => unused(8 downto 0),
WDATA => unused(7 downto 0),
WCLK => rclk,
WCLKE => unused(0),
WE => unused(0));
end structural;
""")

    def dump_test_rom(self, fd: typing.IO) -> None:
        fd.write("""
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity microcode_store is port (
        rdata       : out std_logic_vector (7 downto 0) := (others => '0');
        raddr       : in std_logic_vector (8 downto 0);
        rclk        : in std_logic);
end microcode_store;
architecture behavioural of microcode_store is
    subtype t_word is std_logic_vector (7 downto 0);
    type t_storage is array (0 to 511) of t_word;
    signal storage : t_storage := (
""")
        memory = self.get_memory_image()
        for (address, code) in enumerate(memory[:-1]):
            fd.write(f'{address} => "{code:08b}",\n')
        code = memory[-1]
        fd.write(f'others => "{code:08b}");\n')
        fd.write("""
begin
    process (rclk)
    begin
        if rclk'event and rclk = '1' then
            if rclke = '1' and re = '1' then
                rdata <= storage (to_integer (unsigned (raddr)));
            end if;
        end if;
    end process;
end architecture behavioural;
""")

def get_shift_line(target: Register) -> ControlLine:
    if not isinstance(target, Register):
        raise ValueError("Unknown Register type")
    return SHIFT_CONTROL_LINE[target]
