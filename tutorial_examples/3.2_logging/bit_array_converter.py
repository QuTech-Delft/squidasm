from typing import List


def from_bit_str(string: str) -> List[int]:
    bits = []
    for i in range(len(string)):
        bit = int(string[i])
        assert bit==0 or bit==1
        bits.append(bit)
    return bits


def to_bit_str(bits: List[int]) -> str:
    string = ""
    for bit in bits:
        string += str(bit)
    return string
