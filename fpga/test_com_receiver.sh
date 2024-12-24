#!/bin/sh -xe
set -xe
RFLAGS=--assert-level=note

ghdl --remove
ghdl -a --work=comfilter \
        crc.vhdl \
        pulse_gen.vhdl \
        com_receiver.vhdl \
        filter_unit_settings.vhdl \
        ../generated/test_packet_signal.vhdl \
        ../fpga/test_com_receiver.vhdl
ghdl -r --work=comfilter test_com_receiver ${RFLAGS}
echo "tests ok"
