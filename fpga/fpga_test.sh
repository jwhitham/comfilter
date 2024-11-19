#!/bin/bash -xe

set -xe

RFLAGS=--assert-level=note

TEST_VHDL=\
		../generated/test_signal_generator.vhdl \
        ../generated/control_line_decoder.vhdl \
        ../generated/microcode_store.test.vhdl \
		test_top_level.vhdl

ghdl --remove
ghdl -a --work=work $TEST_VHDL
ghdl -r test_top_level $RFLAGS > output.txt
grep 'Reached the end' output.txt
