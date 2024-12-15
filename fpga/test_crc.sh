#!/bin/sh -xe
set -xe
RFLAGS=--assert-level=note

ghdl --remove
ghdl -a --work=comfilter \
        crc.vhdl \
        test_crc.vhdl
ghdl -r --work=comfilter test_crc ${RFLAGS}
echo "tests ok"
