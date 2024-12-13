#!/bin/sh -xe
set -xe
RFLAGS=--assert-level=note

ghdl -a --work=comfilter \
        crc.vhdl \
        crc_test.vhdl
ghdl -r --work=comfilter crc_test ${RFLAGS}
echo "tests ok"
