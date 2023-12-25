import json

class ConnException(Exception):
    pass

def bind(port):
    with open("./files/ports.json") as fp:
        occupied_ports = json.load(fp)
    if port in occupied_ports:
        raise ConnException("port " + str(port) + " is occupied")
    with open("./files/ports.json", "w") as fp:
        json.dump(occupied_ports + [port], fp=fp, ensure_ascii=False, indent=2)

def close_port(port):
    with open("./files/ports.json") as fp:
        occupied_ports = json.load(fp)

    if port not in occupied_ports:
        raise ConnException("port " + str(port) + " is not occupied")

    with open("./files/ports.json", "w") as fp:
        json.dump(
            [p for p in occupied_ports if p != port],
            fp=fp,
            ensure_ascii=False,
            indent=2,
        )