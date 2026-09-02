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
            if 'A' in t[k] and not any('B' in t[m] for m in range(k + 1, min(k + 4, n))): return False
        return True
