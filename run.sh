#!/bin/bash -xe

set -xe
gcc -o siggen.exe siggen.c -Wall -Werror -g  -O -lm
gcc -o sigdec.exe sigdec.c -Wall -Werror -g  -O -lm
./siggen.exe test_data signal.wav debug_1
xxd -g1 test_data
#minimodem --rx --file signal.wav 300
#cat test_data test_data test_data | minimodem --tx --file signal.wav 300
./sigdec.exe signal.wav output debug_2
gnuplot test1.gnuplot > t.png
xxd -g1 output

