STAGES = [
    ("L1", "P1", 8, "R1", "Q1", 10),
    ("L2", "P2", 8, "R2", "Q2", 10),
    ("L3", "P3", 8, "R3", "Q3", 10),
    ("L4", "P4", 8, "R4", "Q4", 10),
]

GLOBAL_AVOID = [
    "BAD",
]

BRANCH_POST_SEQUENCES = [
    ("L2", ("P2", "Z2")),
    ("L4", ("P4", "N1", "N2")),
]

BOUNDED_RESPONSES = [
    ("H", "REC", 3),
]

AVOID_UNTIL = [
    ("R3", "Y3", "Q3"),
]
