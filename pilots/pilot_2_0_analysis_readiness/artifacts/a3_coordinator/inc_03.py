class Monitor:
    def reset(self):
        self.t = []

    def step(self, propositions):
        self.t.append(set(propositions))

    def finish(self):
        t = self.t
        n = len(t)
        if not any('A' in s for s in t): return False
        for k in range(n):
            if 'A' in t[k] and not (k + 1 < n and 'B' in t[k + 1]): return False
        return not any('B' in s for s in t)
