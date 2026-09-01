def monitor(trajectory):
    state = "WAIT_A1"
    for event in trajectory:
        if state == "WAIT_A1" and event == "A1":
            state = "WAIT_A2"
        elif state == "WAIT_A2" and event == "A2":
            state = "SUCCESS"
    return state == "SUCCESS"
