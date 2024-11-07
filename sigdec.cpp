// Suggested compile command: g++ -o sigdec.exe sigdec.cpp -Wall -Werror -g  -O -lm -std=c++17
//
#include <stdio.h>
#include <string.h>
#include <cstdint>
#include <stdlib.h>
#include <math.h>
#include <limits.h>
#include <stdbool.h>

#include "wave.h"
#include "settings.h"

#define BLOCK_SIZE              (1 << 14)
#define FILTER_WIDTH            (100)
#define MINIMUM_AMPLITUDE       (0.1)
#define SCHMITT_THRESHOLD       (0.7)
#define RC_DECAY_PER_BIT        (0.1)

namespace {

struct fixed_t {
public:
    fixed_t() : m_value(0.0) {}
    fixed_t(const double value) : m_value(value) {
        if (fabs(value) >= 2.0) {
            fprintf(stderr, "Fixed point value out of range: %1.3f\n", value);
            exit(1);
        }
    }
    fixed_t(const std::int16_t value) : m_value((double) value / (double) INT16_MAX) {}

    fixed_t operator*(const fixed_t& other) {
        return fixed_t(m_value * other.m_value);
    }
    fixed_t operator+(const fixed_t& other) {
        return fixed_t(m_value + other.m_value);
    }
    fixed_t operator-(const fixed_t& other) {
        return fixed_t(m_value - other.m_value);
    }
    fixed_t operator/(const fixed_t& other) {
        return fixed_t(m_value / other.m_value);
    }
    bool operator>(const fixed_t& other) {
        return m_value > other.m_value;
    }
    double to_double() {
        return m_value;
    }
private:
    double m_value;
};

struct my_filter_state_t {
    my_filter_state_t() {};
    fixed_t a0, a1, a2;
    fixed_t b0, b1, b2;
    fixed_t i1, i2;
    fixed_t o1, o2;
};

static void my_filter_setup(
                my_filter_state_t* mf,
                t_header* header,
                double frequency,
                double width) {
    const double w0 = 2 * M_PI * frequency / (double) header->sample_rate;
    const double alpha = sin(w0)/(2*frequency/width);
    double b0 =   alpha;
    double b1 =   0;
    double b2 =  -alpha;
    double a0 =   1 + alpha;
    double a1 =  -2*cos(w0);
    double a2 =   1 - alpha;
    b2 /= a0;
    b1 /= a0;
    b0 /= a0;
    a2 /= a0;
    a1 /= a0;
    printf("Matrix for frequency %1.0f Hz width %1.0f Hz\n", frequency, width);
    printf("   w0 = %14.6e a  = %14.6e\n", w0, alpha);
    printf("   a0 = %14.6e a1 = %14.6e a2 = %14.6e\n", a0, a1, a2);
    printf("   b0 = %14.6e b1 = %14.6e b2 = %14.6e\n", b0, b1, b2);
    mf->b0 = fixed_t(b0);
    mf->b1 = fixed_t(b1);
    mf->b2 = fixed_t(b2);
    mf->a0 = fixed_t(a0);
    mf->a1 = fixed_t(a1);
    mf->a2 = fixed_t(a2);
}

static void my_filter(
                my_filter_state_t* mf,
                fixed_t* input,
                fixed_t* output,
                size_t num_samples) {

    for (size_t i = 0; i < num_samples; i++) {
        fixed_t i0 = input[i];
        fixed_t o0 = i0*mf->b0 + mf->i1*mf->b1 + mf->i2*mf->b2 - mf->o1*mf->a1 - mf->o2*mf->a2;
        mf->i2 = mf->i1;
        mf->i1 = i0;
        mf->o2 = mf->o1;
        mf->o1 = o0;
        output[i] = o0;
    }
}

struct rc_filter_state_t {
    rc_filter_state_t() {};
    fixed_t      level;
    fixed_t      decay;
};

static void rc_filter_setup(
                    rc_filter_state_t* ds,
                    t_header* header,
                    std::uint32_t frequency)
{
    // Number of samples per bit
    const double bit_samples = ((double) header->sample_rate / (double) BAUD_RATE);
    // This is the time constant, like k = 1 / RC for a capacitor discharging
    // Note: Level is y = exp(-kt) at time t, assuming level was 1.0 at time 0
    // The level should be reduced from 1.0 to RC_DECAY_PER_BIT during each bit
    const double time_constant = log(RC_DECAY_PER_BIT) / -bit_samples;
    // Each transition from t to t+1 is a multiplication by exp(-k)
    ds->decay = fixed_t(exp(-time_constant));
}

static void rc_filter(
                    rc_filter_state_t* ds,
                    fixed_t* samples,
                    size_t num_samples,
                    fixed_t* levels)
{
    for (size_t i = 0; i < num_samples; i++) {
        fixed_t sample = samples[i];
        ds->level = ds->level * ds->decay;
        if (sample > ds->level) {
            ds->level = sample;
        }
        levels[i] = ds->level;
    }
}

typedef enum { ZERO, ONE, INVALID } bit_t;
typedef enum { STOP, STOP_ERROR, START,
               DATA_0, DATA_1, DATA_ERROR,
               NOTHING } identified_t;


typedef struct serial_decode_state_t {
    std::uint32_t   sample_countdown, half_bit;
    std::uint32_t   byte_countdown;
    std::uint8_t    byte;
    bit_t           previous_bit;
} serial_decode_state_t;

static void serial_decode(
                    serial_decode_state_t* ds,
                    fixed_t* upper_levels,
                    fixed_t* lower_levels,
                    identified_t* identified,
                    bit_t* received_bit,
                    size_t num_samples,
                    FILE* out)
{
    for (size_t i = 0; i < num_samples; i++) {
        bit_t bit = ds->previous_bit;
        fixed_t sum = upper_levels[i] + lower_levels[i];
        if (fixed_t(MINIMUM_AMPLITUDE) > sum) {
            bit = INVALID;
        } else if ((upper_levels[i] > (sum * fixed_t(SCHMITT_THRESHOLD)))
        && ((bit == ZERO) || (bit == INVALID))) {
            bit = ONE;
        } else if ((lower_levels[i] > (sum * fixed_t(SCHMITT_THRESHOLD)))
        && ((bit == ONE) || (bit == INVALID))) {
            bit = ZERO;
        }
        identified[i] = NOTHING;
        received_bit[i] = bit;
        if (ds->sample_countdown == 0) {
            if ((ds->previous_bit != bit) && (bit == ZERO)) {
                ds->sample_countdown = ds->half_bit * 3;
                ds->byte_countdown = 8;
                ds->byte = 0;
                identified[i] = START;
            }
        } else if (ds->sample_countdown == 1) {
            ds->sample_countdown--;
            if (ds->byte_countdown == 0) {
                // stop bit reached
                switch (bit) {
                    case ONE:
                        fputc(ds->byte, out);
                        identified[i] = STOP;
                        break;
                    case ZERO:
                        printf("framing error - stop bit is 0\n");
                        identified[i] = STOP_ERROR;
                        break;
                    default:
                        printf("framing error - stop bit is invalid\n");
                        identified[i] = STOP_ERROR;
                        break;
                }
                ds->byte = 0;
            } else {
                // data bit
                ds->sample_countdown = ds->half_bit * 2;
                ds->byte_countdown--;
                ds->byte = ds->byte >> 1;
                switch (bit) {
                    case ONE:
                        ds->byte |= 0x80;
                        identified[i] = DATA_1;
                        break;
                    case ZERO:
                        identified[i] = DATA_0;
                        break;
                    default:
                        printf("framing error - data bit is invalid\n");
                        ds->sample_countdown = 0;
                        identified[i] = DATA_ERROR;
                        break;
                }
            }
        } else {
            ds->sample_countdown--;
        }
        ds->previous_bit = bit;
    }
}

static void generate(FILE* fd_in, FILE* fd_out, FILE* fd_debug)
{
    t_header        header;

    // Read wav header
    if (fread(&header, sizeof(header), 1, fd_in) != 1) {
        perror("read header");
        exit(1);
    }

    if ((memcmp(header.fixed_riff, "RIFF", 4) != 0)
    || (memcmp(header.fixed_wave, "WAVE", 4) != 0)
    || (memcmp(header.fixed_fmt, "fmt ", 4) != 0)
    || (header.length_of_format_data != 16)
    || (header.type_of_format != 1) // WAVE_FORMAT_PCM
    || (header.number_of_channels != 1)
    || (header.bytes_per_second != (header.sample_rate * header.bytes_per_period))
    || (header.bits_per_sample != ((header.bytes_per_period / header.number_of_channels) * 8))
    || (memcmp(header.fixed_data, "data", 4) != 0)
    || (header.bytes_per_period != sizeof(std::int16_t))
    || (header.bits_per_sample != 16)) {
        fprintf(stderr, "Format is incorrect - needs to be a simple mono PCM file, 16 bit\n");
        exit(1);
    }

    // Check endianness
    if (((std::uint32_t *) &header.fixed_riff)[0] != 0x46464952) {
        fprintf(stderr, "endianness error (little endian assumed, sorry)\n");
        exit(1);
    }

    my_filter_state_t upper_filter;
    my_filter_state_t lower_filter;
    my_filter_setup(&upper_filter, &header, UPPER_FREQUENCY, FILTER_WIDTH);
    my_filter_setup(&lower_filter, &header, LOWER_FREQUENCY, FILTER_WIDTH);

    rc_filter_state_t upper_decode_state;
    rc_filter_state_t lower_decode_state;
    rc_filter_setup(&upper_decode_state, &header, UPPER_FREQUENCY); 
    rc_filter_setup(&lower_decode_state, &header, LOWER_FREQUENCY); 

    serial_decode_state_t serial_decode_state;
    memset(&serial_decode_state, 0, sizeof(serial_decode_state_t));
    serial_decode_state.previous_bit = INVALID;
    serial_decode_state.half_bit = (header.sample_rate / BAUD_RATE) / 2;

    uint64_t sample_count = 0;

    while (1) {
        std::int16_t samples[BLOCK_SIZE];
        fixed_t input[BLOCK_SIZE];
        fixed_t upper_output[BLOCK_SIZE];
        fixed_t lower_output[BLOCK_SIZE];
        size_t i;

        // Input from .wav file
        ssize_t num_samples = fread(samples, sizeof(std::int16_t), BLOCK_SIZE, fd_in);
        if (num_samples <= 0) {
            break;
        }

        for (i = 0; i < ((size_t) num_samples); i++) {
            input[i] = fixed_t(samples[i]);
        }
        // Bandpass filters
        my_filter(&upper_filter, input, upper_output, num_samples);
        my_filter(&lower_filter, input, lower_output, num_samples);

        // Level
        fixed_t upper_levels[BLOCK_SIZE];
        fixed_t lower_levels[BLOCK_SIZE];
        rc_filter(&upper_decode_state, upper_output, (size_t) num_samples, upper_levels);
        rc_filter(&lower_decode_state, lower_output, (size_t) num_samples, lower_levels);

        // Serial decoding
        identified_t identified[BLOCK_SIZE];
        bit_t received_bit[BLOCK_SIZE];
        serial_decode(&serial_decode_state,
                      upper_levels,
                      lower_levels,
                      identified,
                      received_bit,
                      (size_t) num_samples,
                      fd_out);

        // Debug output shows filtering and detection
        for (i = 0; i < ((size_t) num_samples); i++) {
            fprintf(fd_debug, "%7.5f ", (double) sample_count / (double) header.sample_rate); // time
            fprintf(fd_debug, "%7.4f ", input[i].to_double() / (double) INT_MAX); // encoded signal
            fprintf(fd_debug, "%7.4f ", upper_output[i].to_double() / (double) INT_MAX); // upper bandpass filter output
            fprintf(fd_debug, "%7.4f ", lower_output[i].to_double() / (double) INT_MAX); // lower bandpass filter output
            fprintf(fd_debug, "%7.4f ", upper_levels[i].to_double()); // upper, rectify and RC filter
            fprintf(fd_debug, "%7.4f ", lower_levels[i].to_double()); // lower, rectify and RC filter

            switch(received_bit[i]) {
                case ZERO:          fprintf(fd_debug, "0 "); break;
                case ONE:           fprintf(fd_debug, "1 "); break;
                default:            fprintf(fd_debug, "- "); break;
            }
            switch(identified[i]) {
                case DATA_0:        fprintf(fd_debug, "0 "); break;
                case DATA_1:        fprintf(fd_debug, "1 "); break;
                case START:         fprintf(fd_debug, "2 "); break;
                case STOP:          fprintf(fd_debug, "3 "); break;
                case DATA_ERROR:    fprintf(fd_debug, "4 "); break;
                case STOP_ERROR:    fprintf(fd_debug, "5 "); break;
                default:            fprintf(fd_debug, "- "); break;
            }
            fprintf(fd_debug, "\n");
            sample_count++;
        }
    }
}

} // namespace

int main(int argc, char ** argv)
{
    FILE *          fd_in;
    FILE *          fd_out;
    FILE *          fd_debug;

    if (argc != 4) {
        fprintf(stderr, "Usage: sigdec <signal.wav> <data output> <debug output>\n");
        return 1;
    }

    fd_in = fopen(argv[1], "rb");
    if (!fd_in) {
        perror("open (read)");
        return 1;
    }
    fd_out = fopen(argv[2], "wb");
    if (!fd_out) {
        perror("open (write)");
        return 1;
    }
    fd_debug = fopen(argv[3], "wt");
    if (!fd_debug) {
        perror("open (write)");
        return 1;
    }
    generate(fd_in, fd_out, fd_debug);
    fclose(fd_debug);
    fclose(fd_out);
    fclose(fd_in);
    return 0;
}

