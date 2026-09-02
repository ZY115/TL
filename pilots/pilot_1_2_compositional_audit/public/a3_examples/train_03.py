class Monitor:
    def reset(self):
        self.trace = []

    def step(self, propositions):
        self.trace.append(set(propositions))

    def finish(self):
        idx_a = None
        for i, props in enumerate(self.trace):
            if 'A' in props:
                idx_a = i
                break
        if idx_a is None:
            return False
        return any('B' in self.trace[j] for j in range(idx_a + 1, len(self.trace)))
