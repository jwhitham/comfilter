
RFLAGS = --assert-level=note

VHDL =

TEST_VHDL = \
		test/generated/test_signal_generator.vhdl \
		test/test_bandpass_filter.vhdl

all: run_tests

clean:
	ghdl --remove
	-rm -f generated/*

test/generated/signal.wav: ../test_data ../siggen.c
	gcc -o ../siggen.exe ../siggen.c -I.. -Wall -Werror -g  -O -lm
	../siggen.exe ../test_data test/generated/signal.wav

run_tests: test/generated/signal.wav
	ghdl --remove
	python test/make_test_bench.py
	ghdl -a --work=work $(VHDL) $(TEST_VHDL)
	ghdl -r test_bandpass_filter $(RFLAGS)
	echo "tests ok"
