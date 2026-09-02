class Monitor:
    def reset(self):
        self.t = []

    def step(self, propositions):
        self.t.append(set(propositions))

    def finish(self):
        t = self.t
        n = len(t)
        c = next((k for k in range(n) if 'C' in t[k]), None)
        if c is None: return False
        if any('X' in t[m] for m in range(c)): return False
        return not any('C' in s for s in t)
