import socket

s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)

ip_header = b'\x45\x00\x00\x28'  # Version, IHL, Type of Service | Total Length
ip_header += b'\xab\xcd\x00\x00'  # Identification | Flags, Fragment Offset
ip_header += b'\x40\x06\xa6\xec'  # TTL, Protocol | Header Checksum
ip_header += b'\x0a\x00\x00\x01'  # Source Address
ip_header += b'\x0a\x00\x00\x02'  # Destination Address

tcp_header = b'\x30\x39\x00\x50'  # Source Port | Destination Port
tcp_header += b'\x00\x00\x00\x00'  # Sequence Number
tcp_header += b'\x00\x00\x00\x00'  # Acknowledgement Number
tcp_header += b'\x50\x02\x71\x10'  # Data Offset, Reserved, Flags | Window Size
tcp_header += b'\xe6\x32\x00\x00'  # Checksum | Urgent Pointer

packet = ip_header + tcp_header
s.sendto(packet, ('10.0.0.2', 0))
