import json

import pytest

from bedrock_platform.data.splitter import SplitError, split_records


def record(question: str, answer: str) -> str:
    return json.dumps(
        {
            "schemaVersion": "bedrock-conversation-2024",
            "system": [{"text": "sys"}],
            "messages": [
                {"role": "user", "content": [{"text": question}]},
                {"role": "assistant", "content": [{"text": answer}]},
            ],
        }
    )


def answer_of(line: str) -> str:
    return json.loads(line)["messages"][-1]["content"][0]["text"]


def generative_dataset() -> list[str]:
    """Mirrors the real shape: each question appears under several conversational
    prefixes, and all its variants share one long gold answer."""
    prefixes = ["Hi, ", "Just checking, ", "Real quick — ", "Please help: ", "Hello — "]
    return [
        record(f"{p}how do I do task {i}?", f"Here are the steps for task {i}. " * 6)
        for i in range(20)
        for p in prefixes
    ]


def classification_dataset() -> list[str]:
    labels = ["Cardiac", "Skin", "Respiratory", "General"]
    return [
        record(f"case number {i} with distinct clinical detail", labels[i % len(labels)])
        for i in range(120)
    ]


def test_generative_split_leaks_no_gold_answer() -> None:
    train, validation = split_records(generative_dataset(), 0.10)

    train_answers = {answer_of(line) for line in train}
    leaked = [line for line in validation if answer_of(line) in train_answers]
    assert leaked == [], f"{len(leaked)} validation answers also appear in training"


def test_generative_split_holds_out_whole_question_groups() -> None:
    """The failure this splitter exists to prevent: variants of one question landing on
    both sides, so evaluation scores memorised answers."""
    train, validation = split_records(generative_dataset(), 0.10)

    def questions(lines: list[str]) -> set[str]:
        return {
            json.loads(line)["messages"][0]["content"][0]["text"].split("how do I ")[1]
            for line in lines
        }

    assert questions(train) & questions(validation) == set()


def test_classification_split_keeps_every_label_in_training() -> None:
    """Grouping by answer would be actively harmful here — it would move an entire label
    into validation and leave the model unable to ever predict it."""
    train, validation = split_records(classification_dataset(), 0.10)

    train_labels = {answer_of(line) for line in train}
    validation_labels = {answer_of(line) for line in validation}
    assert validation_labels <= train_labels
    assert len(train_labels) == 4


def test_split_is_deterministic_and_order_independent() -> None:
    records = generative_dataset()
    first = split_records(records, 0.10)
    second = split_records(list(reversed(records)), 0.10)
    assert sorted(first[0]) == sorted(second[0])
    assert sorted(first[1]) == sorted(second[1])


def test_split_covers_every_record_exactly_once() -> None:
    records = generative_dataset()
    train, validation = split_records(records, 0.10)
    assert sorted(train + validation) == sorted(records)


def test_neither_side_is_empty() -> None:
    train, validation = split_records(classification_dataset(), 0.10)
    assert train and validation


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.5])
def test_invalid_split_fraction_is_rejected(bad: float) -> None:
    with pytest.raises(SplitError):
        split_records(generative_dataset(), bad)


def test_dataset_too_small_is_rejected() -> None:
    with pytest.raises(SplitError):
        split_records([record("only one", "answer")], 0.10)
