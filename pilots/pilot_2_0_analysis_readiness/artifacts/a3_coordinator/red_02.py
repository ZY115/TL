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
        return any('B' in t[k] for k in range(i + 1, n)) and any('A' in s for s in t)
