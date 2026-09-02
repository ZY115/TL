class Monitor:
    def reset(self):
        self.trace = []

    def step(self, propositions):
        self.trace.append(set(propositions))

    def finish(self):
        n = len(self.trace)
        for i in range(n):
            if 'A' not in self.trace[i]:
                continue
            found = any('B' in self.trace[j] or 'C' in self.trace[j] for j in range(i, n))
            if not found:
                return False
        return True
