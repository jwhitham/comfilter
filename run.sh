#!/bin/bash -xe

set -xe
gcc -o siggen.exe siggen.c -Wall -Werror -g  -O -lm
gcc -o sigdec.exe sigdec.c biquads.c -Wall -Werror -g  -O -lm
./siggen.exe test_data signal.wav debug_1
cat test_data
./sigdec.exe signal.wav output debug_2
cat output
