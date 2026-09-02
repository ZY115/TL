class Monitor:
    def reset(self):
        self.t = []

    def step(self, propositions):
        self.t.append(set(propositions))

    def finish(self):
        t = self.t
        n = len(t)
        # A, then B, then C at strictly increasing steps; separately, no X
        # strictly before the first C in the trace.
        i = next((k for k in range(n) if 'A' in t[k]), None)
        if i is None: return False
        j = next((k for k in range(i + 1, n) if 'B' in t[k]), None)
        if j is None: return False
        if not any('C' in t[k] for k in range(j + 1, n)): return False
        c = next((k for k in range(n) if 'C' in t[k]), None)
        return c is not None and all('X' not in t[m] for m in range(c))
