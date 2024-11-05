

set terminal png

# debug_1
# column 1 - time in seconds
# column 2 - encoded signal
# column 3 - input bit
# debug_2
# column 1 - time in seconds
# column 2 - encoded signal
# column 3 - upper bandpass filter output
# column 4 - lower bandpass filter output
# column 5 - upper rectify and RC filter output
# column 6 - lower rectify and RC filter output
# column 7 - output bit

set xrange [ 0.0 : 0.1 ]
set yrange [ 0.0 : 16.0 ]
plot \
    "debug_1" using 1:( $2 + 12 ) with lines title "encoded signal", \
    "debug_2" using 1:( $3 + 10 ) with lines title "upper bandpass", \
    "debug_2" using 1:( $4 + 8 ) with lines title "lower bandpass", \
    "debug_2" using 1:( $5 + 6 ) with lines title "upper rectify", \
    "debug_2" using 1:( $6 + 4 ) with lines title "lower rectify", \
    "debug_1" using 1:( $3 + 2.1 ) with lines title "input bit", \
    "debug_2" using 1:( $7 + 2 ) with lines title "output bit"
