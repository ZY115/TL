class Monitor:
    def reset(self):
        self.t = []

    def step(self, propositions):
        self.t.append(set(propositions))

    def finish(self):
        t = self.t
        n = len(t)
        return any('B' in s for s in t) and not any('X' in s for s in t)
