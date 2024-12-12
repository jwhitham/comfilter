library comfilter;
use comfilter.all;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use debug_textio.all;

-- The generic defaults are the correct settings for CRC-32, matching the zlib.crc32 function,
-- assuming that bits are shifted LSB first.
--
-- For CRC-16 use polynomial = x"8005", bit_width = 16, flip = false.
--
-- Test: crc16("123456789") == 0xbb3d
-- Test: crc32("123456789") == 0xcbf43926
--
entity crc is
    generic map (
        bit_width       : Natural := 32;
        polynomial      : std_logic_vector (bit_width - 1 downto 0) := x"04C11DB7";
        flip            : Boolean := true);
    port map (
        clock_in        : std_logic := '0';
        reset_in        : std_logic := '0';
        strobe_in       : std_logic := '0';
        bit_in          : std_logic := '0';
        crc_out         : std_logic_vector (bit_width - 1 downto 0) := (others => '0'));
end entity crc;

architecture structural of crc is

    signal invert_bit       : std_logic := '0';
    signal invert_bits      : std_logic_vector (bit_width - 1 downto 0) := (others => '0');
    signal next_value       : std_logic_vector (bit_width - 1 downto 0) := (others => '0');
    signal value            : std_logic_vector (bit_width - 1 downto 0) := (others => '0');

begin

    invert_bit <= '1' when flip else '0';
    invert_bits <= (others => invert_bit);
    next_value (bit_width - 1 downto 1) <= value (bit_width - 2 downto 0);
    next_value (0) <= '0';

    process (clock_in) is
    begin
        if clock_in = '1' and clock_in'event then
            if reset_in = '1' then
                value <= invert_bits;

            elsif strobe_in = '1' then
                if (value (bit_width - 1) xor bit_in) = '1' then
                    value <= next_value xor polynomial;
                else
                    value <= next_value;
                end if;
            end if;
        end if;
    end process;

    crc_out <= value xor invert_bits;

end structural;

                if 

def crc(data, polynomial = 0x4c11db7, bit_width = 32, flip = True):
    value = 0
    if flip:
        value ^= (1 << bit_width) - 1
    # for each bit
    for byte in data:
        for j in range(8):
            bit_flag = (value >> (bit_width - 1)) ^ (byte >> (j))
            value = value << 1
            if bit_flag & 1:
                value ^= polynomial
            value &= (1 << bit_width) - 1

    if flip:
        value ^= (1 << bit_width) - 1
    # bit reverse
    value2 = 0
    for j in range(bit_width):
        value2 |= ((value >> j) & 1) << (bit_width - 1 - j)
    value = value2
    return value

def check(a):
    assert crc(a) == zlib.crc32(a)

for i in range(10):
    check(b"\x00" * i)
for i in range(1, 10):
    check(b"\x01" * i)
for i in range(1, 10):
    check(b"\x80" * i)

check(b"123456789")
check(b"hello world")

for i in range(1, 4):
    check(b"\x55\xaa\x99" * i)


def crc16(data):
    polynomial = 0x8005
    bit_width = 16
    return crc(data, polynomial, bit_width, False)

assert crc16(b"123456789") == 0xbb3d
