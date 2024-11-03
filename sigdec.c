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

#define UPPER_FREQUENCY         (10000)
#define LOWER_FREQUENCY         (5000)
#define FILTER_WIDTH            (100)
#define UPPER_AMPLITUDE         (0.10)
#define LOWER_AMPLITUDE         (0.05)
#define BAUD_RATE               (10)
#define BLOCK_SIZE              (1 << 14)
#define MAX_RING_BUFFER_SIZE    (500)


typedef struct threshold_decode_state_t {
    int16_t     ring_buffer[MAX_RING_BUFFER_SIZE];
    int64_t     total;
    bool        high;
    size_t      index;
    size_t      ring_buffer_size;
    int64_t     lower_threshold;
    int64_t     upper_threshold;
} threshold_decode_state_t;

static void threshold_decode(
                    threshold_decode_state_t* ds,
                    sox_sample_t* samples,
                    size_t num_samples,
                    bool* threshold)
{
    for (size_t i = 0; i < num_samples; i++) {
        int16_t sample = (int16_t) abs(samples[i] >> 16);
        ds->total -= (int64_t) ds->ring_buffer[ds->index];
        ds->ring_buffer[ds->index] = sample;
        ds->total += (int64_t) sample;
        ds->index++;
        if (ds->index >= ds->ring_buffer_size) {
            ds->index = 0;
        }

        if (ds->high) {
            if (ds->total < ds->lower_threshold) {
                ds->high = false;
            }
        } else {
            if (ds->total > ds->upper_threshold) {
                ds->high = true;
            }
        }
        threshold[i] = ds->high;
    }
}

typedef enum { ZERO = 0, ONE = 1, INVALID = -1 } bit_t;

typedef struct serial_decode_state_t {
    uint32_t    sample_countdown, half_bit;
    uint16_t    byte;
    bit_t       previous_bit;
} serial_decode_state_t;

static void serial_decode(
                    serial_decode_state_t* ds,
                    bool* upper_detect,
                    bool* lower_detect,
                    size_t num_samples,
                    FILE* out)
{
    for (size_t i = 0; i < num_samples; i++) {
        bit_t bit = INVALID;
        if (upper_detect[i] && !lower_detect[i]) {
            bit = ONE;
        } else if (lower_detect[i] && !upper_detect[i]) {
            bit = ZERO;
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

static void generate(FILE* fd_in, FILE* fd_out, FILE* fd_out2)
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
    fwrite(&header, 1, sizeof(header), fd_out);

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

    threshold_decode_state_t upper_decode_state, lower_decode_state;
    memset(&upper_decode_state, 0, sizeof(threshold_decode_state_t));
    upper_decode_state.ring_buffer_size = 2 * (header.sample_rate / UPPER_FREQUENCY);
    if (upper_decode_state.ring_buffer_size > MAX_RING_BUFFER_SIZE) {
        upper_decode_state.ring_buffer_size = MAX_RING_BUFFER_SIZE;
    }
    upper_decode_state.upper_threshold =
        (int64_t) ((((double) (1 << header.bits_per_sample) / 2)
            * (double) upper_decode_state.ring_buffer_size) * UPPER_AMPLITUDE);
    upper_decode_state.lower_threshold =
        (int64_t) ((((double) (1 << header.bits_per_sample) / 2)
            * (double) upper_decode_state.ring_buffer_size) * LOWER_AMPLITUDE);
    memcpy(&lower_decode_state, &upper_decode_state, sizeof(threshold_decode_state_t));

    serial_decode_state_t serial_decode_state;
    memset(&serial_decode_state, 0, sizeof(serial_decode_state_t));
    serial_decode_state.previous_bit = INVALID;
    serial_decode_state.half_bit = (header.sample_rate / BAUD_RATE) / 2;

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

        // Threshold decoding
        bool upper_detect[BLOCK_SIZE];
        bool lower_detect[BLOCK_SIZE];
        threshold_decode(&upper_decode_state, upper_output, (size_t) num_samples, upper_detect);
        threshold_decode(&lower_decode_state, lower_output, (size_t) num_samples, lower_detect);

        // Debug output .wav file shows filtering and detection
        for (i = 0; i < ((size_t) num_samples); i++) {
            samples[i].left = (upper_detect[i] ? 1 : -1) * (1 << (bits_per_sample - 2));
            samples[i].right = (lower_detect[i] ? 1 : -1) * (1 << (bits_per_sample - 2));
            samples[i].left += (int16_t) ((upper_output[i] >> (int32_t) bit_shift) >> 4);
            samples[i].right += (int16_t) ((lower_output[i] >> (int32_t) bit_shift) >> 4);
        }
        if (fwrite(samples, sizeof(t_stereo16), num_samples, fd_out) != num_samples) {
            perror("write error (debug wav)");
            exit(1);
        }

        // Serial decoding
        serial_decode(&serial_decode_state,
                      upper_detect,
                      lower_detect,
                      (size_t) num_samples,
                      fd_out2);
    }
}

int main(int argc, char ** argv)
{
    FILE *          fd_in;
    FILE *          fd_out;
    FILE *          fd_out2;

    if (argc != 4) {
        fprintf(stderr, "Usage: sigdec <signal.wav> <debug.wav> <data.bin>\n");
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
    fd_out2 = fopen(argv[3], "wb");
    if (!fd_out2) {
        perror("open (write)");
        return 1;
    }
    generate(fd_in, fd_out, fd_out2);
    fclose(fd_out2);
    fclose(fd_out);
    fclose(fd_in);
    return 0;
}

