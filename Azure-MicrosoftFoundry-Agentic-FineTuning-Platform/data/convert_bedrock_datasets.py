"""Convert AWS Bedrock Converse-format JSONL datasets to the flat Azure OpenAI
fine-tuning format this project's schema (`app.schemas.training.TrainingRecord`)
expects.

Input row shape (Bedrock, `schemaVersion: bedrock-conversation-2024`):
    {"schemaVersion": "...",
     "system": [{"text": "..."}],
     "messages": [{"role": "user", "content": [{"text": "..."}]},
                  {"role": "assistant", "content": [{"text": "..."}]}]}

Output row shape (Azure OpenAI SFT):
    {"messages": [{"role": "system", "content": "..."},
                  {"role": "user", "content": "..."},
                  {"role": "assistant", "content": "..."}]}

Every source file here happens to be uniform — exactly one system text, and
exactly one user + one assistant message with one content block each — so the
conversion is a lossless 1:1 reshape, not a summarization. A row that doesn't
match that shape is skipped and reported rather than guessed at.

Usage:
    python data/convert_bedrock_datasets.py
Writes converted files to data/converted/<same-filename>, and validates each
one against the project's own Pydantic schema before declaring success.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
OUT_DIR = DATA_DIR / "converted"

SOURCE_FILES = [
    "support_ticket_triage.jsonl",
    "pharma_adverse_event_triage.jsonl",
    "patient_message_triage.jsonl",
    "ecommerce_product_copy.jsonl",
    "it_helpdesk_l1.jsonl",
    "banking_assistant.jsonl",
    "gardening_lessons.jsonl",
]


def _first_text(blocks: list[dict]) -> str | None:
    if len(blocks) != 1 or "text" not in blocks[0]:
        return None
    return blocks[0]["text"]


def convert_row(row: dict) -> dict | None:
    system_blocks = row.get("system", [])
    system_text = _first_text(system_blocks)
    if system_text is None:
        return None

    messages = row.get("messages", [])
    if len(messages) != 2:
        return None
    user_msg, assistant_msg = messages
    if user_msg.get("role") != "user" or assistant_msg.get("role") != "assistant":
        return None

    user_text = _first_text(user_msg.get("content", []))
    assistant_text = _first_text(assistant_msg.get("content", []))
    if user_text is None or assistant_text is None:
        return None

    return {
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
    }


def convert_file(name: str) -> tuple[int, int]:
    src = DATA_DIR / name
    dst = OUT_DIR / name
    converted = 0
    skipped = 0
    out_lines: list[str] = []

    for i, line in enumerate(src.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            print(f"  ! {name}:{i} invalid JSON, skipped")
            continue
        out = convert_row(row)
        if out is None:
            skipped += 1
            print(f"  ! {name}:{i} unexpected shape, skipped")
            continue
        out_lines.append(json.dumps(out, ensure_ascii=False))
        converted += 1

    dst.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return converted, skipped


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    sys.path.insert(0, str(DATA_DIR.parent / "src"))
    from app.schemas.training import validate_jsonl_text

    total_bad = 0
    print(f"Converting {len(SOURCE_FILES)} Bedrock-format datasets -> {OUT_DIR}\n")
    for name in SOURCE_FILES:
        converted, skipped = convert_file(name)
        dst = OUT_DIR / name
        report = validate_jsonl_text(dst.read_text(encoding="utf-8"), name)
        status = "OK" if report.is_valid else "SCHEMA INVALID"
        print(
            f"{name:36s} converted={converted:4d} skipped={skipped:2d} "
            f"-> {report.valid_rows}/{report.total_lines} pass schema [{status}]"
        )
        if not report.is_valid:
            total_bad += 1
            for err in report.errors[:5]:
                print(f"    line {err.line_number}: {err.error}")

    print()
    if total_bad:
        print(f"{total_bad} file(s) failed schema validation after conversion.")
        return 1
    print("All converted datasets pass TrainingRecord schema validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
