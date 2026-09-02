class Monitor:
    def reset(self):
        self.t = []

    def step(self, propositions):
        self.t.append(set(propositions))

    def finish(self):
        t = self.t
        n = len(t)
        for k in range(n):
            if 'A' in t[k]:
                if not any('B' in t[m] for m in range(k + 1, min(k + 3, n))): return False
                if not any('B' in t[m] for m in range(k + 1, min(k + 4, n))): return False
        return True
