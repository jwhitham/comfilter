// Suggested compile command: gcc -o sigdec.exe sigdec.c -Wall -Werror -g  -O -lm
//
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#include <limits.h>
#include <stdbool.h>

#include "wave.h"
#include "biquad.h"
#include "settings.h"

#define FILTER_WIDTH            (100)
#define THRESHOLD_AMPLITUDE     (0.05)
#define BLOCK_SIZE              (1 << 14)
#define MAX_RING_BUFFER_SIZE    (500)


typedef struct window_max_state_t {
    double      level;
    double      decay;
} window_max_state_t;

static void window_max_setup(
                    window_max_state_t* ds,
                    t_header* header,
                    uint32_t frequency)
{
    memset(ds, 0, sizeof(window_max_state_t));
    // Amplitude should decay below the threshold in half a bit
    const double samples_to_decay_below_threshold =
        ((double) header->sample_rate / (double) BAUD_RATE) / 0.25;
    // This is the time constant, like k = 1 / RC for a capacitor discharging
    // Level is y = y0 * exp(-kt) at time t, assuming level was y0 at time 0
    const double time_constant = log(THRESHOLD_AMPLITUDE) / -samples_to_decay_below_threshold;
    // Each transition from t to t+1 is a multiplication by exp(-k)
    ds->decay = exp(-time_constant);
}

static void window_max(
                    window_max_state_t* ds,
                    sox_sample_t* samples,
                    size_t num_samples,
                    double* levels)
{
    for (size_t i = 0; i < num_samples; i++) {
        double sample = ((double) samples[i]) / ((double) INT_MAX);
        ds->level *= ds->decay;
        if (sample > ds->level) {
            ds->level = sample;
        }
        levels[i] = ds->level;
    }
}

typedef enum { ZERO = 0, ONE = 1, INVALID = -1 } bit_t;

typedef struct serial_decode_state_t {
    uint32_t    sample_countdown, half_bit;
    uint16_t    byte;
    bit_t       previous_bit;
    double      threshold;
} serial_decode_state_t;

