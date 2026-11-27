"""Task packet v1 and its model-facing prompt format."""

import argparse
import json
from pathlib import Path
import shlex
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator


class FileRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    new: bool = False
    lines: tuple[PositiveInt, PositiveInt] | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, path: str) -> str:
        if not path or path.startswith("/") or "\\" in path or ":" in path or ".." in path.split("/"):
            raise ValueError("expected a relative path with / separators and no colon or .. segment")
        return path

    @model_validator(mode="after")
    def validate_lines(self):
        if self.lines and self.lines[0] > self.lines[1]:
            raise ValueError("line range start must be at or before its end")
        return self


class Packet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: Literal[1]
    goal: str = Field(min_length=1, max_length=400)
    kind: Literal["edit", "analyze"]
    requirements: list[Annotated[str, Field(max_length=200)]] = Field(default=[], max_length=5)
    files: list[FileRef] = Field(min_length=1, max_length=3)
    accept: Annotated[list[str], Field(min_length=1)] | None = None
    env: dict[str, str] = {}
    must_not_change: list[str] = Field(default=[], max_length=10)
    context: str = Field(default="", max_length=1500)


def task_files(packet: Packet) -> list[str]:
    return [file.path for file in packet.files]


def render(packet: Packet) -> str:
    lines = [f"Goal: {packet.goal}"]
    if packet.requirements:
        lines.append("Requirements:")
        lines.extend(f"- {item}" for item in packet.requirements)
    lines.append("Files:")
    for file in packet.files:
        entry = f"- {file.path}"
        if file.new:
            entry += " (new)"
        if file.lines:
            start, end = file.lines
            entry += f" lines {start}-{end}"
        lines.append(entry)
    if packet.context:
        lines.append(f"Context: {packet.context}")
    if packet.accept:
        lines.append(f"Accept: `{shlex.join(packet.accept)}`")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the task packet JSON schema.")
    parser.add_argument("--schema", required=True, action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    schema = json.dumps(Packet.model_json_schema(), indent=2) + "\n"
    if args.out:
        args.out.write_text(schema, encoding="utf-8", newline="\n")
    else:
        print(schema, end="")
