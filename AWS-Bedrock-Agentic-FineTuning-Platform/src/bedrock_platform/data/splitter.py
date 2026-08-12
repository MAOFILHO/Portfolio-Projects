"""Train/validation splitting that does not leak between the two sides.

The original strategy — take the last `validation_split` fraction of the file — assumed
records were independent and in arbitrary order. Neither holds for these datasets. They
are grouped: the same underlying question appears several times with different
conversational prefixes ("Hi, ...", "Just checking, ..."), and those variants share one
gold answer verbatim.

A positional tail slice therefore cuts through the middle of groups. Measured on
`banking_assistant.jsonl`, the last 10% produced a "held-out" set of 3 distinct questions,
every one of them present in training under a different prefix, with all 23 gold answers
appearing verbatim in the training data. Evaluating on that set measures recall of
memorised answers, not generalisation.

Two dataset shapes need different handling, and they are distinguished by how much the
answer space repeats:

*Generative* (banking, it_helpdesk) — answers are long and near-unique per question.
    Whole answer-groups are assigned to one side, so no gold answer is ever seen during
    training and then scored at evaluation.

*Classification* (pharma) — answers are drawn from a small closed set, so repetition is
    inherent and grouping by answer would be wrong: with 16 distinct outputs, group
    assignment would hand entire classes to validation and leave them absent from
    training. These are stratified instead, so each label keeps its proportional share on
    both sides.

Both paths are deterministic and free of RNG state: ordering comes from a SHA-256 digest
of the group key, so the same input always produces the same split regardless of file
order, platform, or Python hash seed.
"""

import hashlib
import json
from collections import defaultdict

# Below this ratio of distinct answers to records, the dataset is treated as
# classification. Pharma sits at 16/210 = 0.08; banking at 0.13 by raw answer but its
# answers are long free text, so the ratio alone is not enough — see _looks_like_labels.
CLASSIFICATION_DISTINCT_RATIO = 0.5

# A closed label set is short. Free-text answers in these datasets run 12-35 words.
MAX_LABEL_WORDS = 8


class SplitError(ValueError):
    """Raised when a dataset cannot be split without emptying one side."""


def _answer_of(line: str) -> str:
    record = json.loads(line)
    blocks = record["messages"][-1]["content"]
    return "".join(b.get("text", "") for b in blocks).strip()


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _looks_like_labels(answers: set[str]) -> bool:
    """True when the answer space behaves like a closed label set rather than free text.

    Both conditions must hold: few distinct values *and* those values are short. A
    generative dataset with heavy paraphrase reuse can have a low distinct ratio while
    still emitting long prose, and must not be stratified as if it were classification.
    """
    if not answers:
        return False
    longest = max(len(a.split()) for a in answers)
    return longest <= MAX_LABEL_WORDS


def split_records(records: list[str], validation_split: float) -> tuple[list[str], list[str]]:
    """Splits raw JSONL lines into (train, validation).

    Deterministic: no RNG, and independent of the order of `records`.
    """
    if not 0.0 < validation_split < 1.0:
        raise SplitError(f"validation_split must be between 0 and 1, got {validation_split}")
    if len(records) < 2:
        raise SplitError(f"need at least 2 records to split, got {len(records)}")

    target = max(1, round(len(records) * validation_split))

    by_answer: dict[str, list[str]] = defaultdict(list)
    for line in records:
        by_answer[_answer_of(line)].append(line)

    distinct_ratio = len(by_answer) / len(records)
    stratify = distinct_ratio < CLASSIFICATION_DISTINCT_RATIO and _looks_like_labels(set(by_answer))

    if stratify:
        train, validation = _stratified(by_answer, validation_split)
    else:
        train, validation = _grouped(by_answer, target)

    if not train or not validation:
        raise SplitError(
            f"split left an empty side (train={len(train)}, validation={len(validation)}); "
            f"dataset has {len(records)} records across {len(by_answer)} answer groups"
        )
    return train, validation


def _stratified(
    by_answer: dict[str, list[str]], validation_split: float
) -> tuple[list[str], list[str]]:
    """Each label contributes its proportional share to validation, so every label
    remains represented in training."""
    train: list[str] = []
    validation: list[str] = []
    for answer in sorted(by_answer, key=_digest):
        group = sorted(by_answer[answer], key=_digest)
        n_val = round(len(group) * validation_split)
        # Never take a whole label into validation — that would delete it from training.
        n_val = min(n_val, len(group) - 1)
        validation.extend(group[:n_val])
        train.extend(group[n_val:])
    return train, validation


def _grouped(by_answer: dict[str, list[str]], target: int) -> tuple[list[str], list[str]]:
    """Whole answer-groups go to one side, so no gold answer spans the split.

    Validation fills until it reaches `target`, then everything else goes to training.
    Because groups are indivisible the final size can overshoot `target` by at most one
    group; that is the price of not leaking, and is preferable to hitting an exact ratio
    by cutting a group in half.
    """
    train: list[str] = []
    validation: list[str] = []
    for answer in sorted(by_answer, key=_digest):
        group = by_answer[answer]
        if len(validation) < target:
            validation.extend(group)
        else:
            train.extend(group)
    return train, validation
