#!/bin/bash -xe

set -xe
gcc -o siggen.exe siggen.c -Wall -Werror -g  -O -lm
gcc -o sigdec.exe sigdec.c biquads.c -Wall -Werror -g  -O -lm
./siggen.exe test_data signal.wav debug_1
xxd -g1 test_data
#echo Hello world | minimodem --tx --file x.wav 300
#sox x.wav y.wav channels 2
#./sigdec.exe y.wav output debug_2
./sigdec.exe signal.wav output debug_2
gnuplot test1.gnuplot > t.png
xxd -g1 output

