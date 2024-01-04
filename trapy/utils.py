from struct import pack, unpack
import socket


def parse_address(address):
    host, port = address.split(":")

    if host == "":
        host = "localhost"

    return host, int(port)


def build_packet(
    source, dest, seq, ack, data=b"", syn=0, fin=0, rst=0, _ack=0
):
    # IP HEADER
    ip_ver = 4
    ip_ihl = 5
    ip_dscp = 0
    ip_total_len = 20 + 20 + len(data)  # IP header + TCP header + data
    ip_id = 54321
    ip_frag_off = 0
    ip_ttl = 255
    ip_proto = socket.IPPROTO_RAW
    ip_check = 0
    ip_saddr = socket.inet_aton(source[0])
    ip_daddr = socket.inet_aton(dest[0])

    ip_ihl_ver = (ip_ver << 4) + ip_ihl
    ip_header = pack('!BBHHHBBH4s4s', ip_ihl_ver, ip_dscp, ip_total_len, ip_id, ip_frag_off, ip_ttl, ip_proto, ip_check, ip_saddr, ip_daddr)

    # TCP HEADER
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
    tcp_flags = tcp_fin + (tcp_syn << 1) + (tcp_rst << 2) + (tcp_psh << 3) + (tcp_ack << 4) + (tcp_urg << 5)

    tcp_header = pack('!HHLLBBHHH', source[1], dest[1], tcp_seq, tcp_ack_seq, tcp_offset_res, tcp_flags, tcp_window, tcp_check, tcp_urg_ptr)

    # Pseudo header for checksum calculation
    placeholder = 0
    protocol = socket.IPPROTO_RAW
    tcp_length = len(tcp_header) + len(data)

    pseudo_header = pack("!BBH", placeholder, protocol, tcp_length)

    total_header = pseudo_header + tcp_header
    total_header = total_header + data

    tcp_check = get_checksum(total_header)

    tcp_header = pack('!HHLLBBHHH', source[1], dest[1], tcp_seq, tcp_ack_seq, tcp_offset_res, tcp_flags, tcp_window, tcp_check, tcp_urg_ptr)

    packet = ip_header + tcp_header + data

    return packet


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


def get_packet(packet, conn):
    ip_header = packet[:20]
    iph = unpack('!BBHHHBBH4s4s', ip_header)
    
    total_length = iph[2]

    tcp_header = packet[20:40]
    tcph = unpack('!HHLLBBHHH', tcp_header)

    dest_port = tcph[1]

    data = packet[40:total_length]

    #print(dest_ip)
    #print(conn.source_address)

    if (
        dest_port == conn.source_address[1]
        and verify_checksum(iph, tcph, data)
    ):
        return iph, tcph, data
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


def clean_in_buffer(conn):
    while True:
        try:
            _, _ = conn.socket.recvfrom(65565)
        except socket.timeout:
            break
