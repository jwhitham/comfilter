#!/bin/bash -xe

set -xe
count=0
gcc -o siggen.exe siggen.c -Wall -Werror -g  -O -lm
g++ -o sigdec.exe sigdec.cpp -std=c++17 -Wall -Werror -g  -O -lm
TI=/tmp/test-input-$$
while test $count -lt 1000
do
    dd if=/dev/urandom of=$TI bs=1k count=1
    ./siggen.exe $TI signal.wav
    ./sigdec.exe signal.wav output
    cmp $TI output
    count=$(( $count + 1 ))
done

