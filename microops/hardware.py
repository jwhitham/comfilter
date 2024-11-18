
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
    SET_X_IN_TO_X = enum.auto()
    SET_X_IN_TO_REG_OUT = enum.auto()
    SET_X_IN_TO_ABS_O1_REG_OUT = enum.auto()
    SET_Y_IN_TO_X_MINUS_REG_OUT = enum.auto()
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
    ASSERT_X_IS_ABS_O1 = enum.auto()
    ASSERT_A_HIGH_ZERO = enum.auto()
    ASSERT_A_LOW_ZERO = enum.auto()
    ASSERT_R_ZERO = enum.auto()
    ASSERT_Y_IS_X_MINUS_L = enum.auto()
    SEND_O1_TO_OUTPUT = enum.auto()
    SEND_L_TO_OUTPUT = enum.auto()

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

class Operation:
    def __init__(self) -> None:
        self.address = 0

    def __str__(self) -> str:
        return "<base>"

    def dump_code(self, fd: typing.IO) -> None:
        pass

class CommentOperation(Operation):
    def __init__(self, comment: str) -> None:
        Operation.__init__(self)
        self.comment = comment

    def __str__(self) -> str:
        return self.comment

    def dump_code(self, fd: typing.IO) -> None:
        fd.write('     # ')
        fd.write(str(self))
        fd.write("\n")

class ControlOperation(Operation):
    def __init__(self, controls: ControlLines) -> None:
        Operation.__init__(self)
        self.controls = controls

    def __str__(self) -> str:
        return ','.join(sorted([cl.name for cl in self.controls]))

    def dump_code(self, fd: typing.IO) -> None:
        fd.write(f'{self.address:03x}  ')
        fd.write(str(self))
        fd.write("\n")

class DebugOperation(Operation):
    def __init__(self, debug: Debug) -> None:
        Operation.__init__(self)
        self.debug = debug

    def __str__(self) -> str:
        return self.debug.name

    def dump_code(self, fd: typing.IO) -> None:
        fd.write(f'{self.address:03x}  {self.debug.name}\n')

class MuxOperation(Operation):
    def __init__(self, source: MuxCode) -> None:
        Operation.__init__(self)
        self.source = source

    def __str__(self) -> str:
        return f"SET MUX {self.source.name}"

    def dump_code(self, fd: typing.IO) -> None:
        fd.write(f'{self.address:03x}  {self}\n')

class OperationList:
    def __init__(self) -> None:
        self.operations: typing.List[Operation] = []

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
        self.operations.append(ControlOperation(control_lines))
   
    def debug(self, debug: Debug) -> None:
        self.operations.append(DebugOperation(debug))
   
    def comment(self, text: str) -> None:
        self.operations.append(CommentOperation(text))
   
    def mux(self, source: typing.Union[MuxCode, Register]) -> None:
        if isinstance(source, Register):
            source = MuxCode(source.value)

        if not isinstance(source, MuxCode):
            raise ValueError("Unknown Register or MuxCode")
       
        self.operations.append(MuxOperation(source))

    def __iter__(self) -> typing.Iterator[Operation]:
        for op in self.operations:
            yield op

    def finalise(self) -> None:
        address = 0
        count: typing.Dict[typing.Tuple, int] = {}
        for op in self.operations:
            op.address = address
            if isinstance(op, ControlOperation) or isinstance(op, MuxOperation):
                address += 1

    def dump_code(self, fd: typing.IO) -> None:
        for op in self.operations:
            op.dump_code(fd)
   
def get_shift_line(target: Register) -> ControlLine:
    if not isinstance(target, Register):
        raise ValueError("Unknown Register type")
    return SHIFT_CONTROL_LINE[target]