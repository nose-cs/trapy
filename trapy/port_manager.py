import json
import pathlib


class ConnException(Exception):
    pass


class PortManager:
    def __init__(self, filename="ports.json"):
        """
        Keeps track of the ports in use.

        Args:
        filename (optional, defaults to "./ports.json"): This specified file contains a list of ports that are
        already occupied.
        """

        path = pathlib.Path(__file__).parent.resolve().joinpath(filename)
        self.filepath = path
        print(path)
        with open(path) as fp:
            self.occupied_ports = set(json.load(fp))

    def __save(self):
        with open(self.filepath, "w") as fp:
            json.dump(list(self.occupied_ports), fp, ensure_ascii=False, indent=2)

    def get_port(self):
        """
        Searches for an unoccupied port and mark it as occupied.

        Returns:
            The port number.

        Raises:
            ConnException: if no ports are available.
        """
        for port in range(int(2 ** 16)):
            if port not in self.occupied_ports:
                self.occupied_ports.add(port)
                self.__save()
                return port
        raise ConnException("no port available")

    def bind(self, port):
        """
        Reserves an specific port.

        Args:
            port (int): Port number

        Raises:
            ConnException: if the port is occupied
        """
        if port in self.occupied_ports:
            raise ConnException("port " + str(port) + " is occupied")
        self.occupied_ports.add(port)
        self.__save()

    def close_port(self, port):
        """
        Closes an specific port.

        Args:
            port (int): Port number

        Raises:
            ConnException: if the port is not occupied
        """
        if port not in self.occupied_ports:
            raise ConnException("port " + str(port) + " is not occupied")
        self.occupied_ports.remove(port)
        self.__save()
