def monitor(trajectory):
    state = "WAIT_A1"
    start_C1 = None
    start_C2 = None
    for step, event in enumerate(trajectory):
        if state == "WAIT_A1" and event == "A1":
            start_C1 = step
            state = "WAIT_A2"
        elif state == "WAIT_A2" and event == "A2":
            start_C2 = step
            state = "WAIT_A3"
        elif state == "WAIT_A3" and event == "A3":
            state = "WAIT_A4"
        elif state == "WAIT_A4" and event == "A4":
            state = "WAIT_A5"
        elif state == "WAIT_A5" and event == "A5":
            state = "WAIT_A6"
        elif state == "WAIT_A6" and event == "A6":
            if start_C1 is None or step - start_C1 > 6:
                return False
            state = "WAIT_A7"
        elif state == "WAIT_A7" and event == "A7":
            if start_C2 is None or step - start_C2 > 8:
                return False
            state = "WAIT_A8"
        elif state == "WAIT_A8" and event == "A8":
            state = "WAIT_A9"
        elif state == "WAIT_A9" and event == "A9":
            state = "WAIT_A10"
        elif state == "WAIT_A10" and event == "A10":
            state = "SUCCESS"
    return state == "SUCCESS"
