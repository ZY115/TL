class Monitor:
    def reset(self):
        self.t = []

    def step(self, propositions):
        self.t.append(set(propositions))

    def finish(self):
        t = self.t
        n = len(t)
        i = next((k for k in range(n) if 'A' in t[k]), None)
        if i is None: return False
        j = next((k for k in range(i + 1, n) if 'B' in t[k]), None)
        if j is None: return False
        return any('C' in t[k] for k in range(j + 1, n))
