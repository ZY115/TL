class Monitor:
    def reset(self):
        self.trace = []

    def step(self, propositions):
        self.trace.append(set(propositions))

    def finish(self):
        if any('X' in props for props in self.trace):
            return False
        return any('A' in props for props in self.trace)
