class Monitor:
    def reset(self):
        self.trace = []

    def step(self, propositions):
        self.trace.append(set(propositions))

    def finish(self):
        n = len(self.trace)
        for i in range(n):
            if 'B' not in self.trace[i]:
                continue
            ok = False
            for k in range(i, n):
                if 'C' not in self.trace[k]:
                    continue
                if all('X' not in self.trace[m] for m in range(i, k)):
                    ok = True
                    break
            if not ok:
                return False
        return True
