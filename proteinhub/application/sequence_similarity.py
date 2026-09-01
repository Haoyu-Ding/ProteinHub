from __future__ import annotations

from functools import lru_cache


def normalize_sequence(sequence: str) -> str:
    return "".join((sequence or "").upper().split())


def sequence_identity(sequence_a: str, sequence_b: str) -> tuple[float, int]:
    if not sequence_a or not sequence_b:
        return 0.0, max(len(sequence_a), len(sequence_b))
    if len(sequence_a) > len(sequence_b):
        sequence_a, sequence_b = sequence_b, sequence_a
    if len(sequence_b) > 500:
        return _longest_common_subsequence_identity(sequence_a, sequence_b)
    return _global_alignment_best_identity(sequence_a, sequence_b)


@lru_cache(maxsize=2048)
def _global_alignment_best_identity(sequence_a: str, sequence_b: str) -> tuple[float, int]:
    m = len(sequence_a)
    n = len(sequence_b)
    if m == 0 or n == 0:
        return 0.0, max(m, n)
    previous = [0] * (n + 1)
    for aa in sequence_a:
        current = [0]
        for j, bb in enumerate(sequence_b, start=1):
            match = previous[j - 1] + (1 if aa == bb else 0)
            delete = previous[j]
            insert = current[j - 1]
            current.append(max(match, delete, insert))
        previous = current
    matches = previous[-1]
    alignment_length = max(m, n)
    return (matches / alignment_length if alignment_length else 0.0, alignment_length)


def _longest_common_subsequence_identity(sequence_a: str, sequence_b: str) -> tuple[float, int]:
    m = len(sequence_a)
    n = len(sequence_b)
    if m == 0 or n == 0:
        return 0.0, max(m, n)
    if m > n:
        sequence_a, sequence_b = sequence_b, sequence_a
        m, n = n, m
    previous = [0] * (n + 1)
    for aa in sequence_a:
        current = [0]
        for j, bb in enumerate(sequence_b, start=1):
            if aa == bb:
                current.append(previous[j - 1] + 1)
            else:
                current.append(max(previous[j], current[-1]))
        previous = current
    matches = previous[-1]
    alignment_length = max(m, n)
    return (matches / alignment_length if alignment_length else 0.0, alignment_length)
