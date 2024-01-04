from mapper import Mapper
from threading import Thread
from port_manager import get_port, bind, close_port
from threads import RecvTask
from utils import (
    parse_address,
    build_packet,
    get_packet,
    clean_in_buffer,
)
import random, socket, time

class Conn:
    def __init__(self, sock=None, size=1024):
        if sock is None:
            self.socket = socket.socket(
                socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW
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


def accept(conn : Conn, size=1024) -> Conn:
    print("ACCEPT")

    while True:
        conn.socket.settimeout(None)
        try:
            data, address = conn.socket.recvfrom(1024)
            ip_header, tcp_header, _ = get_packet(data, conn)
        except (TypeError, socket.timeout):
            continue

        if (tcp_header[5] >> 1 & 0x01) != 1:
            print(
                "field to accept conection from: "
                + str((address[0], tcp_header[0]))
                + " syn flag has value 0"
            )
            continue

        new_conn = Conn(size=size)
        new_conn.source_address = (
            conn.source_address[0],
            get_port(),
        )
        new_conn.dest_address = (address[0], tcp_header[0])

        print("accepted connection from: " + str((address[0], tcp_header[0])))

        packet = build_packet(
            new_conn.source_address,
            new_conn.dest_address,
            new_conn.seq,
            tcp_header[2] + 1,
            syn=1,
        )

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
                print("re-sending second SYN-ACK")
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
            print("Reset accept")
            close(new_conn)
            continue

        print("Succesfull handshake")
        print((new_conn.seq, new_conn.ack))

        return new_conn


def dial(address, size=1024) -> Conn:
    print("DIAL")
    conn = Conn(size=size)

    conn.source_address = (conn.socket.getsockname()[0], get_port())
    conn.dest_address = parse_address(address)

    packet = build_packet(conn.source_address, conn.dest_address, conn.seq, 7,syn=1)

    print("dial to: " + str(address))

    conn.socket.sendto(packet, conn.dest_address)

    close_dial = False
    time_limit = conn.get_time_limit()
    timer = time.time()
    conn.socket.settimeout(1)
    while True:
        if time_limit is None:
            close_dial = True
            break

        if time.time() - timer > time_limit:
            print("re-sending SYN")
            conn.socket.sendto(packet, conn.dest_address)
            time_limit = conn.get_time_limit()
            timer = time.time()
            continue

        try:
            try:
                data, address = conn.socket.recvfrom(1024)
            except socket.timeout:
                continue

            ip_header, tcp_header, _ = get_packet(data, conn)
            conn.reset_time_limit()
            break
        except TypeError:
            continue

    conn.socket.settimeout(None)
    if close_dial:
        raise ConnException("Dial Failed")

    conn.ack = tcp_header[2]

    conn.dest_address = (socket.inet_ntoa(ip_header[8]), tcp_header[0])

    print("Succesful handshake")
    print((conn.seq, conn.ack))

    packet = build_packet(conn.source_address, conn.dest_address, conn.seq, conn.ack + 1)
    conn.socket.sendto(packet, conn.dest_address)

    return conn


def send(conn: Conn, data: bytes) -> int:
    print("SEND")
    size = conn.fragment_size
    window_size = size * 20

    window = conn.seq
    duplicated_ack = 0
    mapper = Mapper(conn.seq, conn.seq_limit, len(data), window_size, size)
    recv_task = RecvTask()
    t = Thread(target=recv_task._recv, args=[conn])
    t.start()

    timer = None
    time_limit = conn.get_time_limit()

    while True:
        if time_limit is None:
            recv_task.stop()
            t.join()
            print("Expired Connection")
            return mapper.get(window)

        if len(recv_task.recived) > 0:
            conn.reset_time_limit()

            _, tcp_header, _ = recv_task.recived.pop(0)

            if (tcp_header[5] >> 4 & 0x01) != 1:
                continue

            ack = tcp_header[3] % conn.seq_limit

            if mapper.get(ack) >= len(data):
                recv_task.stop()
                t.join()
                print("Sended " + str(len(data)) + " bytes of data")
                return len(data)

            if mapper.get(ack) > mapper.get(window):
                if conn.seq != window:
                    timer = time.time()
                else:
                    timer = None

                window = ack % conn.seq_limit
                duplicated_ack = 0

            else:
                duplicated_ack += 1
                if duplicated_ack == 3:
                    recv_task.recived.clear()
                    conn.seq = ack % conn.seq_limit
                    duplicated_ack = 0

        if timer is not None and time.time() - timer > conn.time_limit:
            conn.seq = window % conn.seq_limit
            time_limit = conn.get_time_limit()
            timer = time.time()

        if (
            (mapper.get(conn.seq) < (mapper.get(window) + window_size))
            and (mapper.get(conn.seq) < len(data))
            or len(data) == 0
        ):

            if timer is None:
                timer = time.time()

            if mapper.get(conn.seq) + size >= len(data):
                to_send = data[mapper.get(conn.seq) :]
                packet = build_packet(
                    conn.source_address,
                    conn.dest_address,
                    conn.seq,
                    3,
                    fin=1,
                    data=to_send,
                )
            else:
                to_send = data[mapper.get(conn.seq) : mapper.get(conn.seq) + size]
                packet = build_packet(
                    conn.source_address,
                    conn.dest_address,
                    conn.seq,
                    4,
                    data=to_send,
                )

            conn.socket.sendto(packet, conn.dest_address)
            conn.seq = (conn.seq + len(to_send)) % conn.seq_limit


def recv(conn: Conn, length: int) -> bytes:
    print("RECV")
    recv_task = RecvTask()
    t = Thread(target=recv_task._recv, args=[conn])
    t.start()
    timer = time.time()
    time_limit = conn.get_time_limit()
    retr = 0
    while True:
        if time_limit is None:
            recv_task.is_runing = False
            t.join()
            clean_in_buffer(conn)
            print("Expired connection")
            if len(conn.recived_buffer) < length:
                result = conn.recived_buffer[:]
                conn.recived_buffer = b""
                print("recived " + str(len(result)) + " bytes of data")
                return result
            else:
                result = conn.recived_buffer[0:length]
                conn.recived_buffer = conn.recived_buffer[length:]
                print("recived " + str(len(result)) + " bytes of data")
                return result

        if len(recv_task.recived) > 0:

            timer = time.time()
            conn.reset_time_limit()
            _, tcp_header, data = recv_task.recived.pop(0)

            if (tcp_header[5] >> 4 & 0x01) == 1:
                continue

            seq_recived = tcp_header[2]
            if seq_recived == conn.ack:

                retr = 0
                conn.ack = (seq_recived + len(data)) % conn.seq_limit

                conn.recived_buffer += data
                packet = build_packet(
                    conn.source_address, conn.dest_address, 7, conn.ack, _ack=1
                )

                conn.socket.sendto(packet, conn.dest_address)
                
                if (tcp_header[5] & 0x01) == 1 or len(conn.recived_buffer) >= length:
                    
                    for _ in range(3):
                        conn.socket.sendto(packet, conn.dest_address)
                    
                    recv_task.is_runing = False
                    t.join()

                    if len(conn.recived_buffer) < length:
                        result = conn.recived_buffer[:]
                        conn.recived_buffer = b""
                        print("recived " + str(len(result)) + " bytes of data")
                        return result
                    else:
                        result = conn.recived_buffer[0:length]
                        conn.recived_buffer = conn.recived_buffer[length:]
                        print("recived " + str(len(result)) + " bytes of data")
                        return result

            else:

                retr += 1
                if retr == 3:
                    retr = 0
                    recv_task.recived.clear()
                    packet = build_packet(
                        conn.source_address,
                        conn.dest_address,
                        7,
                        conn.ack,
                        _ack=1,
                    )
                    conn.socket.sendto(packet, conn.dest_address)

        if timer is not None and time.time() - timer > time_limit:
            timer = time.time()
            time_limit = conn.get_time_limit()
            
            print("re-sending ack " + str(conn.ack))
            
            packet = build_packet(
                conn.source_address, conn.dest_address, 7, conn.ack, _ack=1
            )
            
            conn.socket.sendto(packet, conn.dest_address)


def close(conn: Conn):
    print("CLOSE")
    
    packet = build_packet(
        conn.source_address, conn.dest_address, conn.seq, 3, fin=1
    )
    
    conn.socket.sendto(packet, conn.dest_address)
    conn.socket.close()
    conn.socket = None
    
    close_port(conn.source_address[1])