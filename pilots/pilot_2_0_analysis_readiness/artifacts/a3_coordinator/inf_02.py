class Monitor:
    def reset(self):
        self.t = []

    def step(self, propositions):
        self.t.append(set(propositions))

    def finish(self):
        t = self.t
        n = len(t)
        i = next((k for k in range(n) if 'B' in t[k]), None)
        if i is None: return False
        return any('C' in t[k] for k in range(i + 1, n)) and not any('X' in s for s in t)
