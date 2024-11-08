// Suggested compile command: g++ -o sigdec.exe sigdec.cpp -Wall -Werror -g  -O -lm -std=c++17
//
#include <stdio.h>
#include <string.h>
#include <cstdint>
#include <stdlib.h>
#include <math.h>
#include <limits.h>
#include <stdbool.h>

#include "wave.h"
#include "settings.h"

static constexpr size_t BLOCK_SIZE = 1 << 14;
static constexpr double FILTER_WIDTH = 100;
static constexpr double RC_DECAY_PER_BIT = 0.1;

namespace {

static constexpr std::uint64_t FIXED_BITS = 9;

struct fixed_t {
public:
    fixed_t() {}
    fixed_t(double value) {
        if (value < 0.0) {
            m_negative = true;
            value = -value;
        }
        if (value >= 2.0) {
            fprintf(stderr, "Fixed point value out of range on construction: %1.3f\n", value);
            exit(1);
        }
        value *= (double) one;
        m_bits = static_cast<std::uint64_t>(floor(value + 0.5));
    }

    fixed_t(const fixed_t&) = default;
    fixed_t& operator=(const fixed_t&) = default;

    fixed_t(std::int16_t value) {
        if (value < 0) {
            m_negative = true;
            value = -value;
        }
        const std::uint64_t value_bits = 15; // 16 bit -> 15 magnitude, 1 sign
        if constexpr (FIXED_BITS >= value_bits) {
            m_bits = static_cast<std::uint64_t>(value) << (FIXED_BITS - value_bits);
        } else {
            m_bits = static_cast<std::uint64_t>(value) >> (value_bits - FIXED_BITS);
        }
    }

    fixed_t operator*(const fixed_t& other) {
        fixed_t out;
        out.m_bits = (m_bits * other.m_bits) >> FIXED_BITS;
        out.m_negative = (m_negative != other.m_negative);
        out.range_check();
        return out;
    }

    fixed_t operator/(const fixed_t& other) {
        fixed_t out;
        out.m_bits = (m_bits << FIXED_BITS) / other.m_bits;
        out.m_negative = (m_negative != other.m_negative);
        out.range_check();
        return out;
    }

    fixed_t operator+(const fixed_t& other) {
        fixed_t out;
        if (m_negative == other.m_negative) {
            out.m_bits = m_bits + other.m_bits;
            out.m_negative = m_negative;
        } else if (other.m_bits <= m_bits) {
            out.m_bits = m_bits - other.m_bits;
            out.m_negative = m_negative;
        } else {
            out.m_bits = other.m_bits - m_bits;
            out.m_negative = other.m_negative;
        }
        out.range_check();
        return out;
    }

    fixed_t operator-(const fixed_t& other) {
        fixed_t negated;
        negated.m_bits = other.m_bits;
        negated.m_negative = !other.m_negative;
        return *this + negated;
    }

    bool operator>(const fixed_t& other) {
        fixed_t temp = *this - other;
        temp.range_check();
        return (!temp.m_negative) && (temp.m_bits > 0);
    }

    fixed_t abs() {
        fixed_t temp = *this;
        temp.m_negative = false;
        return temp;
    }

    double to_double() {
        double value = (double) m_bits / (double) one;
        if (m_negative) {
            value = -value;
        }
        return value;
    }

