

set terminal png size 1300,800

# debug_1
# column 1 - time in seconds
# column 2 - encoded signal (upper)
# column 3 - encoded signal (lower)
# column 4 - input bit
# debug_2
# column 1 - time in seconds
# column 2 - encoded signal (mixed)
# column 3 - upper bandpass filter output
# column 4 - lower bandpass filter output
# column 5 - upper rectify and RC filter output
# column 6 - lower rectify and RC filter output
# column 7 - output bit

set xrange [ 0.45 : 0.65 ]
set yrange [ 0.0 : 14.0 ]
plot \
    "debug_1" using 1:( $2 + 12 ) with lines title "encoded signal (upper)", \
    "debug_1" using 1:( $3 + 12 ) with lines title "encoded signal (lower)", \
    "debug_2" using 1:( $3 + 10 ) with lines title "upper bandpass", \
    "debug_2" using 1:( $4 + 8 ) with lines title "lower bandpass", \
    "debug_2" using 1:( $5 + 6 ) with lines title "upper rectify", \
    "debug_2" using 1:( $6 + 4 ) with lines title "lower rectify", \
    "debug_1" using 1:( $4 + 2 ) with lines title "input bit", \
    "debug_2" using 1:( $7 + 0.5 ) with lines title "output bit", \
    "debug_2" using 1:( $8 ) with points title "identified"
