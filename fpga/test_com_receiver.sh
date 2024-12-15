#!/bin/sh -xe
set -xe
RFLAGS=--assert-level=note

pushd ..
python microops/filter_implementation.py
generated/packetgen.exe vhdl generated/test_packet_signal.vhdl 0xc001
popd

ghdl --remove
ghdl -a --work=comfilter \
        crc.vhdl \
        pulse_gen.vhdl \
        com_receiver.vhdl \
        ../generated/filter_unit_settings.vhdl \
        ../generated/test_packet_signal.vhdl \
        test_com_receiver.vhdl
ghdl -r --work=comfilter test_com_receiver ${RFLAGS}
echo "tests ok"
