// Suggested compile command: gcc -o sigdec.exe sigdec.c -Wall -Werror -g  -O -lm
//
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#include <limits.h>

#include "wave.h"

#define ring_buffer_size (48000 / 20)
#define block_size (1 << 14)
static const uint32_t lower_threshold = (32768 * 1) / 10;
static const uint32_t upper_threshold = (32768 * 2) / 10;


typedef struct t_decode_state {
    int16_t     ring_buffer[ring_buffer_size];
    int64_t     total;
    int16_t     high;
    uint32_t    index;
} t_decode_state;

static void decode(t_decode_state* ds,
                    t_stereo16* samples,
                    uint32_t num_samples,
                    FILE* fd_out2)
{
    uint32_t i;
    for (i = 0; i < num_samples; i++) {
        int16_t sample = (int16_t) abs(samples[i].left);
        ds->total -= (int64_t) ds->ring_buffer[ds->index];
        ds->ring_buffer[ds->index] = sample;
        ds->total += (int64_t) sample;
        ds->index++;
        if (ds->index >= ring_buffer_size) {
            ds->index = 0;
        }

        if (ds->high) {
            if (ds->total < ((int64_t) lower_threshold * (int64_t) ring_buffer_size)) {
                ds->high = 0;
            }
        } else {
            if (ds->total > ((int64_t) upper_threshold * (int64_t) ring_buffer_size)) {
                ds->high = 1;
            }
        }
        samples[i].right = (1 | (ds->total / ring_buffer_size)) * (ds->high ? 1 : -1);
        if (fputc(ds->high ? '1' : '0', fd_out2) == EOF) {
            perror("write error (data.bin)");
            exit(1);
        }
    }
}


static void generate(FILE* fd_in, FILE* fd_out, FILE* fd_out2)
{
    t_header        header;
    t_stereo16      samples[block_size];
    t_decode_state  decode_state;

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

    memset(&decode_state, 0, sizeof(decode_state));

    // Decode data
    while (1) {
        ssize_t num_samples = fread(samples, sizeof(t_stereo16), block_size, fd_in);
        if (num_samples <= 0) {
            break;
        }
        decode(&decode_state, samples, (uint32_t) num_samples, fd_out2);
        if (fwrite(samples, sizeof(t_stereo16), num_samples, fd_out) != num_samples) {
            perror("write error (debug wav)");
            exit(1);
        }
    }
}

int main(int argc, char ** argv)
{
    FILE *          fd_in;
    FILE *          fd_out;
    FILE *          fd_out2;

    if (argc != 4) {
        fprintf(stderr, "Usage: sigdec <lower/upper.wav> <debug.wav> <data.bin>\n");
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

