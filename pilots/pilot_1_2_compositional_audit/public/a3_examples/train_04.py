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
            window = range(i + 1, min(i + 5, n))
            if not any('B' in self.trace[j] for j in window):
                return False
        return True