    void range_check() {
        if (m_bits >= (one * 2)) {
            fprintf(stderr, "Fixed point value out of range after operation: %1.3f\n", 
                to_double());
            exit(1);
        }
    }
private:
    std::uint64_t m_bits{0};
    bool m_negative{false};
    static constexpr std::uint64_t one{static_cast<std::uint64_t>(1) << FIXED_BITS};
};

struct my_filter_state_t {
    my_filter_state_t() {};
    fixed_t a0, a1, a2;
    fixed_t b0, b1, b2;
    fixed_t i1, i2;
    fixed_t o1, o2;
};

static void my_filter_setup(
                my_filter_state_t* mf,
                t_header* header,
                double frequency,
                double width) {
    const double w0 = 2 * M_PI * frequency / (double) header->sample_rate;
    const double alpha = sin(w0)/(2*frequency/width);
    double b0 =   alpha;
    double b1 =   0;
    double b2 =  -alpha;
    double a0 =   1 + alpha;
    double a1 =  -2*cos(w0);
    double a2 =   1 - alpha;
    b2 /= a0;
    b1 /= a0;
    b0 /= a0;
    a2 /= a0;
    a1 /= a0;
    printf("Matrix for frequency %1.0f Hz width %1.0f Hz\n", frequency, width);
    printf("   w0 = %14.6e a  = %14.6e\n", w0, alpha);
    printf("   a0 = %14.6e a1 = %14.6e a2 = %14.6e (double)\n", a0, a1, a2);
    printf("   b0 = %14.6e b1 = %14.6e b2 = %14.6e (double)\n", b0, b1, b2);
    mf->b0 = fixed_t(b0);
    mf->b1 = fixed_t(b1);
    mf->b2 = fixed_t(b2);
    mf->a0 = fixed_t(a0);
    mf->a1 = fixed_t(a1);
    mf->a2 = fixed_t(a2);
    printf("   a0 = %14.6e a1 = %14.6e a2 = %14.6e (fixed_t %u)\n",
            mf->a0.to_double(), mf->a1.to_double(), mf->a2.to_double(),
            static_cast<unsigned>(FIXED_BITS));
    printf("   b0 = %14.6e b1 = %14.6e b2 = %14.6e (fixed_t %u)\n",
            mf->b0.to_double(), mf->b1.to_double(), mf->b2.to_double(),
            static_cast<unsigned>(FIXED_BITS));
}

static void my_filter(
                my_filter_state_t* mf,
                fixed_t* input,
                fixed_t* output,
                size_t num_samples) {

    for (size_t i = 0; i < num_samples; i++) {
        fixed_t i0 = input[i];
        fixed_t o0 = i0*mf->b0 + mf->i1*mf->b1 + mf->i2*mf->b2 - mf->o1*mf->a1 - mf->o2*mf->a2;
        mf->i2 = mf->i1;
        mf->i1 = i0;
        mf->o2 = mf->o1;
        mf->o1 = o0;
        output[i] = o0;
    }
}

struct rc_filter_state_t {
    rc_filter_state_t() {};
    fixed_t      level;
    fixed_t      decay;
};

static void rc_filter_setup(
                    rc_filter_state_t* ds,
                    t_header* header,
                    std::uint32_t frequency)
{
    // Number of samples per bit
    const double bit_samples = ((double) header->sample_rate / (double) BAUD_RATE);
    // This is the time constant, like k = 1 / RC for a capacitor discharging
    // Note: Level is y = exp(-kt) at time t, assuming level was 1.0 at time 0
    // The level should be reduced from 1.0 to RC_DECAY_PER_BIT during each bit
    const double time_constant = log(RC_DECAY_PER_BIT) / -bit_samples;
    // Each transition from t to t+1 is a multiplication by exp(-k)
    const double decay = exp(-time_constant);
    ds->decay = fixed_t(decay);
    printf("Decay %10.6f (double) %10.6f (fixed_t)\n", decay, ds->decay.to_double());
}

static void rc_filter(
                    rc_filter_state_t* ds,
                    fixed_t* samples,
                    size_t num_samples,
                    fixed_t* levels)
{
    for (size_t i = 0; i < num_samples; i++) {
        fixed_t sample = samples[i].abs();
        ds->level = ds->level * ds->decay;
        if (sample > ds->level) {
            ds->level = sample;
        }
        levels[i] = ds->level;
    }
}

typedef enum { WAIT_START = 0, WAIT_NEXT, CHECK_START,
               STOP, STOP_ERROR, START, START_ERROR,
               DATA_0, DATA_1 } identified_t;


typedef struct serial_decode_state_t {
    std::uint32_t   sample_countdown, half_bit;
    std::uint32_t   byte_countdown;
    std::uint8_t    byte;
    bool            previous_bit;
    identified_t    state;
} serial_decode_state_t;

static void serial_decode(
                    serial_decode_state_t* ds,
                    fixed_t* upper_levels,
                    fixed_t* lower_levels,
                    identified_t* identified,
                    bool* received_bit,
                    size_t num_samples,
                    FILE* out)
{
    for (size_t i = 0; i < num_samples; i++) {
        const bool bit = (upper_levels[i] > lower_levels[i]);
        received_bit[i] = bit;

        switch (ds->state) {
            case WAIT_START:
                if (ds->previous_bit && !bit) {
                    ds->sample_countdown = ds->half_bit;
                    ds->state = START;
                }
                break;
            case START:
                ds->state = CHECK_START;
                break;
            case CHECK_START:
                if (bit) {
                    ds->state = START_ERROR;
                } else {
                    ds->sample_countdown--;
                    if (ds->sample_countdown == 0) {
                        ds->sample_countdown = ds->half_bit * 2;
                        ds->state = WAIT_NEXT;
                        ds->byte_countdown = 9;
                        ds->byte = 0;
                    }
                }
                break;
            case WAIT_NEXT:
                ds->sample_countdown--;
                if (ds->sample_countdown == 0) {
                    ds->sample_countdown = ds->half_bit * 2;
                    ds->byte_countdown--;
                    if (ds->byte_countdown == 0) {
                        if (bit) {
                            fputc(ds->byte, out);
                            ds->state = STOP;
                        } else {
                            ds->state = STOP_ERROR;
                        }
                    } else {
                        ds->byte = ds->byte >> 1;
                        if (bit) {
                            ds->byte |= 0x80;
                            ds->state = DATA_1;
                        } else {
                            ds->state = DATA_0;
                        }
                    }
                }
                break;
            case DATA_1:
            case DATA_0:
                ds->sample_countdown--;
                ds->state = WAIT_NEXT;
                break;
            case START_ERROR:
            case STOP_ERROR:
            case STOP:
                ds->state = WAIT_START;
                break;
        }
        identified[i] = ds->state;
        ds->previous_bit = bit;
    }
}

static void generate(FILE* fd_in, FILE* fd_out, FILE* fd_debug)
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
    || (header.number_of_channels != 1)
    || (header.bytes_per_second != (header.sample_rate * header.bytes_per_period))
    || (header.bits_per_sample != ((header.bytes_per_period / header.number_of_channels) * 8))
    || (memcmp(header.fixed_data, "data", 4) != 0)
    || (header.bytes_per_period != sizeof(std::int16_t))
    || (header.bits_per_sample != 16)) {
        fprintf(stderr, "Format is incorrect - needs to be a simple mono PCM file, 16 bit\n");
        exit(1);
    }

    // Check endianness
    if (((std::uint32_t *) &header.fixed_riff)[0] != 0x46464952) {
        fprintf(stderr, "endianness error (little endian assumed, sorry)\n");
        exit(1);
    }

    my_filter_state_t upper_filter;
    my_filter_state_t lower_filter;
    my_filter_setup(&upper_filter, &header, UPPER_FREQUENCY, FILTER_WIDTH);
    my_filter_setup(&lower_filter, &header, LOWER_FREQUENCY, FILTER_WIDTH);

    rc_filter_state_t upper_decode_state;
    rc_filter_state_t lower_decode_state;
    rc_filter_setup(&upper_decode_state, &header, UPPER_FREQUENCY); 
    rc_filter_setup(&lower_decode_state, &header, LOWER_FREQUENCY); 

    serial_decode_state_t serial_decode_state;
    memset(&serial_decode_state, 0, sizeof(serial_decode_state_t));
    serial_decode_state.half_bit = (header.sample_rate / BAUD_RATE) / 2;

    uint64_t sample_count = 0;

    while (1) {
        std::int16_t samples[BLOCK_SIZE];
        fixed_t input[BLOCK_SIZE];
        fixed_t upper_output[BLOCK_SIZE];
        fixed_t lower_output[BLOCK_SIZE];
        size_t i;

        // Input from .wav file
        ssize_t num_samples = fread(samples, sizeof(std::int16_t), BLOCK_SIZE, fd_in);
        if (num_samples <= 0) {
            break;
        }

        for (i = 0; i < ((size_t) num_samples); i++) {
            input[i] = fixed_t(samples[i]);
        }
        // Bandpass filters
        my_filter(&upper_filter, input, upper_output, num_samples);
        my_filter(&lower_filter, input, lower_output, num_samples);

        // Level
        fixed_t upper_levels[BLOCK_SIZE];
        fixed_t lower_levels[BLOCK_SIZE];
        rc_filter(&upper_decode_state, upper_output, (size_t) num_samples, upper_levels);
        rc_filter(&lower_decode_state, lower_output, (size_t) num_samples, lower_levels);

        // Serial decoding
        identified_t identified[BLOCK_SIZE];
        bool received_bit[BLOCK_SIZE];
        serial_decode(&serial_decode_state,
                      upper_levels,
                      lower_levels,
                      identified,
                      received_bit,
                      (size_t) num_samples,
                      fd_out);

        // Debug output shows filtering and detection
        for (i = 0; i < ((size_t) num_samples); i++) {
            fprintf(fd_debug, "%7.5f ", (double) sample_count / (double) header.sample_rate); // time
            fprintf(fd_debug, "%7.4f ", input[i].to_double()); // encoded signal
            fprintf(fd_debug, "%7.4f ", upper_output[i].to_double()); // upper bandpass filter output
            fprintf(fd_debug, "%7.4f ", lower_output[i].to_double()); // lower bandpass filter output
            fprintf(fd_debug, "%7.4f ", upper_levels[i].to_double()); // upper, rectify and RC filter
            fprintf(fd_debug, "%7.4f ", lower_levels[i].to_double()); // lower, rectify and RC filter

            switch(received_bit[i]) {
                case false:         fprintf(fd_debug, "0 "); break;
                default:            fprintf(fd_debug, "1 "); break;
            }
            switch(identified[i]) {
                case DATA_0:        fprintf(fd_debug, "0 "); break;
                case DATA_1:        fprintf(fd_debug, "1 "); break;
                case START:         fprintf(fd_debug, "2 "); break;
                case STOP:          fprintf(fd_debug, "3 "); break;
                case START_ERROR:   fprintf(fd_debug, "4 "); break;
                case STOP_ERROR:    fprintf(fd_debug, "5 "); break;
                default:            fprintf(fd_debug, "- "); break;
            }
            fprintf(fd_debug, "\n");
            sample_count++;
        }
    }
}

} // namespace

int main(int argc, char ** argv)
{
    FILE *          fd_in;
    FILE *          fd_out;
    FILE *          fd_debug;

    if (argc != 4) {
        fprintf(stderr, "Usage: sigdec <signal.wav> <data output> <debug output>\n");
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
    generate(fd_in, fd_out, fd_debug);
    fclose(fd_debug);
    fclose(fd_out);
    fclose(fd_in);
    return 0;
}

