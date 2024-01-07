from threading import Thread
from port_manager import PortManager
from threads import RecvTask
from utils import (
    parse_address,
    build_packet,
    get_packet,
    clean_in_buffer,
)
import socket
import time


class Conn:
    """
    Represents a network connection.

    Attributes:
        socket: it can either be a raw socket or an existing socket passed during the creation of the instance.

        fragment_size: maximum size of data packets that can be sent or received through the connection.

        seq: sequence number.

        ack: acknowledgment number.

        source_address: source IP address of the connection.

        dest_address: destination IP address of the connection.

        time_limit: time limit for network operations. It is used to control how long to wait before considering that an
        operation has failed.

        time_errors_count: counter for time errors

        received_buffer: buffer where received data from the connection is stored.
    """

    def __init__(self, sock=None, size=1024):
        if sock is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
        else:
            self.socket = sock

        self.fragment_size = size
        self.seq = 0

        self.ack = None

        self.source_address = None
        self.dest_address = None
        self.time_limit = 0.25
        self.time_errors_count = 0
        self.received_buffer = b""

    def get_time_limit(self):
        """
        Doubles the current time limit and increments the time errors count.

        Returns:
            None: if the errors count reaches 10.
            The current time limit: otherwise.
        """
        result = self.time_limit
        self.time_limit = self.time_limit * 2
        self.time_errors_count += 1
        if self.time_errors_count == 10:
            return None
        return result

    def reset_time_limit(self):
        """
        Resets the time limit and errors count to their default values.
        """
        self.time_limit = 0.25
        self.time_errors_count = 0


class ConnException(Exception):
    pass


def listen(address: str) -> Conn:
    """
    Prepares a connection that accepts packets sent to address.

    Args:
        address (str): A string representing the IP address and port number where the connection will listen for
        incoming packets.

    Returns:
        A Conn object representing the prepared connection.
    """

    print("LISTEN")
    conn = Conn()

    print("socket binded to: " + address)
    conn.source_address = parse_address(address)

    port_manager = PortManager()
    port_manager.bind(conn.source_address[1])

    return conn


def accept(conn: Conn, size=1024) -> Conn:
    """
    Waits for a connection request using a Conn previously created with listen.

    Args:
        conn: A Conn object representing a network connection.

        size (optional): An integer representing the maximum size of the data packets that can be sent or received
        through the connection. Defaults to 1024.

    Returns:
        A new Conn object representing the accepted connection.
    """
    print("ACCEPT")

    while True:
        conn.socket.settimeout(None)
        try:
            data, address = conn.socket.recvfrom(1024)
            _, tcp_header, _ = get_packet(data, conn)
        except (TypeError, socket.timeout):
            continue

        if (tcp_header[5] >> 1 & 0x01) != 1:
            print(
                "Failed to accept conection from: "
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
                print("Resending second SYN-ACK")
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
    """
    Establishes a connection with a remote address.

    Args:
        address (str): A string representing the IP address and port number of the remote address.
        size (optional): An integer representing the maximum size of the data packets that can be sent or received
        through the connection. Defaults to 1024.

    Returns:
        A Conn object representing the established connection.
    """
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
            print("Resending SYN")
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

    print("Succesfull handshake")
    print((conn.seq, conn.ack))

    packet = build_packet(conn.source_address, conn.dest_address, conn.seq, conn.ack + 1)
    conn.socket.sendto(packet, conn.dest_address)

    return conn


def send(conn: Conn, data: bytes) -> int:
    """
    Sends data over a network connection.

    Args:
        conn (Conn): A Conn object representing the network connection.
        data (bytes): A byte string containing the data to be sent.

    Returns:
        An integer representing the number of bytes sent.
    """
    if len(data) >= 2**32:
        left = send(conn, data[: data / 2])
        right = send(conn, data[data / 2:])
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

        if len(recv_task.received) > 0:
            # conn.reset_time_limit()

            _, tcp_header, _ = recv_task.received.pop(0)

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
                    recv_task.received.clear()
                    curr_ack = ack
                    window = ack

        if timer is not None and time.time() - timer > conn.time_limit:
            print("Resend from " + str(curr_ack))
            window = curr_ack
            time_limit = conn.get_time_limit()
            timer = time.time()

        if curr_ack >= window:

            window = max(curr_ack, window)

            final_window = window + window_size

            while window <= final_window and window < len(data):

                if window + size >= len(data):
                    to_send = data[window:]
                    packet = build_packet(
                        conn.source_address,
                        conn.dest_address,
                        window,
                        3,
                        fin=1,
                        data=to_send,
                    )
                else:
                    to_send = data[window: window + size]
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
    """
    Receives data stored in the network connection's buffer.

    Args:
    conn (Conn): A Conn object representing the network connection.
    length (int): An integer representing the amount of data to be received.

    Returns:
    A byte string containing the received data.
    """

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
            if len(conn.received_buffer) < length:
                result = conn.received_buffer[:]
                conn.received_buffer = b""
                print("Received " + str(len(result)) + " bytes of data")
                return result
            else:
                result = conn.received_buffer[0:length]
                conn.received_buffer = conn.received_buffer[length:]
                print("Received " + str(len(result)) + " bytes of data")
                return result

        if len(recv_task.received) > 0:

            timer = time.time()
            conn.reset_time_limit()
            _, tcp_header, data = recv_task.received.pop(0)

            if len(data) == 0 and (tcp_header[5] & 0x01) == 1:
                recv_task.is_runing = False
                t.join()
                return b""

            if (tcp_header[5] >> 4 & 0x01) == 1:
                continue

            seq_received = tcp_header[2]
            if seq_received <= conn.ack:

                packet = build_packet(conn.source_address, conn.dest_address, 7, conn.ack, _ack=1)

                if seq_received == conn.ack:
                    conn.received_buffer += data
                    conn.ack = seq_received + len(data)

                conn.socket.sendto(packet, conn.dest_address)

                if (tcp_header[5] & 0x01) == 1 or len(conn.received_buffer) >= length:

                    recv_task.is_runing = False
                    t.join()

                    if len(conn.received_buffer) < length:
                        result = conn.received_buffer[:]
                        conn.received_buffer = b""
                        print("Received " + str(len(result)) + " bytes of data")
                        return result
                    else:
                        result = conn.received_buffer[0:length]
                        conn.received_buffer = conn.received_buffer[length:]
                        print("Received " + str(len(result)) + " bytes of data")
                        return result

            elif seq_received > conn.ack:
                print("Restart from " + str(conn.ack))
                recv_task.received.clear()
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
            packet = build_packet(conn.source_address, conn.dest_address, 7, conn.ack, _ack=1)
            conn.socket.sendto(packet, conn.dest_address)


def close(conn: Conn):
    """
    Closes a network connection.

    Args:
    conn (Conn): A Conn object representing the network connection.
    """

    print("CLOSE")

    if (conn.dest_address is not None):
        packet = build_packet(conn.source_address, conn.dest_address, conn.seq, 3, fin=1)
        conn.socket.sendto(packet, conn.dest_address)

    conn.socket.close()
    conn.socket = None

    port_manager = PortManager()
    port_manager.close_port(conn.source_address[1])
