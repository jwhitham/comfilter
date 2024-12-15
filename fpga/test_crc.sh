#!/bin/sh -xe
set -xe
RFLAGS=--assert-level=note

ghdl --remove
ghdl -a --work=comfilter \
        debug_textio.vhdl \
        debug_textio-body.vhdl \
        crc.vhdl \
        test_crc.vhdl
ghdl -r --work=comfilter test_crc ${RFLAGS}
echo "tests ok"
