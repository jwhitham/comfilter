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

#define ring_buffer_size (48000 / 20)
#define block_size (1 << 14)
static const uint32_t lower_threshold = (32768 * 1) / 10;
static const uint32_t upper_threshold = (32768 * 2) / 10;


typedef struct decode_state_t {
    int16_t     ring_buffer[ring_buffer_size];
    int64_t     total;
    bool        high;
    size_t      index;
} decode_state_t;

static void decode(decode_state_t* ds,
                    sox_sample_t* samples,
                    size_t num_samples,
                    bool* threshold)
{
    size_t i;
    for (i = 0; i < num_samples; i++) {
        int16_t sample = (int16_t) abs(samples[i] >> 16);
        ds->total -= (int64_t) ds->ring_buffer[ds->index];
        ds->ring_buffer[ds->index] = sample;
        ds->total += (int64_t) sample;
        ds->index++;
        if (ds->index >= ring_buffer_size) {
            ds->index = 0;
        }

        if (ds->high) {
            if (ds->total < ((int64_t) lower_threshold * (int64_t) ring_buffer_size)) {
                ds->high = false;
            }
        } else {
            if (ds->total > ((int64_t) upper_threshold * (int64_t) ring_buffer_size)) {
                ds->high = true;
            }
        }
        threshold[i] = ds->high;
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

    sox_effect_t    upper_filter;
    sox_effect_t    lower_filter;
    memset(&upper_filter, 0, sizeof(sox_effect_t));
    upper_filter.in_signal.rate = header.sample_rate;
    upper_filter.in_signal.channels = header.number_of_channels;
    upper_filter.in_signal.precision = header.bits_per_sample;
    memcpy(&lower_filter, &upper_filter, sizeof(sox_effect_t));
    if (lsx_biquad_start(&upper_filter, 10000, 100) != SOX_SUCCESS) {
        exit(1);
    }
    if (lsx_biquad_start(&lower_filter, 5000, 100) != SOX_SUCCESS) {
        exit(1);
    }

    decode_state_t  upper_decode, lower_decode;
    memset(&upper_decode, 0, sizeof(decode_state_t));
    memset(&lower_decode, 0, sizeof(decode_state_t));

    while (1) {
        t_stereo16   samples[block_size];
        sox_sample_t input[block_size];
        sox_sample_t upper_output[block_size];
        sox_sample_t lower_output[block_size];
        size_t isamp, osamp, i;

        // Input from .wav file
        ssize_t num_samples = fread(samples, sizeof(t_stereo16), block_size, fd_in);
        if (num_samples <= 0) {
            break;
        }

        for (i = 0; i < ((size_t) num_samples); i++) {
            input[i] = ((int32_t) samples[i].left) << 16;
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

        // Debug output .wav file
        for (i = 0; i < ((size_t) num_samples); i++) {
            samples[i].left = (int16_t) (upper_output[i] >> (int32_t) 16);
            samples[i].right = (int16_t) (lower_output[i] >> (int32_t) 16);
        }
        if (fwrite(samples, sizeof(t_stereo16), num_samples, fd_out) != num_samples) {
            perror("write error (debug wav)");
            exit(1);
        }

        // Threshold decoding
        bool upper_threshold[block_size];
        bool lower_threshold[block_size];
        decode(&upper_decode, upper_output, (size_t) num_samples, upper_threshold);
        decode(&lower_decode, lower_output, (size_t) num_samples, lower_threshold);

        // Serial decoding
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

