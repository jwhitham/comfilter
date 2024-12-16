#!/bin/bash -xe

set -xe

export PATH=/j/GHDL/0.37-mingw32-mcode/bin:$PATH


# Build and packaging
G=generated
P=comfilter
rm -rf $P
mkdir $P
python microops/make_settings.py
python microops/filter_implementation.py

cat $G/settings.h c/packetgen.c > $P/packetgen.c
cp c/packetgen.h $P
cp fpga/banked_shift_register.vhdl $P
cp fpga/filter_unit.vhdl $P
cp fpga/shift_register.vhdl $P
cp fpga/subtractor.vhdl $P
cp fpga/debug_textio-body.vhdl $P
cp fpga/debug_textio.vhdl $P
cp $G/filter_unit_control_line_decoder.vhdl $P
cp $G/filter_unit_microcode_store.vhdl $P
cp $G/filter_unit_microcode_store.test.vhdl $P
cp $G/filter_unit_settings.vhdl $P
cp fpga/com_receiver.vhdl $P
cp fpga/pulse_gen.vhdl $P
cp fpga/crc.vhdl $P
cp fpga/comfilter_main.vhdl $P
git rev-parse HEAD > $P/version.txt
tar cvzf $P-$(git rev-parse HEAD).tar.gz $P

# Model test (C++)
gcc -o $G/siggen.exe model/siggen.c -Wall -Werror -g -lm -I$G
g++ -o $G/sigdec.exe model/sigdec.cpp -std=c++17 -Wall -Werror -g -lm -I$G
$G/siggen.exe test_data $G/signal.wav $G/debug_1
$G/sigdec.exe $G/signal.wav $G/output $G/test_vector $G/debug_2
#gnuplot model/test1.gnuplot > $G/t.png
cmp test_data $G/output

# Library test (C++)
gcc -o $G/packetgen.exe model/sigpacket.c -I$P $P/packetgen.c -Wall -Werror -g -lm -I$G
$G/packetgen.exe wav $G/packet.wav 1 2 4 8 16 32 64 128 256 512

# Functional test (Python only)
python microops/func_test.py

# Test VHDL components without microcode
cd $P
../fpga/test_crc.sh
../fpga/test_com_receiver.sh
cd ..

# Test VHDL components with microcode
python microops/ghdl_test.py

# Hardware test (use with fpga_test_project_top_bitmap.bin)
# python microops/fpga_test.py

