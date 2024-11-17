
from settings import (
        FRACTIONAL_BITS,
        NON_FRACTIONAL_BITS,
    )
import enum, typing

ALL_BITS = FRACTIONAL_BITS + NON_FRACTIONAL_BITS
A_BITS = R_BITS = (FRACTIONAL_BITS * 2) + NON_FRACTIONAL_BITS

class Register(enum.Enum):
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
    ZERO = 11
    # Special codes
    UNCHANGED = 0
    # Hidden registers
    LS = -1
    O1S = -2
    O2S = -3

class ControlLine(enum.Enum):
    ADD_A_TO_R = enum.auto()
    BANK_SWITCH = enum.auto()
    LOAD_I0_FROM_INPUT = enum.auto()
    SEND_Y_TO_OUTPUT = enum.auto()
    SET_X_IN_TO_X = enum.auto()
    SET_X_IN_TO_REG_OUT = enum.auto()
    SET_X_IN_TO_ABS_O1_REG_OUT = enum.auto()
    SET_Y_IN_TO_X_MINUS_REG_OUT = enum.auto()
    RESTART = enum.auto()
    ASSERT_X_IS_ABS_O1 = enum.auto()
    ASSERT_A_HIGH_ZERO = enum.auto()
    ASSERT_A_LOW_ZERO = enum.auto()
    ASSERT_R_ZERO = enum.auto()
    ASSERT_Y_IS_X_MINUS_L = enum.auto()
    SEND_O1_TO_OUTPUT = enum.auto()
    SEND_L_TO_OUTPUT = enum.auto()
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
    SET_MUX_BIT_1 = enum.auto()
    SET_MUX_BIT_2 = enum.auto()
    SET_MUX_BIT_4 = enum.auto()
    SET_MUX_BIT_8 = enum.auto()
    SET_MUX_L_OR_X = enum.auto()
    REPEAT_FOR_ALL_BITS = enum.auto()

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
        fd.write('# ')
        fd.write(str(self))
        fd.write("\n")

class ControlOperation(Operation):
    def __init__(self, controls: ControlLines) -> None:
        Operation.__init__(self)
        self.controls = controls

    def __str__(self) -> str:
        return ','.join(sorted([cl.name for cl in self.controls]))

    def dump_code(self, fd: typing.IO) -> None:
        fd.write(str(self))
        fd.write("\n")

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
   
    def comment(self, text: str) -> None:
        self.operations.append(CommentOperation(text))
   
    def __iter__(self) -> typing.Iterator[Operation]:
        for op in self.operations:
            yield op

    def dump_code(self, fd: typing.IO) -> None:
        for op in self.operations:
            op.dump_code(fd)
   
def get_mux_lines(source: Register) -> typing.Sequence[ControlLine]:
    if not isinstance(source, Register):
        raise ValueError("Unknown Register type")
   
    value = source.value
    if (value < 0) or (value > 15):
        raise ValueError(f"Non-selectable register {source.name}")

    control_lines = []
    if value & 1:
        control_lines.append(ControlLine.SET_MUX_BIT_1)
    if value & 2:
        control_lines.append(ControlLine.SET_MUX_BIT_2)
    if value & 4:
        control_lines.append(ControlLine.SET_MUX_BIT_4)
    if value & 8:
        control_lines.append(ControlLine.SET_MUX_BIT_8)
    return control_lines

def get_shift_line(target: Register) -> ControlLine:
    if not isinstance(target, Register):
        raise ValueError("Unknown Register type")
    return SHIFT_CONTROL_LINE[target]
