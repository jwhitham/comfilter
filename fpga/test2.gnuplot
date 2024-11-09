

set terminal png size 1300,800

set xrange [ 0.005 : 0.015 ]
set yrange [ 0.0 : 6.0 ]
plot \
    "output.txt" using ($1 / 48000):(($2 / 32768) + 2) with lines title "input", \
    "output.txt" using ($1 / 48000):(($3 / 512) + 4) with lines title "output"
