def evaluate(trajectory):
    if not trajectory or trajectory[0] != "S":
        return False
    expected_stage = 1
    success = False
    selected_1 = None
    start_1 = None
    done_1 = False
    for step, event in enumerate(trajectory):
        if event == "E":
            success = expected_stage == 2 and done_1
            return success
        elif event == "L1":
            if expected_stage != 1:
                return False
            selected_1 = "L"
            start_1 = step
            expected_stage += 1
        elif event == "R1":
            if expected_stage != 1:
                return False
            selected_1 = "R"
            start_1 = step
            expected_stage += 1
        elif event == "P1" and selected_1 == "L":
            if not 1 <= step - start_1 <= 8:
                return False
            done_1 = True
        elif event == "Q1" and selected_1 == "R":
            if not 1 <= step - start_1 <= 10:
                return False
            done_1 = True
    return success
