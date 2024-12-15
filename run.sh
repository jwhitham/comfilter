#!/bin/bash -xe

set -xe

export PATH=/j/GHDL/0.37-mingw32-mcode/bin:$PATH

G=generated
python microops/make_settings.py
gcc -o $G/siggen.exe model/siggen.c -Wall -Werror -g -lm -I$G
gcc -o $G/packetgen.exe model/packetgen.c -Wall -Werror -g -lm -I$G
g++ -o $G/sigdec.exe model/sigdec.cpp -std=c++17 -Wall -Werror -g -lm -I$G
$G/siggen.exe test_data $G/signal.wav $G/debug_1
$G/sigdec.exe $G/signal.wav $G/output $G/test_vector $G/debug_2
#gnuplot model/test1.gnuplot > $G/t.png
cmp test_data $G/output
python microops/filter_implementation.py
$G/packetgen.exe wav $G/packet.wav 0xc001


cd fpga
./test_crc.sh
./test_com_receiver.sh
cd ..
python microops/ghdl_test.py
python microops/func_test.py

# hardware test:
# python microops/fpga_test.py
