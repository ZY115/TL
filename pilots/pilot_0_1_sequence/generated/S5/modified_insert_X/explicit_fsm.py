def monitor(trajectory):
    state = "WAIT_A1"
    for event in trajectory:
        if state == "WAIT_A1" and event == "A1":
            state = "WAIT_A2"
        elif state == "WAIT_A2" and event == "A2":
            state = "WAIT_A3"
        elif state == "WAIT_A3" and event == "A3":
            state = "WAIT_X"
        elif state == "WAIT_X" and event == "X":
            state = "WAIT_A4"
        elif state == "WAIT_A4" and event == "A4":
            state = "WAIT_A5"
        elif state == "WAIT_A5" and event == "A5":
            state = "SUCCESS"
    return state == "SUCCESS"
