class Mapper:
    def __init__(self, initial_seq, max_seq, window_size, fragment_size):
        self.map = {}
        self.window_size = window_size
        self.fragment_size = fragment_size
        self.mod = max_seq
        self.initial_seq = initial_seq
        self.last = (initial_seq + window_size - 1) % max_seq
        self.n = 0

        for i in range(initial_seq, initial_seq + window_size):
            if i >= max_seq:
                i = i % max_seq
            self.map[i] = self.n
            self.n += 1

    def get(self, seq):

        if (self.last - seq >= 0 and self.last - seq <= self.fragment_size) or (
            self.last - seq < 0
            and ((self.mod - 1) - seq + self.last) <= self.fragment_size
        ):
            for _ in range(3 * self.window_size):
                self.last = (self.last + 1) % self.mod
                self.map[self.last] = self.n
                self.n += 1
                _ = self.map.pop((self.last - 6 * self.window_size) % self.mod, None)

        return self.map[seq]