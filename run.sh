#!/bin/bash -xe

set -xe
gcc -o siggen.exe siggen.c -Wall -Werror -g  -O -lm
gcc -o sigdec.exe sigdec.c -Wall -Werror -g  -O -lm
./siggen.exe test_data signal.wav
sox signal.wav upper.wav vol 0.5 bandpass 10000 100h
sox signal.wav lower.wav vol 0.5 bandpass 5000 100h
./sigdec.exe upper.wav upper2.wav 
./sigdec.exe lower.wav lower2.wav 
