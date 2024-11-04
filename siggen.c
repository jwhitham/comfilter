// Suggested compile command: gcc -o siggen.exe siggen.c -Wall -Werror -g  -O -lm
//
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#include <limits.h>

#include "wave.h"
#include "settings.h"

#define BLOCK_SIZE (1 << 14)

static void generate(const uint32_t sample_rate, uint32_t bits,
            double upper_frequency, double lower_frequency,
            uint32_t baud_rate, FILE* fd_in, uint32_t num_bytes, FILE* fd_out)
{
    t_header        header;
    const uint32_t  num_bits = num_bytes * 10;
    const uint32_t  num_repeats = 3;
    const uint32_t  wav_length = (num_bits * num_repeats) / baud_rate;
    const uint32_t  bytes_per_sample = (bits == 16) ? 2 : 4;
    t_stereo32      samples[BLOCK_SIZE];
    const uint32_t  num_blocks = (sample_rate * wav_length) / BLOCK_SIZE;
    const uint32_t  num_samples = num_blocks * BLOCK_SIZE;
    uint32_t        i = 0;
    uint32_t        j = 0;
    double          angle = 0.0;
    double          upper_delta = ((M_PI * 2.0) / (double) sample_rate) * upper_frequency;
    double          lower_delta = ((M_PI * 2.0) / (double) sample_rate) * lower_frequency;
    uint32_t        samples_per_bit = sample_rate / baud_rate;
    uint32_t        bit_lifetime = 0;
    uint32_t        byte_lifetime = 0;
    int32_t         byte = -1;

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
    header.bytes_per_period = bytes_per_sample * 2; // applies to 2 channels
    header.bits_per_sample = bytes_per_sample * 8; // applies to 1 channel
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
        for (i = 0; i < BLOCK_SIZE; i++) {
            if (bit_lifetime == 0) {
                bit_lifetime = samples_per_bit;
                if (byte_lifetime == 0) {
                    byte_lifetime = 10;
                    byte = fgetc(fd_in);
                    if (byte == EOF) {
                        rewind(fd_in);
                        byte = -1;
                    }
                    byte |= 0x100;
                } else {
                    byte = byte << 1;
                }
                byte_lifetime--;
            }
            bit_lifetime--;
            if (byte >= 0) {
                angle += (byte & 0x100) ? upper_delta : lower_delta;
                if (angle > (M_PI * 2.0)) {
                    angle -= M_PI * 2.0;
                }
                samples[i].left = floor((sin(angle) * (double) (INT_MAX - 1)) + 0.5);
                samples[i].right = (byte & 0x100) ? (INT_MAX / 2) : 0;
            } else {
                angle = 0.0;
                samples[i].left = samples[i].right = 0;
            }
        }

        if (bits == 16) {
            // Convert 32-bit to 16-bit
            t_stereo16      samples16[BLOCK_SIZE];

            for (i = 0; i < BLOCK_SIZE; i++) {
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
    FILE *          fd_in;
    FILE *          fd_out;

    if (argc != 3) {
        fprintf(stderr, "Usage: siggen <modulation.bin> <output.wav>\n");
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
    fseek(fd_in, 0, SEEK_END);
    off_t size = ftell(fd_in);
    fseek(fd_in, 0, SEEK_SET);
    generate(48000, 16, UPPER_FREQUENCY, LOWER_FREQUENCY, BAUD_RATE, fd_in, (uint32_t) size, fd_out);
    fclose(fd_out);
    fclose(fd_in);
    return 0;
}

