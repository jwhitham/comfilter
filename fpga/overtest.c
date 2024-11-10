
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>

void overflow_test(int8_t a, int8_t b, int8_t* r, bool* overflow);

bool helper(int8_t a, int8_t b) {
    int8_t r = 0;
    bool overflow = false;
    overflow_test(a, b, &r, &overflow);
    printf("%d - %d = %d ", a, b, r);
    if (overflow) {
        printf("yes\n");
        return true;
    } else {
        printf("no\n");
        return false;
    }
}

int main(void)
{
    const int min_value = -128;
    const int max_value = 127;
    const int wrap_value = 256;
    int i, j;
    for (i = min_value; i <= max_value; i += 10) {
        for (j = min_value; j <= max_value; j += 10) {
            bool overflow = helper(i, j);
            int expect = i - j;
            bool expect_overflow = false;
            if (expect > max_value) {
                expect = expect - wrap_value;
                expect_overflow = true;
            }
            if (expect < min_value) {
                expect = expect + wrap_value;
                expect_overflow = true;
            }
            if (expect_overflow != overflow) {
                printf("WHAT\n");
                return 1;
            }
        }
    }
    return 0;
}
