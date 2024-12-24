
#include "packetgen.h"
#ifndef DATA_BITS
#include "settings.h"
#endif

#include <stdlib.h>
#include <math.h>
#include <limits.h>


static const uint32_t crc_bits = 16;
static const uint32_t data_bits = DATA_BITS;

uint64_t packetgen_build_bits(uint64_t data)
{
    // get data bits
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

bool packetgen_build_samples(const uint32_t num_packets, const uint64_t* packet_data,
                             const uint32_t sample_rate, const uint32_t num_channels,
                             int16_t** sample_data, uint32_t* sample_count)
{
    const uint32_t  bits_per_packet = data_bits + crc_bits + 2; // 2 = stop and start bits
    const uint32_t  num_bits = num_packets * bits_per_packet;
    const uint32_t  samples_per_bit = sample_rate / BAUD_RATE;
    const uint32_t  leadin_samples = sample_rate / 10;
    const uint32_t  leadout_samples = sample_rate / 10;
    const uint32_t  packet_samples = num_bits * samples_per_bit;
    const uint32_t  num_samples = leadin_samples + leadout_samples + packet_samples;

    // allocate space for samples
    int16_t* output = (int16_t*) calloc(sizeof(int16_t) * num_channels, num_samples);
    if (!output) {
        // allocation failed
        return false;
    }

    // output sample iteration
    int16_t*        output_iter = output;

    // Oscillator settings
    // Note that 48kHz is always used as the sample rate here, regardless of the mixer sample rate,
    // because the same assumption is made at the decoder.
    const float     pi = (float) M_PI;
    const float     upper_delta = ((pi * 2.0F) / (float) SAMPLE_RATE) * UPPER_FREQUENCY;
    const float     lower_delta = ((pi * 2.0F) / (float) SAMPLE_RATE) * LOWER_FREQUENCY;
    float           angle = 0.0F;

    // Iteration through the packets
    uint32_t        packet_index = 0;
    bool            reached_leadout = false;

    // Initial setup time - no data - hold at 1
    uint32_t        packet_lifetime = 0;
    uint64_t        packet = 1;
    uint32_t        bit_lifetime = leadin_samples;

    for (uint32_t i = 0; i < num_samples; i++) {
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
                    packet = packetgen_build_bits(packet_data[packet_index]);
                    packet_index++;
                }
            } else {
                packet = packet >> (uint64_t) 1;
            }
            packet_lifetime--;
        }
        bit_lifetime--;
        if (packet == 0) {
            // Internal error: packet data was 0 (packet incorrectly generated)
            free(output);
            return false;
        }
        angle += (packet & 1) ? upper_delta : lower_delta;
        if (angle > (pi * 2.0)) {
            angle -= pi * 2.0;
        }
        // generate oscillator output
        const int16_t value = (int16_t) floorf((sinf(angle) * (float) (INT16_MAX - 1)) + 0.5);
        // copy to all channels
        for (uint32_t j = 0; j < num_channels; j++) {
            *output_iter = value;
            output_iter++;
        }
    }

    if (!reached_leadout) {
        // Internal error: should have generated all packets (computed sizes are wrong)
        free(output);
        return false;
    }

    // valid output
    *sample_count = (uint32_t) num_samples;
    *sample_data = output;
    return true;
}
