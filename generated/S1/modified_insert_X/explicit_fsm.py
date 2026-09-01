def monitor(trajectory):
    state = "WAIT_A1"
    for event in trajectory:
        if state == "WAIT_A1" and event == "A1":
            state = "WAIT_X"
        elif state == "WAIT_X" and event == "X":
            state = "SUCCESS"
    return state == "SUCCESS"
