#!/bin/bash -xe

set -xe
G=generated
python microops/make_settings.py
gcc -o $G/siggen.exe model/siggen.c -Wall -Werror -g -lm -I$G
g++ -o $G/sigdec.exe model/sigdec.cpp -std=c++17 -Wall -Werror -g -lm -I$G
$G/siggen.exe test_data $G/signal.wav $G/debug_1
$G/sigdec.exe $G/signal.wav $G/output $G/test_vector $G/debug_2
#gnuplot model/test1.gnuplot > $G/t.png
cmp test_data $G/output
python microops/filter_implementation.py
python microops/func_test.py
