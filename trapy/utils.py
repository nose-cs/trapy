import socket

from struct import pack, unpack


def parse_address(address):
    host, port = address.split(':')

    if host == '':
        host = 'localhost'

    return host, int(port)


def get_checksum(data):
    sum = 0
    for i in range(0, len(data), 2):
        if i < len(data) and (i + 1) < len(data):
            sum += data[i] + (data[i + 1]) << 8
        elif i < len(data) and (i + 1) == len(data):
            sum += data[i]
    addon_carry = (sum & 0xFFFF) + (sum >> 16)
    result = (~addon_carry) & 0xFFFF
    result = result >> 8 | ((result & 0x00FF) << 8)
    return result


def build_tcp_header(source_port, dest_port, seq, ack, data=b"", syn=0, fin=0,
                     rst=0, _ack=0):
    tcp_source = source_port
    tcp_dest = dest_port
    tcp_seq = seq
    tcp_ack_seq = ack
    tcp_doff = 5
    tcp_fin = fin
    tcp_syn = syn
    tcp_rst = rst
    tcp_psh = 0
    tcp_ack = _ack
    tcp_urg = 0
    tcp_window = socket.htons(5840)
    tcp_check = 0
    tcp_urg_ptr = 0

    tcp_offset_res = (tcp_doff << 4) + 0
    tcp_flags = (
        tcp_fin
        + (tcp_syn << 1)
        + (tcp_rst << 2)
        + (tcp_psh << 3)
        + (tcp_ack << 4)
        + (tcp_urg << 5)
    )

    tcp_header = pack(
        "!HHLLBBHHH",
        tcp_source,
        tcp_dest,
        tcp_seq,
        tcp_ack_seq,
        tcp_offset_res,
        tcp_flags,
        tcp_window,
        tcp_check,
        tcp_urg_ptr,
    )

    placeholder = 0
    protocol = socket.IPPROTO_TCP

    tcp_length = 20 + len(data)

    pseudo_header = pack("!BBH", placeholder, protocol, tcp_length)

    total_header = pseudo_header + tcp_header
    total_header = total_header + data

    tcp_check = get_checksum(total_header)

    tcp_header = pack(
        "!HHLLBBHHH",
        tcp_source,
        tcp_dest,
        tcp_seq,
        tcp_ack_seq,
        tcp_offset_res,
        tcp_flags,
        tcp_window,
        tcp_check,
        tcp_urg_ptr,
    )
    return tcp_header


def _get_packet(data, conn):
    ip_header = data[0:20]
    ip_header = unpack("!BBHHHBBH4s4s", ip_header)

    tcp_header = data[20:40]
    tcp_header = unpack("!HHLLBBHHH", tcp_header)

    data = data[40:]

    if tcp_header[1] == conn.source_address[1]:
        return ip_header, tcp_header, data
    else:
        return None


def get_packet(data, conn):
    ip_header = data[0:20]
    ip_header = unpack("!BBHHHBBH4s4s", ip_header)

    tcp_header = data[20:40]
    tcp_header = unpack("!HHLLBBHHH", tcp_header)

    data = data[40:]

    if (
        tcp_header[1] == conn.source_address[1]
        and tcp_header[0] == conn.dest_address[1]
        and socket.inet_ntoa(ip_header[8]) == conn.dest_address[0]
        and verify_checksum(ip_header, tcp_header, data)
    ):
        return ip_header, tcp_header, data
    else:
        return None


def verify_checksum(ip_header, tcp_header, data=b""):
    placeholder = 0
    if len(data) > 0:
        tcp_length = 20 + len(data)
    else:
        tcp_length = 20
    protocol = ip_header[6]

    received_tcp_segment = pack(
        "!HHLLBBHHH",
        tcp_header[0],
        tcp_header[1],
        tcp_header[2],
        tcp_header[3],
        tcp_header[4],
        tcp_header[5],
        tcp_header[6],
        0,
        tcp_header[8],
    )
    pseudo_hdr = pack("!BBH", placeholder, protocol, tcp_length)
    total_msg = pseudo_hdr + received_tcp_segment
    if data is not None:
        total_msg += data

    checksum_from_packet = tcp_header[7]
    tcp_checksum = get_checksum(total_msg)

    return checksum_from_packet == tcp_checksum
