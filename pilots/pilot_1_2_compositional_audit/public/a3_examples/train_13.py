class Monitor:
    def reset(self):
        self.trace = []

    def step(self, propositions):
        self.trace.append(set(propositions))

    def finish(self):
        n = len(self.trace)
        x_never = not any('X' in props for props in self.trace)
        idx_a = None
        for i, props in enumerate(self.trace):
            if 'A' in props:
                idx_a = i
                break
        plan1 = False
        if idx_a is not None and x_never:
            plan1 = any('B' in self.trace[j] for j in range(idx_a + 1, n))
        plan2 = any('D' in props for props in self.trace)
        return plan1 or plan2
