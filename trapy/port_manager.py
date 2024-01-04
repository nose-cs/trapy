import json


class ConnException(Exception):
    pass


class PortManager:
    def __init__(self, filename="./ports.json"):
        self.filename = filename
        with open(filename) as fp:
            self.occupied_ports = set(json.load(fp))

    def __save(self):
        with open(self.filename, "w") as fp:
            json.dump(list(self.occupied_ports), fp, ensure_ascii=False, indent=2)

    def get_port(self):
        for port in range(int(2 ** 16)):
            if port not in self.occupied_ports:
                self.occupied_ports.add(port)
                self.__save()
                return port
        raise ConnException("no port available")

    def bind(self, port):
        if port in self.occupied_ports:
            raise ConnException("port " + str(port) + " is occupied")
        self.occupied_ports.add(port)
        self.__save()

    def close_port(self, port):
        if port not in self.occupied_ports:
            raise ConnException("port " + str(port) + " is not occupied")
        self.occupied_ports.remove(port)
        self.__save()
