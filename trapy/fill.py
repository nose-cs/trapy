with open('./source_files/a.txt', "wb") as fp:
    fp.write(b"".join([str(i).encode() for i in range(500000)]))
