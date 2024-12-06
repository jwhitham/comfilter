import settings


def main() -> None:
    with open("generated/settings.h", "wt", encoding="utf-8") as fd:
        fd.write(f"""
#define UPPER_FREQUENCY     {settings.UPPER_FREQUENCY:1.1f}
#define LOWER_FREQUENCY     {settings.LOWER_FREQUENCY:1.1f}
#define BAUD_RATE           {settings.BAUD_RATE:1.1f}
#define FRACTIONAL_BITS     {settings.FRACTIONAL_BITS:d}
#define NON_FRACTIONAL_BITS {settings.NON_FRACTIONAL_BITS:d}
#define RC_DECAY_PER_BIT    {settings.RC_DECAY_PER_BIT:1.5f}
#define FILTER_WIDTH        {settings.FILTER_WIDTH:1.1f}
#define SAMPLE_RATE         {settings.SAMPLE_RATE:d}
""")

if __name__ == "__main__":
    main()
