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
            option1 = False
            for j in range(i + 1, min(i + 3, n)):
                if 'B' not in self.trace[j]:
                    continue
                if any('C' in self.trace[k] for k in range(j, n)):
                    option1 = True
                    break
            option2 = any('D' in self.trace[m] for m in range(i, n))
            if not (option1 or option2):
                return False
        return True
