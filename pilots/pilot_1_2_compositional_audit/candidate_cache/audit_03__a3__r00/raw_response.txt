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
        idx_b = None
        for j in range(idx_a + 1, len(self.trace)):
            if 'B' in self.trace[j]:
                idx_b = j
                break
        if idx_b is None:
            return False
        return any('C' in self.trace[k] for k in range(idx_b + 1, len(self.trace)))
