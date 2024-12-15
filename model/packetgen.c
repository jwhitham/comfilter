#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#include <limits.h>
#include <stdbool.h>

#include "wave.h"
#include "settings.h"

#define BLOCK_SIZE (1 << 8)

static const uint32_t crc_bits = 16;
static const uint32_t data_bits = DATA_BITS;

static uint64_t build_packet(const char* packet)
{
    // get data bits
    uint64_t data = (uint64_t) strtoll(packet, NULL, 0);
    data &= ((uint64_t) 1 << (uint64_t) data_bits) - 1;

    // compute the CRC
    const uint16_t polynomial = 0x8005;
    uint16_t crc_value = 0;
    for (uint16_t i = 0; i < data_bits; i++) {
        uint16_t bit_flag = (uint16_t) (data >> (uint64_t) i) ^ (crc_value >> (uint64_t) (crc_bits - 1));
        crc_value = crc_value << 1;
        if (bit_flag & 1) {
            crc_value ^= polynomial;
        }
    }
    // bit reverse CRC and append
    for (uint16_t i = 0; i < crc_bits; i++) {
        data |= (uint64_t) ((crc_value >> i) & 1) << (uint64_t) (data_bits + crc_bits - 1 - i);
    }
    // append stop bit (1)
    data |= (uint64_t) 1 << (uint64_t) (data_bits + crc_bits);
    // insert start bit (0)
    data = data << (uint64_t) 1;
    return data;
}

static void generate_vhdl(FILE* fd_out, uint32_t num_packets, char* const* packets)
{
    // Write VHDL test bench
    fprintf(fd_out,
        "library ieee;\n"
        "use ieee.std_logic_1164.all;\n"
        "entity test_packet_signal is port (\n"
        "start_in : in std_logic;\n"
        "data_out : out std_logic;\n"
        "done_out : out std_logic);\n"
        "end test_packet_signal;\n"
        "architecture test_bench of test_packet_signal is\n"
        "constant baud_rate : Real := %1.2f;\n"
        "constant one_bit_time : Time := 1e9 ns / baud_rate;\n"
        "begin\n"
        "process is begin\n"
        "done_out <= '0';\n"
        "data_out <= '0';\n"
        "wait for one_bit_time;\n"
        "wait until start_in = '1';\n"
        "data_out <= '1';\n"
        "wait for one_bit_time * 100;\n", (double) BAUD_RATE);

    const uint32_t bits_per_packet = data_bits + crc_bits + 2; // 2 = stop and start bits
    for (uint32_t i = 0; i < num_packets; i++) {

        uint64_t packet = build_packet(packets[i]);
        uint64_t copy_packet = packet;
        fprintf(fd_out, "-- packet: ");
        for (uint32_t j = 0; j < 16; j++) {
            fprintf(fd_out, "%x", (unsigned) (packet >> (uint64_t) 60));
            packet = packet << 4;
        }
        fprintf(fd_out, "\n");

        packet = copy_packet;
        for (uint32_t j = 0; j < bits_per_packet; j++) {
            fprintf(fd_out, "data_out <= '%d'; wait for one_bit_time;\n", (int) (packet & 1));
            packet = packet >> (uint64_t) 1;
        }
    }
    fprintf(fd_out,
        "-- end\n"
        "wait for one_bit_time * 100;\n"
        "done_out <= '1';\n"
        "wait;\n"
        "end process;\n"
        "end architecture test_bench;\n");
}

static void generate_wav(FILE* fd_out, uint32_t num_packets, char* const* packets)
{
    t_header        header;
    const uint32_t  bits_per_packet = data_bits + crc_bits + 2; // 2 = stop and start bits
    const uint32_t  num_bits = num_packets * bits_per_packet;
    const uint32_t  sample_rate = SAMPLE_RATE;
    const uint32_t  samples_per_bit = sample_rate / BAUD_RATE;
    const uint32_t  leadin_samples = sample_rate / 10;
    const uint32_t  leadout_samples = sample_rate / 10;
    const uint32_t  packet_samples = num_bits * samples_per_bit;
    const double    active_time =
        (leadin_samples + leadout_samples + packet_samples) / (double) sample_rate;
    const uint32_t  bytes_per_sample = 2;
    const uint32_t  num_active_blocks = (uint32_t) ceil((sample_rate * active_time) / BLOCK_SIZE);
    const uint32_t  num_samples = num_active_blocks * BLOCK_SIZE;
    const double    upper_delta = ((M_PI * 2.0) / (double) sample_rate) * UPPER_FREQUENCY;
    const double    lower_delta = ((M_PI * 2.0) / (double) sample_rate) * LOWER_FREQUENCY;

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

    uint64_t        sample_count = 0;
    bool            reached_leadout = false;
    uint32_t        bit_lifetime = leadin_samples;
    uint32_t        packet_index = 0;
    double          angle = 0.0;

    // Initial setup time - no data - hold at 1
    uint32_t        packet_lifetime = 0;
    uint64_t        packet = 1;

    // Generate active blocks
    for (uint32_t j = 0; j < num_active_blocks; j++) {
        for (uint32_t i = 0; i < BLOCK_SIZE; i++) {
            if (bit_lifetime == 0) {
                bit_lifetime = samples_per_bit;
                if (packet_lifetime == 0) {
                    if (packet_index >= num_packets) {
                        // leadout - hold at 1
                        packet_lifetime = 1;
                        bit_lifetime = leadout_samples;
                        packet = 1;
                        reached_leadout = true;
                    } else {
                        // get packet data
                        packet_lifetime = bits_per_packet;
                        packet = build_packet(packets[packet_index]);
                        packet_index++;
                    }
                } else {
                    packet = packet >> (uint64_t) 1;
                }
                packet_lifetime--;
            }
            bit_lifetime--;
            if (packet == 0) {
                fprintf(stderr, "Error: packet data was 0 (packet incorrectly generated)\n");
                exit(1);
            }
            angle += (packet & 1) ? upper_delta : lower_delta;
            if (angle > (M_PI * 2.0)) {
                angle -= M_PI * 2.0;
            }
            samples[i] = floor((sin(angle) * (double) (INT16_MAX - 1)) + 0.5);
        }

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
    if (!reached_leadout) {
        fprintf(stderr, "Error: should have generated all packets (computed sizes are wrong)\n");
        exit(1);
    }
}

int main(int argc, char ** argv)
{
    FILE *          fd_out = NULL;
    const char*     arg_wav = "wav";
    const char*     arg_vhdl = "vhdl";

    if ((argc < 4)
    || ((strcmp(argv[1], arg_vhdl) != 0) && (strcmp(argv[1], arg_wav) != 0))) {
        fprintf(stderr, "Usage: packetgen wav <output.wav> <packets ...>\n"
                        "   or: packetgen vhdl <test.vhdl> <packets ...>\n");
        return 1;
    }

    bool wav_out = strcmp(argv[1], arg_wav) == 0;
    if (wav_out) {
        fd_out = fopen(argv[2], "wb");
    } else {
        fd_out = fopen(argv[2], "wt");
    }
    if (!fd_out) {
        perror("open (write)");
        return 1;
    }
    if (wav_out) {
        generate_wav(fd_out, argc - 3, &argv[3]);
    } else {
        generate_vhdl(fd_out, argc - 3, &argv[3]);
    }
    fclose(fd_out);
    return 0;
}

