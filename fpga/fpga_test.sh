#!/bin/bash -xe

set -xe

RFLAGS=--assert-level=note
pushd ..
python microops/filtersetup.py
python fpga/make_test_bench.py
popd

ghdl --remove
ghdl -a --work=work \
    ../generated/control_line_decoder.vhdl \
    ../generated/microcode_store.test.vhdl \
    ../generated/test_signal_generator.vhdl \
    shift_register.vhdl \
    banked_shift_register.vhdl \
    subtractor.vhdl \
    filter_unit.vhdl \
    test_top_level.vhdl
ghdl -r test_top_level $RFLAGS > output.txt
grep 'Reached the end' output.txt
