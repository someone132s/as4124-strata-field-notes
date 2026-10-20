from intervals import merge_intervals
assert merge_intervals([]) == []
assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]
assert merge_intervals([(1, 10), (2, 3)]) == [(1, 10)]
print("public tests passed")
