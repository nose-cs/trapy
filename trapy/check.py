with open('./source_files/a.txt', "rb") as fp:
    a = fp.read(2 ** 20)

    with open('./destination_files/b.txt', "rb") as fp:
        b = fp.read(2 ** 20)
        print(a.decode() == b.decode())
