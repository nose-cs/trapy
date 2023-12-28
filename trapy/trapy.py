import socket, random, time

from utils import parse_address, build_tcp_header, _get_packet, get_packet
from port_manager import bind, close_port, get_port

class Conn:
    def __init__(self, sock = None, size = 1024):
        if sock is None:
            self.socket = socket.socket(
                socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP
            )
        else:
            self.socket = sock

        self.fragment_size = size
        self.seq_limit = 2 ** 32
        self.seq = random.randint(0, self.seq_limit)

        self.ack = None

        self.source_address = None
        self.dest_address = None
        self.time_limit = 0.25
        self.time_errors_count = 1
        self.recived_buffer = b""

    def get_time_limit(self):
        result = self.time_limit
        self.time_limit = self.time_limit * 2
        self.time_errors_count += 1
        if self.time_errors_count == 10:
            return None
        return result

    def reset_time_limit(self):
        self.time_limit = 0.25
        self.time_errors_count = 1


class ConnException(Exception):
    pass


def listen(address: str) -> Conn:
    print("LISTEN")
    conn = Conn()

    print("socket binded to: " + address)
    conn.source_address = parse_address(address)
    bind(conn.source_address[1])

    return conn


def accept(conn: Conn, size = 1024) -> Conn:
    print("ACCEPT")

    while True:
        #ignore timeout
        conn.socket.settimeout(None)
        try:
            data, address = conn.socket.recvfrom(1024)
            _, tcp_header, _ = _get_packet(data, conn)
        except (TypeError, socket.timeout):
            continue

        #check SYN flag
        if (tcp_header[5] >> 1 & 0x01) == 0:
            print(f"Failed to accept the connection from: {(address[0], tcp_header[0])}, SYN flag has value 0")
            continue

        new_conn = Conn(size = size)

        new_conn.source_address = (conn.source_address[0],get_port())

        new_conn.dest_address = (address[0], tcp_header[0])

        print(f"Accepted connection from:  {str((address[0], tcp_header[0]))}")

        resp_tcp_header = build_tcp_header(
            new_conn.source_address[1],
            new_conn.dest_address[1],
            new_conn.seq,
            tcp_header[2] + 1,
            syn=1,
        )

        packet = resp_tcp_header

        new_conn.socket.sendto(packet, new_conn.dest_address)

        new_conn.ack = tcp_header[2]

        reset = False
        time_limit = new_conn.get_time_limit()
        timer = time.time()
        new_conn.socket.settimeout(1)

        while True:

            if time_limit is None:
                reset = True
                break

            if time.time() - timer > time_limit:
                print("Resending SYN-ACK")
                timer = time.time()
                new_conn.socket.sendto(packet, new_conn.dest_address)
                time_limit = new_conn.get_time_limit()

            try:
                data, address = new_conn.socket.recvfrom(1024)

            except socket.timeout:
                continue

            try:
                _, _, _ = get_packet(data, new_conn)
                new_conn.reset_time_limit()
                break
            except TypeError:
                continue

        new_conn.socket.settimeout(None)

        if reset:
            print("Accepted reset")
            close(new_conn)
            continue

        print("Succesfull handshake")
        print((new_conn.seq, new_conn.ack))

        return new_conn


def dial(address) -> Conn:
    pass


def send(conn: Conn, data: bytes) -> int:
    pass


def recv(conn: Conn, length: int) -> bytes:
    pass


def close(conn: Conn):
    print("CLOSE")
    tcp_header = build_tcp_header(
        conn.source_address[1], conn.dest_address[1], conn.seq, 3, fin=1
    )
    conn.socket.sendto(tcp_header, conn.dest_address)
    conn.socket.close()
    conn.socket = None
    close_port(conn.source_address[1])
