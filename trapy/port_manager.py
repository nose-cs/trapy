import json


class ConnException(Exception):
    pass


def get_port():
    with open("./ports.json") as fp:
        occupied_ports = json.load(fp)

    for port in range(int(2 ** 16)):
        if port in occupied_ports:
            continue

        with open("./ports.json", "w") as fp:
            json.dump(occupied_ports + [port], fp=fp, ensure_ascii=False, indent=2)
        return port

    raise ConnException("no port available")


def bind(port):
    with open("./ports.json") as fp:
        occupied_ports = json.load(fp)
    if port in occupied_ports:
        raise ConnException("port " + str(port) + " is occupied")
    with open("./ports.json", "w") as fp:
        json.dump(occupied_ports + [port], fp=fp, ensure_ascii=False, indent=2)


def close_port(port):
    with open("./ports.json") as fp:
        occupied_ports = json.load(fp)

    if port not in occupied_ports:
        raise ConnException("port " + str(port) + " is not occupied")

    with open("./ports.json", "w") as fp:
        json.dump(
            [p for p in occupied_ports if p != port],
            fp=fp,
            ensure_ascii=False,
            indent=2,
        )
