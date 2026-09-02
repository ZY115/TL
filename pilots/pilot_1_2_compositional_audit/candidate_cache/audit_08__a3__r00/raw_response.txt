class Monitor:
    def reset(self):
        self.trace = []

    def step(self, propositions):
        self.trace.append(set(propositions))

    def finish(self):
        n = len(self.trace)
        for k in range(n):
            if 'C' not in self.trace[k]:
                continue
            if all('X' not in self.trace[m] for m in range(k)):
                return True
        return False
