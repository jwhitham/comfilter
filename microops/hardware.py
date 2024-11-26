
from settings import (
        FRACTIONAL_BITS,
        NON_FRACTIONAL_BITS,
    )
import enum, typing

ALL_BITS = FRACTIONAL_BITS + NON_FRACTIONAL_BITS
A_BITS = R_BITS = (FRACTIONAL_BITS * 2) + NON_FRACTIONAL_BITS

class MuxCode(enum.Enum):
    ZERO = 0
    R = 1
    Y = 2
    O1 = 3
    O2 = 4
    X = 5
    L = 6
    I0 = 7
    I1 = 8
    I2 = 9
    BANK_SWITCH = 14
    L_OR_X = 15

class Register(enum.Enum):
    ZERO = MuxCode.ZERO.value
    R = MuxCode.R.value
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
    A = -4

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
    RESTART = enum.auto()
    LOAD_I0_FROM_INPUT = enum.auto()
    SEND_Y_TO_OUTPUT = enum.auto()
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
        self.table: typing.Dict[str, int] = {"": 0}

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

    def dump_code(self, fd: typing.IO) -> None:
        for (value, key) in sorted((value, key) for (key, value) in self.table.items()):
            if key == "":
                key = "NOP"
            fd.write(f"{value:3d} {key}\n")

class Operation:
    def __init__(self, address) -> None:
        self.address = address

    def __str__(self) -> str:
        return "<base>"

    def dump_code(self, fd: typing.IO) -> None:
        if self.encode() is None:
            fd.write(f'        # {self}\n')
        else:
            fd.write(f'{self.address:3d}  {self.encode():3d} {self}\n')

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
        self.code_table = self.make_code_table()
        self.address = 0

    def make_code_table(self) -> CodeTable:
        return CodeTable()

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

    def generate(self, debug: bool) -> None:
        with open("generated/disassembly.txt", "wt") as fd:
            self.dump_code(fd)

    def dump_code(self, fd: typing.IO) -> None:
        fd.write("Disassembly\n\n")
        for op in self.operations:
            op.dump_code(fd)
        fd.write("\n\nCode table\n\n")
        self.code_table.dump_code(fd)

    def get_memory_image(self) -> bytes:
        memory: typing.List[int] = []
        for op in self.operations:
            code = op.encode()
            if code is not None:
                memory.append(code)
        return bytes(memory)

def get_shift_line(target: Register) -> ControlLine:
    if not isinstance(target, Register):
        raise ValueError("Unknown Register type")
    return SHIFT_CONTROL_LINE[target]
