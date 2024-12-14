#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#include <limits.h>

#include "wave.h"
#include "settings.h"

#define BLOCK_SIZE (1 << 8)

static const uint32_t bits_per_packet = 8;
static int64_t build_packet(const char* packet)
{
    return 1;
}

static void generate(FILE* fd_out, uint32_t num_packets, char* const* packets)
{
    t_header        header;
    const uint32_t  sample_rate = SAMPLE_RATE;
    const uint32_t  num_bits = (num_packets + 1) * (bits_per_packet + 2);
    const uint32_t  samples_per_bit = sample_rate / BAUD_RATE;
    const uint32_t  leadin_samples = samples_per_bit * (bits_per_packet * 2);
    const double    silent_time = 0.01;
    const double    active_time =
        (leadin_samples + (samples_per_bit * num_bits)) / (double) sample_rate;
    const uint32_t  bytes_per_sample = 2;
    const uint32_t  num_active_blocks = (uint32_t) ceil((sample_rate * active_time) / BLOCK_SIZE);
    const uint32_t  num_silent_blocks = (uint32_t) ceil((sample_rate * silent_time) / BLOCK_SIZE);
    const uint32_t  num_samples = (num_active_blocks + num_silent_blocks) * BLOCK_SIZE;
    uint32_t        i = 0;
    uint32_t        j = 0;
    double          angle = 0.0;
    const double    upper_delta = ((M_PI * 2.0) / (double) sample_rate) * UPPER_FREQUENCY;
    const double    lower_delta = ((M_PI * 2.0) / (double) sample_rate) * LOWER_FREQUENCY;
    uint32_t        bit_lifetime = 0;
    uint32_t        packet_lifetime = 0;
    uint32_t        packet_index = 0;
    int64_t         packet = -1;

    // Write wav header
    memset(&header, 0, sizeof(header));
    memcpy(header.fixed_riff, "RIFF", 4);
    memcpy(header.fixed_wave, "WAVE", 4);
    memcpy(header.fixed_fmt, "fmt ", 4);
    header.length_of_format_data = 16;
    header.type_of_format = 1; // WAVE_FORMAT_PCM
    header.number_of_channels = 1;
    header.sample_rate = sample_rate;
    header.bytes_per_second = header.sample_rate * bytes_per_sample * header.number_of_channels;
    header.bytes_per_period = bytes_per_sample * header.number_of_channels; // applies to all channels
    header.bits_per_sample = bytes_per_sample * 8; // applies to 1 channel
    memcpy(header.fixed_data, "data", 4);
    header.data_size = num_samples * bytes_per_sample * header.number_of_channels;
    header.file_size = header.data_size + sizeof(t_header);
    fwrite(&header, 1, sizeof(header), fd_out);

    // Check endianness
    if (((uint32_t *) &header.fixed_riff)[0] != 0x46464952) {
        fprintf(stderr, "endianness error (little endian assumed, sorry)\n");
        exit(1);
    }

    // Samples
    int16_t samples[BLOCK_SIZE];
    memset(&samples, 0, sizeof(samples));
    uint64_t sample_count = 0;

    // Initial setup time - no data - hold at 1
    packet = 1;
    bit_lifetime = leadin_samples;

    // Generate active blocks
    for (j = 0; j < num_active_blocks; j++) {
        for (i = 0; i < BLOCK_SIZE; i++) {
            if (bit_lifetime == 0) {
                bit_lifetime = samples_per_bit;
                if (packet_lifetime == 0) {
                    if (packet_index >= num_packets) {
                        // hold at 1
                        packet_lifetime = 0;
                        packet = 1;
                    } else {
                        // get packet data
                        packet_lifetime = bits_per_packet + 1;
                        packet = build_packet(packets[packet_index]);
                        packet_index++;
                    }
                } else {
                    packet = packet >> 1;
                    packet_lifetime--;
                }
            }
            bit_lifetime--;
            if (packet > 0) {
                angle += (packet & 1) ? upper_delta : lower_delta;
                if (angle > (M_PI * 2.0)) {
                    angle -= M_PI * 2.0;
                }
                samples[i] = floor((sin(angle) * (double) (INT16_MAX - 1)) + 0.5);
            } else {
                angle = 0.0;
                samples[i] = 0;
            }
        }

        fwrite(&samples, 1, sizeof(samples), fd_out);
        sample_count += BLOCK_SIZE;
    }

    // Silence at the end
    memset(&samples, 0, sizeof(samples));

    for (j = 0; j < num_silent_blocks; j++) {
        fwrite(&samples, 1, sizeof(samples), fd_out);
        sample_count += BLOCK_SIZE;
    }

    if (num_samples != sample_count) {
        fprintf(stderr, "Error: should have generated %u samples, actually %u\n",
            (unsigned) num_samples, (unsigned) sample_count);
        exit(1);
    }
    if (ftell(fd_out) != header.file_size) {
        fprintf(stderr, "Error: file size should be %u, actually %u\n",
            (unsigned) header.file_size, (unsigned) ftell(fd_out));
        exit(1);
    }
}

int main(int argc, char ** argv)
{
    FILE *          fd_out = NULL;

    if (argc < 3) {
        fprintf(stderr, "Usage: packetgen <output.wav> <packets ...>\n");
        return 1;
    }

    fd_out = fopen(argv[1], "wb");
    if (!fd_out) {
        perror("open (write)");
        return 1;
    }
    generate(fd_out, argc - 2, &argv[2]);
    fclose(fd_out);
    return 0;
}

