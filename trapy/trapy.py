import socket, random

from utils import parse_address, build_tcp_header
from port_manager import bind, close_port

class Conn:
    def __init__(self, sock=None, size=1024):
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


def accept(conn) -> Conn:
    pass


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
