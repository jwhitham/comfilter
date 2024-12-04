
from func_hardware import (
        ALL_BITS,
    )
from copy import copy
import typing, struct

OUT_VALUES_PER_IN_VALUE = 5
TEST_VECTOR_FORMAT = "<I" + ("I" * OUT_VALUES_PER_IN_VALUE)
TEST_VECTOR_SIZE = struct.calcsize(TEST_VECTOR_FORMAT)
TEST_VECTOR_SHIFT = 32 - ALL_BITS

class OutItem:
    def __init__(self, values: typing.Tuple[int]) -> None:
        self.upper_bandpass = values[0]
        self.upper_rc = values[1]
        self.lower_bandpass = values[2]
        self.lower_rc = values[3]
        self.y = values[4]
        self.out_bit = (values[4] >> (ALL_BITS - 1)) & 1

class OutVector:
    def __init__(self, all_values: typing.List[int]) -> None:
        self.out_values: typing.List[OutItem] = []
        for i in range(0, len(all_values), OUT_VALUES_PER_IN_VALUE):
            self.out_values.append(OutItem(all_values[i:i + OUT_VALUES_PER_IN_VALUE]))

    def substitute_new_out_bits(self, out_bit_values: typing.List[int]) -> "OutVector":
        new_vector = OutVector([])
        for (out_bit, item) in zip(out_bit_values, self.out_values):
            item = copy(item)
            item.out_bit = out_bit
            new_vector.out_values.append(item)
        return new_vector

class TestVector(OutVector):
    def __init__(self, num_compare_tests: int) -> None:
        OutVector.__init__(self, [])
        self.in_values: typing.List[int] = []
        with open("generated/test_vector", "rb") as fd:
            test_vector_data = fd.read(TEST_VECTOR_SIZE)
            while (len(test_vector_data) == TEST_VECTOR_SIZE) and (len(self.in_values) < num_compare_tests):
                values = [v >> TEST_VECTOR_SHIFT for v in struct.unpack(TEST_VECTOR_FORMAT, test_vector_data)]
                self.in_values.append(values[0])
                self.out_values.append(OutItem(values[1:]))
                test_vector_data = fd.read(TEST_VECTOR_SIZE)

