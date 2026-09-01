def evaluate(trajectory):
    if not trajectory or trajectory[0] != "S":
        return False
    expected_stage = 1
    success = False
    selected_1 = None
    start_1 = None
    done_1 = False
    selected_2 = None
    start_2 = None
    done_2 = False
    selected_3 = None
    start_3 = None
    done_3 = False
    selected_4 = None
    start_4 = None
    done_4 = False
    selected_5 = None
    start_5 = None
    done_5 = False
    selected_6 = None
    start_6 = None
    done_6 = False
    for step, event in enumerate(trajectory):
        if event == "E":
            success = (
                expected_stage == 7
                and done_1
                and done_2
                and done_3
                and done_4
                and done_5
                and done_6
            )
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
        elif event == "L2":
            if expected_stage != 2:
                return False
            selected_2 = "L"
            start_2 = step
            expected_stage += 1
        elif event == "R2":
            if expected_stage != 2:
                return False
            selected_2 = "R"
            start_2 = step
            expected_stage += 1
        elif event == "P2" and selected_2 == "L":
            if not 1 <= step - start_2 <= 8:
                return False
            done_2 = True
        elif event == "Q2" and selected_2 == "R":
            if not 1 <= step - start_2 <= 10:
                return False
            done_2 = True
        elif event == "L3":
            if expected_stage != 3:
                return False
            selected_3 = "L"
            start_3 = step
            expected_stage += 1
        elif event == "R3":
            if expected_stage != 3:
                return False
            selected_3 = "R"
            start_3 = step
            expected_stage += 1
        elif event == "X3" and selected_3 == "L":
            if not 1 <= step - start_3 <= 8:
                return False
            done_3 = True
        elif event == "Q3" and selected_3 == "R":
            if not 1 <= step - start_3 <= 10:
                return False
            done_3 = True
        elif event == "L4":
            if expected_stage != 4:
                return False
            selected_4 = "L"
            start_4 = step
            expected_stage += 1
        elif event == "R4":
            if expected_stage != 4:
                return False
            selected_4 = "R"
            start_4 = step
            expected_stage += 1
        elif event == "P4" and selected_4 == "L":
            if not 1 <= step - start_4 <= 8:
                return False
            done_4 = True
        elif event == "Q4" and selected_4 == "R":
            if not 1 <= step - start_4 <= 10:
                return False
            done_4 = True
        elif event == "L5":
            if expected_stage != 5:
                return False
            selected_5 = "L"
            start_5 = step
            expected_stage += 1
        elif event == "R5":
            if expected_stage != 5:
                return False
            selected_5 = "R"
            start_5 = step
            expected_stage += 1
        elif event == "P5" and selected_5 == "L":
            if not 1 <= step - start_5 <= 8:
                return False
            done_5 = True
        elif event == "Q5" and selected_5 == "R":
            if not 1 <= step - start_5 <= 10:
                return False
            done_5 = True
        elif event == "L6":
            if expected_stage != 6:
                return False
            selected_6 = "L"
            start_6 = step
            expected_stage += 1
        elif event == "R6":
            if expected_stage != 6:
                return False
            selected_6 = "R"
            start_6 = step
            expected_stage += 1
        elif event == "P6" and selected_6 == "L":
            if not 1 <= step - start_6 <= 8:
                return False
            done_6 = True
        elif event == "Q6" and selected_6 == "R":
            if not 1 <= step - start_6 <= 10:
                return False
            done_6 = True
    return success
