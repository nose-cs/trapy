from threading import Thread
from mapper import Mapper
from port_manager import PortManager
from threads import RecvTask
from utils import (
    parse_address,
    build_packet,
    get_packet,
    clean_in_buffer,
)
import random
import socket
import time


class Conn:
    def __init__(self, sock=None, size=1024):
        if sock is None:
            self.socket = socket.socket(
                socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW
            )
        else:
            self.socket = sock

        self.fragment_size = size
        self.seq = 0

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

    port_manager = PortManager()
    port_manager.bind(conn.source_address[1])

    return conn


def accept(conn: Conn, size=1024) -> Conn:
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
        port_manager = PortManager()

        new_conn.source_address = (
            conn.source_address[0],
            port_manager.get_port()
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

    port_manager = PortManager()
    conn.source_address = (conn.socket.getsockname()[0], port_manager.get_port())
    conn.dest_address = parse_address(address)

    packet = build_packet(conn.source_address, conn.dest_address, conn.seq, 7, syn=1)

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
    if len(data) >= 2**32 :
        left = send(conn, data[: data / 2])
        right = send(conn, data[data / 2 :])
        return left + right
    
    print("SEND")
    
    size = conn.fragment_size
    window_size = size * 20

    window = 0
    curr_ack = 0

    recv_task = RecvTask()
    t = Thread(target=recv_task._recv, args=[conn])
    t.start()

    timer = None

    if conn.get_time_limit() is not None:
        conn.reset_time_limit()
    
    time_limit = conn.get_time_limit()

    while True:
        if time_limit is None:
            recv_task.stop()
            t.join()
            print("Expired Connection")
            return window

        if len(recv_task.recived) > 0:
            # conn.reset_time_limit()

            _, tcp_header, _ = recv_task.recived.pop(0)

            if (tcp_header[5] >> 4 & 0x01) != 1:
                continue

            ack = tcp_header[3]
            
            if ack + size >= len(data):
                recv_task.stop()
                t.join()
                print("Sent " + str(len(data)) + " bytes of data")
                return len(data)

            if ack >= curr_ack:
                conn.reset_time_limit()
                time_limit = conn.get_time_limit()
                timer = time.time()
                curr_ack = ack + size

            else:
                rst = tcp_header[5] >> 2 & 0x01

                if rst == 1:
                    recv_task.recived.clear()
                    curr_ack = ack
                    window = ack

        if timer is not None and time.time() - timer > conn.time_limit:
            print("RESEND FROM " + str(curr_ack))
            window = curr_ack
            time_limit = conn.get_time_limit()
            timer = time.time()

        if curr_ack >= window:

            window = max(curr_ack, window)

            final_window = window + window_size

            while window <= final_window and window < len(data):

                if window + size >= len(data):
                    to_send = data[window : ]
                    packet = build_packet(
                        conn.source_address,
                        conn.dest_address,
                        window,
                        3,
                        fin=1,
                        data=to_send,
                    )
                else:
                    to_send = data[window : window + size]
                    packet = build_packet(
                        conn.source_address,
                        conn.dest_address,
                        window,
                        4,
                        data=to_send,
                    )

                window += size

                conn.socket.sendto(packet, conn.dest_address)

            timer = time.time()


def recv(conn: Conn, length: int) -> bytes:
    print("RECV")
    recv_task = RecvTask()
    t = Thread(target=recv_task._recv, args=[conn])
    t.start()
    
    timer = time.time()
    time_limit = conn.get_time_limit()

    conn.ack = 0

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

            if len(data) == 0 and (tcp_header[5] & 0x01) == 1:
                recv_task.is_runing = False
                t.join()
                return b""

            if (tcp_header[5] >> 4 & 0x01) == 1:
                continue

            seq_recived = tcp_header[2]
            if seq_recived <= conn.ack:

                packet = build_packet(
                    conn.source_address, conn.dest_address, 7, conn.ack, _ack=1
                )

                if seq_recived == conn.ack:
                    conn.recived_buffer += data
                    conn.ack = seq_recived + len(data)

                conn.socket.sendto(packet, conn.dest_address)
                
                if (tcp_header[5] & 0x01) == 1 or len(conn.recived_buffer) >= length:
                    
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

            elif seq_recived > conn.ack:
                print("RESTART FROM " + str(conn.ack))
                recv_task.recived.clear()
                packet = build_packet(
                    conn.source_address,
                    conn.dest_address,
                    7,
                    conn.ack,
                    rst=1,
                    _ack=1
                )
                conn.socket.sendto(packet, conn.dest_address)

        if timer is not None and time.time() - timer > time_limit:
            timer = time.time()
            time_limit = conn.get_time_limit()
            print("Resending ack " + str(conn.ack))
            packet = build_packet(
                conn.source_address, conn.dest_address, 7, conn.ack, _ack=1
            )
            conn.socket.sendto(packet, conn.dest_address)


def close(conn: Conn):
    print("CLOSE")
    
    if(conn.dest_address is not None):
        packet = build_packet(
            conn.source_address, conn.dest_address, conn.seq, 3, fin=1
        )
        
        conn.socket.sendto(packet, conn.dest_address)
    
    conn.socket.close()
    conn.socket = None

    port_manager = PortManager()
    port_manager.close_port(conn.source_address[1])
