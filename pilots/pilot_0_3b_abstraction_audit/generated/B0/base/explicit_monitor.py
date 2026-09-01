def evaluate(trajectory):
    if not trajectory or trajectory[0] != "S":
        return False
    expected_stage = 1
    success = False
    for step, event in enumerate(trajectory):
        if event == "E":
            success = expected_stage == 1 and True
            return success
    return success
