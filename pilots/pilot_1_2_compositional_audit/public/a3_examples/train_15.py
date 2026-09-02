class Monitor:
    def reset(self):
        self.trace = []

    def step(self, propositions):
        self.trace.append(set(propositions))

    def finish(self):
        n = len(self.trace)
        idx_c = None
        for i, props in enumerate(self.trace):
            if 'C' in props:
                idx_c = i
                break
        cond1 = idx_c is not None and any('D' in self.trace[j] for j in range(idx_c + 1, n))
        cond2 = True
        for i in range(n):
            if 'C' not in self.trace[i]:
                continue
            window = range(i + 1, min(i + 6, n))
            if not any('D' in self.trace[j] for j in window):
                cond2 = False
                break
        return cond1 and cond2
