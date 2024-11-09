#!/bin/bash -xe

set -xe
gcc -o siggen.exe siggen.c -Wall -Werror -g -lm
g++ -o sigdec.exe sigdec.cpp -std=c++17 -Wall -Werror -g -lm
./siggen.exe test_data signal.wav debug_1
./sigdec.exe signal.wav output debug_2
gnuplot test1.gnuplot > t.png
cmp test_data output

