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
            satisfied = False
            for j in range(i + 1, min(i + 4, n)):
                if 'B' not in self.trace[j]:
                    continue
                if any('C' in self.trace[k] for k in range(j, n)):
                    satisfied = True
                    break
            if not satisfied:
                return False
        return True
