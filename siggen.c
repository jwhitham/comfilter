// Suggested compile command: gcc -o siggen.exe siggen.c -Wall -Werror -g  -O -lm
//
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#include <limits.h>


typedef struct t_header {
    uint8_t     fixed_riff[4];      // 0
    uint32_t    file_size;          // 4
    uint8_t     fixed_wave[4];      // 8
    uint8_t     fixed_fmt[4];       // c
    uint32_t    length_of_format_data;  // 10
    uint16_t    type_of_format;         // 14
    uint16_t    number_of_channels;     // 16
    uint32_t    sample_rate;            // 18
    uint32_t    bytes_per_second;       // 1c
    uint16_t    bytes_per_sample;       // 20
    uint16_t    bits_per_sample;        // 22
    uint8_t     fixed_data[4];          // 24
    uint32_t    data_size;              // 28
} t_header;

typedef struct t_stereo32 {
    int32_t     left;
    int32_t     right;
} t_stereo32;

typedef struct t_stereo16 {
    int16_t     left;
    int16_t     right;
} t_stereo16;

static const uint32_t allowed_sample_rate[] = {
    32000, 44100, 48000, 88200, 96000, 0};

static const uint32_t block_size = 1 << 14;

static void generate(const uint32_t sample_rate, uint32_t bits, double frequency, FILE* fd_out)
{
    t_header        header;
    const uint32_t  wav_length = 15;    // seconds
    const uint32_t  bytes_per_sample = (bits == 16) ? 2 : 4;
    t_stereo32      samples[block_size];
    const uint32_t  num_blocks = (sample_rate * 2 * wav_length) / block_size;
    const uint32_t  num_samples = num_blocks * block_size;
    uint32_t        i = 0;
    uint32_t        j = 0;
    double          angle = 0.0;
    double          delta = ((M_PI * 2.0) / (double) sample_rate) * frequency;

    // Write wav header
    memset(&header, 0, sizeof(header));
    memcpy(header.fixed_riff, "RIFF", 4);
    memcpy(header.fixed_wave, "WAVE", 4);
    memcpy(header.fixed_fmt, "fmt ", 4);
    header.length_of_format_data = 16;
    header.type_of_format = 1; // WAVE_FORMAT_PCM
    header.number_of_channels = 2;
    header.sample_rate = sample_rate;
    header.bytes_per_second = header.sample_rate * bytes_per_sample * 2;
    header.bytes_per_sample = bytes_per_sample;
    header.bits_per_sample = bytes_per_sample * 8;
    memcpy(header.fixed_data, "data", 4);
    header.data_size = num_samples * bytes_per_sample * 2;
    header.file_size = header.data_size + sizeof(t_header);
    fwrite(&header, 1, sizeof(header), fd_out);

    // Check endianness
    if (((uint32_t *) &header.fixed_riff)[0] != 0x46464952) {
        fprintf(stderr, "endianness error (little endian assumed, sorry)\n");
        exit(1);
    }

    // Generate repeating sample
    memset(&samples, 0, sizeof(samples));

    for (j = 0; j < num_blocks; j++) {
        // First part of the repeating block: walking 1s (24 samples)
        for (i = 0; i < block_size; i++) {
            samples[i].left = samples[i].right =
                floor((sin(angle) * (double) (INT_MAX - 1)) + 0.5);
            angle += delta;
            if (angle > (M_PI * 2.0)) {
                angle -= M_PI * 2.0;
            }
        }

        if (bits == 16) {
            // Convert 32-bit to 16-bit
            t_stereo16      samples16[block_size];

            for (i = 0; i < block_size; i++) {
                samples16[i].left = (uint32_t) samples[i].left >> 16U;
                samples16[i].right = (uint32_t) samples[i].right >> 16U;
            }
            // write 16-bit data
            fwrite(&samples16, 1, sizeof(samples16), fd_out);
        } else {
            // write 32-bit data
            fwrite(&samples, 1, sizeof(samples), fd_out);
        }
    }
}

int main(int argc, char ** argv)
{
    FILE *          fd_out;
    uint32_t        sample_rate;
    uint32_t        i, bits;
    double          frequency;

    if (argc != 5) {
        fprintf(stderr, "Usage: siggen <sample rate> <bits> <frequency> <output.wav>\n"
                        "<sample rate> may be");
        for (i = 0; allowed_sample_rate[i] != 0; i++) {
            fprintf(stderr, " %u", (unsigned) allowed_sample_rate[i]);
        }
        fprintf(stderr, "\n<bits> may be 16 or 24.\n");
        return 1;
    }

    sample_rate = (uint32_t) atoi(argv[1]);
    i = 0;
    while (allowed_sample_rate[i] != sample_rate) {
        if (allowed_sample_rate[i] == 0) {
            fprintf(stderr, "that sample rate is not allowed\n");
            return 1;
        }
        i++;
    }

    bits = (uint32_t) atoi(argv[2]);
    if ((bits != 16) && (bits != 24)) {
        fprintf(stderr, "that number of bits is not allowed\n");
        return 1;
    }
    frequency = strtod(argv[3], NULL);
    if ((frequency <= 0.0) || (frequency >= ((double) sample_rate / 2.0)) || isnan(frequency))
    {
        fprintf(stderr, "that frequency is not allowed\n");
        return 1;
    }

    fd_out = fopen(argv[4], "wb");
    if (!fd_out) {
        perror("open (write)");
        return 1;
    }
    generate(sample_rate, bits, frequency, fd_out);
    fclose(fd_out);
    return 0;
}

