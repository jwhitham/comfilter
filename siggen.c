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

#define BLOCK_SIZE (1 << 8)

static void generate(const uint32_t sample_rate, uint32_t bits,
            double upper_frequency, double lower_frequency,
            uint32_t baud_rate, FILE* fd_in, uint32_t num_bytes, FILE* fd_out, FILE* fd_debug)
{
    t_header        header;
    const uint32_t  bits_per_byte = 8;
    const uint32_t  num_bits = num_bytes * (bits_per_byte + 2);
    const uint32_t  num_repeats = 3;
    const double    silent_time = 0.01;
    const double    active_time = ((double) (num_bits * num_repeats) / baud_rate);
    const uint32_t  bytes_per_sample = (bits == 16) ? 2 : 4;
    const uint32_t  num_active_blocks = (uint32_t) ceil((sample_rate * active_time) / BLOCK_SIZE);
    const uint32_t  num_silent_blocks = (uint32_t) ceil((sample_rate * silent_time) / BLOCK_SIZE);
    const uint32_t  num_samples = (num_active_blocks + (num_silent_blocks * 2)) * BLOCK_SIZE;
    uint32_t        i = 0;
    uint32_t        j = 0;
    double          angle = 0.0;
    double          upper_delta = ((M_PI * 2.0) / (double) sample_rate) * upper_frequency;
    double          lower_delta = ((M_PI * 2.0) / (double) sample_rate) * lower_frequency;
    const uint32_t  samples_per_bit = sample_rate / baud_rate;
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

    // Generate silent blocks
    t_stereo16      samples16[BLOCK_SIZE];
    t_stereo32      samples[BLOCK_SIZE];
    memset(&samples16, 0, sizeof(samples16));
    memset(&samples, 0, sizeof(samples));
    uint64_t sample_count = 0;

    for (j = 0; j < num_silent_blocks; j++) {
        if (bits == 16) {
            fwrite(&samples16, 1, sizeof(samples16), fd_out);
        } else {
            fwrite(&samples, 1, sizeof(samples), fd_out);
        }
        for (i = 0; i < BLOCK_SIZE; i++) {
            fprintf(fd_debug, "%7.5f ", (double) sample_count / (double) header.sample_rate); // time
            fprintf(fd_debug, "- 0 - ");
            fprintf(fd_debug, "\n");
            sample_count++;
        }
    }

    // Generate active blocks
    for (j = 0; j < num_active_blocks; j++) {
        for (i = 0; i < BLOCK_SIZE; i++) {
            if (bit_lifetime == 0) {
                bit_lifetime = samples_per_bit;
                if (byte_lifetime == 0) {
                    byte_lifetime = bits_per_byte + 1;
                    byte = fgetc(fd_in);
                    if (byte == EOF) {
                        rewind(fd_in);
                        byte = 0x0;       // break (silence)
                        //byte = 0x3ff;       // no data
                    } else {
                        byte ^= 0x1ff;      // RS232 - active low, LSB first, stop bit is high
                        byte = byte << 1;   // add low start bit
                    }
                } else {
                    byte = byte >> 1;
                    byte_lifetime--;
                }
            }
            bit_lifetime--;
            if (byte > 0) {
                angle += (byte & 1) ? upper_delta : lower_delta;
                if (angle > (M_PI * 2.0)) {
                    angle -= M_PI * 2.0;
                }
                samples[i].left = samples[i].right = floor((sin(angle) * (double) (INT_MAX - 1)) + 0.5);
            } else {
                angle = 0.0;
                samples[i].left = samples[i].right = 0;
            }
            fprintf(fd_debug, "%7.5f ", (double) sample_count / (double) header.sample_rate); // time
            if (byte > 0) {
                if (byte & 1) {
                    fprintf(fd_debug, "%7.4f - 1 ", (double) samples[i].left / (double) INT_MAX); // encoded signal
                } else {
                    fprintf(fd_debug, "- %7.4f 0 ", (double) samples[i].left / (double) INT_MAX); // encoded signal
                }
            } else {
                fprintf(fd_debug, "- 0 - ");
            }
            fprintf(fd_debug, "\n");
            sample_count++;
        }

        if (bits == 16) {
            // Convert 32-bit to 16-bit
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

    // Further silence at the end
    memset(&samples16, 0, sizeof(samples16));
    memset(&samples, 0, sizeof(samples));

    for (j = 0; j < num_silent_blocks; j++) {
        if (bits == 16) {
            fwrite(&samples16, 1, sizeof(samples16), fd_out);
        } else {
            fwrite(&samples, 1, sizeof(samples), fd_out);
        }
    }

}

int main(int argc, char ** argv)
{
    FILE *          fd_in;
    FILE *          fd_out;
    FILE *          fd_debug;

    if (argc != 4) {
        fprintf(stderr, "Usage: siggen <data input> <output.wav> <debug output>\n");
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
    fseek(fd_in, 0, SEEK_END);
    off_t size = ftell(fd_in);
    fseek(fd_in, 0, SEEK_SET);
    generate(48000, 16, UPPER_FREQUENCY, LOWER_FREQUENCY, BAUD_RATE, fd_in, (uint32_t) size, fd_out, fd_debug);
    fclose(fd_debug);
    fclose(fd_out);
    fclose(fd_in);
    return 0;
}

