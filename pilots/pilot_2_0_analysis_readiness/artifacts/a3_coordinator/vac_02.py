class Monitor:
    def reset(self):
        self.t = []

    def step(self, propositions):
        self.t.append(set(propositions))

    def finish(self):
        t = self.t
        n = len(t)
        i = next((k for k in range(n) if 'C' in t[k]), None)
        if i is None or not any('D' in t[k] for k in range(i + 1, n)): return False
        if any('X' in s for s in t): return False
        for k in range(n):
            if 'X' in t[k] and not any('D' in t[m] for m in range(k, n)): return False
        return True
