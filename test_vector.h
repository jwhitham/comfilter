#ifndef TEST_VECTOR_H
#define TEST_VECTOR_H

#include <stdint.h>

typedef struct test_vector_t {
    int32_t    input;
    int32_t    upper_bandpass, lower_bandpass;
    int32_t    upper_rc, lower_rc;
    int32_t    out_bit;
} test_vector_t;

#endif
