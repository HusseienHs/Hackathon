import struct

MAGIC_COOKIE = 0xabcddcba
OFFER_TYPE = 0x2
REQUEST_TYPE = 0x3
PAYLOAD_TYPE = 0x4

# ANSI Color Codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"
CYAN = "\033[96m"

def create_offer_packet(udp_port, tcp_port):
    return struct.pack('!IBHH', MAGIC_COOKIE, OFFER_TYPE, udp_port, tcp_port)


def create_request_packet(file_size):
    return struct.pack('!IBQ', MAGIC_COOKIE, REQUEST_TYPE, file_size)


def create_payload_packet(total_segments, current_segment, payload):
    header = struct.pack('!IBQQ', MAGIC_COOKIE, PAYLOAD_TYPE, total_segments, current_segment)
    return header + payload
