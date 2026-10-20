"""Closed integer interval utilities."""


def merge_intervals(intervals):
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda item: item[0])
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start < last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return [tuple(item) for item in merged]
