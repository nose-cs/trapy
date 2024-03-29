from utils import get_packet, socket


class RecvTask:
    def __init__(self):
        self.is_runing = True
        self.received = []

    def stop(self):
        self.is_runing = False

    def _recv(self, conn):
        """
        Receives data from the provided connection until the task stops running.

        Args:
            conn (Conn): A Conn object representing the network connection.
        """

        conn.socket.settimeout(0.01)
        while self.is_runing:
            try:
                data, _ = conn.socket.recvfrom(65565)
                ip_header, tcp_header, data = get_packet(data, conn)
                self.received.append((ip_header, tcp_header, data))

            except (socket.timeout, TypeError):
                continue
