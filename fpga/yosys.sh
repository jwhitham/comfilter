#!/bin/bash -xe

set -xe
cd ..
python microops/pattern_test.py
cd fpga
export PATH=/opt/oss-cad-suite/bin:/opt/ghdl/bin:$PATH
ghdl --remove
ghdl -a --work=work  \
    ../generated/settings.vhdl \
    filter_main.vhdl \
    project/filter_pll.vhd \
    project/filter_top.vhdl
MAIN=filter_top

yosys -p "synth_ice40 -json uc_store.json" ../generated/microcode_store.v
yosys -m ghdl -p "ghdl $MAIN; synth_ice40 -json $MAIN.json"
nextpnr-ice40 -r --hx8k --json $MAIN.json --json uc_store.json \
    --package cb132 --asc $MAIN.asc --opt-timing --pcf project/ice40.pcf 
icepack $MAIN.asc $MAIN.bin

