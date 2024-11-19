#!/bin/bash -xe

set -xe
G=generated
gcc -o $G/siggen.exe model/siggen.c -Wall -Werror -g -lm
g++ -o $G/sigdec.exe model/sigdec.cpp -std=c++17 -Wall -Werror -g -lm
$G/siggen.exe test_data $G/signal.wav $G/debug_1
$G/sigdec.exe $G/signal.wav $G/output $G/test_vector $G/debug_2
gnuplot model/test1.gnuplot > $G/t.png
cmp test_data $G/output
python microops/filtersetup.py
python microops/filtertest.py
python fpga/make_test_bench.py
