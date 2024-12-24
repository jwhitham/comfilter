#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#include <limits.h>
#include <stdbool.h>

#include "wave.h"
#include "settings.h"
#include "packetgen.h"

static const uint32_t crc_bits = 16;
static const uint32_t data_bits = DATA_BITS;


static void generate_vhdl(FILE* fd_out, const size_t num_packets, char* const* packets)
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
    for (size_t i = 0; i < num_packets; i++) {

        uint64_t data = (uint64_t) strtoll(packets[i], NULL, 0);
        uint64_t packet = packetgen_build_bits(data);
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

static void generate_wav(FILE* fd_out, const size_t num_packets, char* const* packets)
{
    // convert packet parameters to numbers
    uint64_t* packet_data = calloc(sizeof(uint64_t), num_packets);
    if (!packet_data) {
        fprintf(stderr, "Error: allocate failed\n");
        exit(1);
    }
    for (uint32_t i = 0; i < num_packets; i++) {
        packet_data[i] = (uint64_t) strtoll(packets[i], NULL, 0);
        
    }

    // convert packets to samples
    size_t sample_count = 0;
    int16_t* sample_data = NULL;

    if (!packetgen_build_samples(num_packets, packet_data, SAMPLE_RATE,
                             &sample_data, &sample_count)) {
        fprintf(stderr, "Error: build_samples failed\n");
        exit(1);
    }
    free(packet_data);

    // Write wav header
    t_header header;
    const uint32_t bytes_per_sample = sizeof(int16_t);
    memset(&header, 0, sizeof(header));
    memcpy(header.fixed_riff, "RIFF", 4);
    memcpy(header.fixed_wave, "WAVE", 4);
    memcpy(header.fixed_fmt, "fmt ", 4);
    header.length_of_format_data = 16;
    header.type_of_format = 1; // WAVE_FORMAT_PCM
    header.number_of_channels = 1;
    header.sample_rate = SAMPLE_RATE;
    header.bytes_per_second = header.sample_rate * bytes_per_sample * header.number_of_channels;
    header.bytes_per_period = bytes_per_sample * header.number_of_channels; // applies to all channels
    header.bits_per_sample = bytes_per_sample * 8; // applies to 1 channel
    memcpy(header.fixed_data, "data", 4);
    header.data_size = sample_count * bytes_per_sample * header.number_of_channels;
    header.file_size = header.data_size + sizeof(t_header);

    // Check endianness
    if (((uint32_t *) &header.fixed_riff)[0] != 0x46464952) {
        fprintf(stderr, "Error: endianness (little endian assumed, sorry)\n");
        exit(1);
    }

    // Write header and samples
    if ((fwrite(&header, sizeof(header), 1, fd_out) != 1)
    || (fwrite(sample_data, sizeof(int16_t), sample_count, fd_out) != sample_count)) {
        fprintf(stderr, "Error: unable to write to file\n");
        exit(1);
    }
    free(sample_data);

    if (ftell(fd_out) != header.file_size) {
        fprintf(stderr, "Error: file size should be %u, actually %u\n",
            (unsigned) header.file_size, (unsigned) ftell(fd_out));
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

