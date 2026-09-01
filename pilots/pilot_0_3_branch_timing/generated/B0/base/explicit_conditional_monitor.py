def evaluate(trajectory):
    if not trajectory or trajectory[0] != "S":
        return False
    expected_stage = 1
    success = False
    seen_named = set()
    for step, event in enumerate(trajectory):
        if event != "O":
            if event in seen_named:
                return False
            seen_named.add(event)
        if event == "E":
            success = expected_stage == 1 and True
            return success
    return success
