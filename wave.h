#ifndef WAVE_H
#define WAVE_H

#include <stdint.h>

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

#endif
