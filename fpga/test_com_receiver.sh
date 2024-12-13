#!/bin/sh -xe
set -xe
RFLAGS=--assert-level=note

ghdl -a --work=comfilter \
        crc.vhdl \
        pulse_gen.vhdl \
        com_receiver.vhdl \
        test_com_receiver.vhdl
ghdl -r --work=comfilter test_com_receiver ${RFLAGS}
echo "tests ok"
