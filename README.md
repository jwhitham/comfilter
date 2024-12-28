
COM Filter project
==================

This is an FPGA design for a digital filter which can be used
to decode data sent by
[frequency-shift keying](https://en.wikipedia.org/wiki/Frequency-shift_keying).
Data is sent at 300 baud by alternating a signal at two frequencies:
22kHz for "high" and 21kHz for "low". These are not the standard
frequencies used by
[Bell 103 modems](https://en.wikipedia.org/wiki/Bell_103_modem),
but the frequencies can be adjusted within
[microops/settings.py](/microops/settings.py) to match Bell 103 or
the ITU V.21 standard if desired.

The purpose of this project was:

- create a remote control for a [dynamic range compressor](https://github.com/jwhitham/spdif-bit-exactness-tools/tree/master/fpga) without using much FPGA space;
- experiment with creating a "bit-serial" CPU in which most operations are carried out one bit at a time;
- learn about digital filtering.

The end result is not technically a CPU, as it has no
capability to branch, access memory or load different programs, but
it is a close relative: a state machine which is driven by a microprogram
in ROM. The project files include C++ and Python models of the design,
with the Python model being a micro-operation level simulation.
The filters were originally derived from the biquad filter in
[SoX](https://sourceforge.net/projects/sox/): I had no
idea how to make a bandpass filter, and it was a lot simpler than
I realised, though I feel there is some "magic" in
[determining the correct filter coefficients](https://github.com/jwhitham/comfilter/blob/663e607e2e4538dde895cae969eb5a13094b95e8/microops/filter_implementation.py#L131-L144).
I could not work this out for myself; the original source code
[cites some references](https://github.com/jwhitham/comfilter/blob/292b828044ca698d06e4a9f8e49026c292e9739c/biquads.c).

Operation
---------

Whenever an audio sample is received by the module, it is processed
by two bandpass filters which are centred on the two frequencies,
22kHz and 21kHz. Each filtered audio signal is passed through an
"abs" function and then a low-pass filter which converts it to a
slowly-decaying level. A comparator, using these two levels, gives
an output bit which is 1 if the 22kHz (high) level is greater than the
21kHz (low) level. This output can be treated as an RS232-like signal
and sent to a serial port.

Actual 300 baud modems used a similar principle, though with analogue
filters created using op-amps. The technique is not very useful at
higher data rates and faster modems used different techniques.
