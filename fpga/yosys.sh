#!/bin/bash -xe

set -xe
export PATH=/opt/oss-cad-suite/bin:/opt/ghdl/bin:$PATH
ghdl --remove
ghdl -a --work=work  \
    "../generated/settings.vhdl" \
    "../generated/microcode_store.vhdl" \
    filter_main.vhdl
MAIN=filter_main

yosys -m ghdl -p "ghdl $MAIN; synth_ice40 -json $MAIN.json"
nextpnr-ice40 -r --hx8k --json $MAIN.json --package cb132 --asc $MAIN.asc --opt-timing --pcf project/ice40.pcf 
icepack $MAIN.asc $MAIN.bin