static void serial_decode(
                    serial_decode_state_t* ds,
                    double* upper_levels,
                    double* lower_levels,
                    size_t num_samples,
                    FILE* out)
{
    for (size_t i = 0; i < num_samples; i++) {
        bit_t bit = INVALID;
        if ((upper_levels[i] > ds->threshold)
        || (lower_levels[i] > ds->threshold)) {
            if (upper_levels[i] > lower_levels[i]) {
                bit = ONE;
            } else {
                bit = ZERO;
            }
        }
        if (ds->sample_countdown == 0) {
            if ((ds->previous_bit != bit) && (bit == ONE)) {
                ds->sample_countdown = ds->half_bit * 3;
                ds->byte = 1;
            }
        } else if (ds->sample_countdown == 1) {
            ds->sample_countdown--;
            if (ds->byte & 0x100) {
                // stop bit reached
                switch (bit) {
                    case ZERO:
                        fputc(ds->byte & 0xff, out);
                        break;
                    case ONE:
                        printf("framing error - stop bit is 1\n");
                        break;
                    default:
                        printf("framing error - stop bit is invalid\n");
                        break;
                }
                ds->byte = 0;
            } else {
                // data bit
                ds->sample_countdown = ds->half_bit * 2;
                ds->byte = ds->byte << 1;
                switch (bit) {
                    case ONE:
                        ds->byte |= 1;
                        break;
                    case ZERO:
                        break;
                    default:
                        printf("framing error - data bit is invalid\n");
                        ds->sample_countdown = 0;
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
    || (header.number_of_channels != 2)
    || (header.bytes_per_second != (header.sample_rate * header.bytes_per_period))
    || (header.bits_per_sample != ((header.bytes_per_period / header.number_of_channels) * 8))
    || (memcmp(header.fixed_data, "data", 4) != 0)
    || (header.bytes_per_period != sizeof(t_stereo16))
    || (header.bits_per_sample != 16)) {
        fprintf(stderr, "Format is incorrect - needs to be a simple stereo PCM file, 16 bit\n");
        exit(1);
    }

    // Check endianness
    if (((uint32_t *) &header.fixed_riff)[0] != 0x46464952) {
        fprintf(stderr, "endianness error (little endian assumed, sorry)\n");
        exit(1);
    }

    const int32_t bits_per_sample = header.bits_per_sample;
    const int32_t bit_shift = 32 - bits_per_sample;

    sox_effect_t    upper_filter;
    sox_effect_t    lower_filter;
    memset(&upper_filter, 0, sizeof(sox_effect_t));
    upper_filter.in_signal.rate = header.sample_rate;
    upper_filter.in_signal.channels = header.number_of_channels;
    upper_filter.in_signal.precision = header.bits_per_sample;
    memcpy(&lower_filter, &upper_filter, sizeof(sox_effect_t));
    if (lsx_biquad_start(&upper_filter, UPPER_FREQUENCY, FILTER_WIDTH) != SOX_SUCCESS) {
        exit(1);
    }
    if (lsx_biquad_start(&lower_filter, LOWER_FREQUENCY, FILTER_WIDTH) != SOX_SUCCESS) {
        exit(1);
    }

    window_max_state_t upper_decode_state, lower_decode_state;
    window_max_setup(&upper_decode_state, &header, UPPER_FREQUENCY); 
    window_max_setup(&lower_decode_state, &header, LOWER_FREQUENCY); 

    serial_decode_state_t serial_decode_state;
    memset(&serial_decode_state, 0, sizeof(serial_decode_state_t));
    serial_decode_state.previous_bit = INVALID;
    serial_decode_state.half_bit = (header.sample_rate / BAUD_RATE) / 2;
    serial_decode_state.threshold = THRESHOLD_AMPLITUDE;

    uint64_t sample_count = 0;

    while (1) {
        t_stereo16   samples[BLOCK_SIZE];
        sox_sample_t input[BLOCK_SIZE];
        sox_sample_t upper_output[BLOCK_SIZE];
        sox_sample_t lower_output[BLOCK_SIZE];
        size_t isamp, osamp, i;

        // Input from .wav file
        ssize_t num_samples = fread(samples, sizeof(t_stereo16), BLOCK_SIZE, fd_in);
        if (num_samples <= 0) {
            break;
        }

        for (i = 0; i < ((size_t) num_samples); i++) {
            input[i] = ((int32_t) samples[i].left) << bit_shift;
        }
        // Higher frequency filter
        isamp = osamp = (size_t) num_samples;
        if (lsx_biquad_flow(&upper_filter, input, upper_output, &isamp, &osamp) != SOX_SUCCESS) {
            fprintf(stderr, "upper filter fail\n");
            exit(1);
        }
        size_t upper_num_samples = osamp;

        // Lower frequency filter
        isamp = osamp = (size_t) num_samples;
        if (lsx_biquad_flow(&lower_filter, input, lower_output, &isamp, &osamp) != SOX_SUCCESS) {
            fprintf(stderr, "lower filter fail\n");
            exit(1);
        }
        size_t lower_num_samples = osamp;
        if (upper_num_samples != lower_num_samples) {
            fprintf(stderr, "filter output inconsistency\n");
            exit(1);
        }
        num_samples = lower_num_samples;

        // Level
        double upper_levels[BLOCK_SIZE];
        double lower_levels[BLOCK_SIZE];
        window_max(&upper_decode_state, upper_output, (size_t) num_samples, upper_levels);
        window_max(&lower_decode_state, lower_output, (size_t) num_samples, lower_levels);

        // Debug output shows filtering and detection
        for (i = 0; i < ((size_t) num_samples); i++) {
            fprintf(fd_debug, "%7.5f ", (double) sample_count / (double) header.sample_rate); // time
            fprintf(fd_debug, "%7.4f ", (double) input[i] / (double) INT_MAX); // encoded signal
            fprintf(fd_debug, "%7.4f ", (double) upper_output[i] / (double) INT_MAX); // upper bandpass filter output
            fprintf(fd_debug, "%7.4f ", (double) lower_output[i] / (double) INT_MAX); // lower bandpass filter output
            fprintf(fd_debug, "%7.4f ", upper_levels[i]); // upper, rectify and RC filter
            fprintf(fd_debug, "%7.4f ", lower_levels[i]); // lower, rectify and RC filter

            if ((upper_levels[i] > serial_decode_state.threshold)
            || (lower_levels[i] > serial_decode_state.threshold)) {
                if (upper_levels[i] > lower_levels[i]) {
                    fprintf(fd_debug, "1 ");
                } else {
                    fprintf(fd_debug, "0 ");
                }
            } else {
                fprintf(fd_debug, "- ");
            }
            fprintf(fd_debug, "\n");
            sample_count++;
        }

        // Serial decoding
        serial_decode(&serial_decode_state,
                      upper_levels,
                      lower_levels,
                      (size_t) num_samples,
                      fd_out);
    }
}

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

