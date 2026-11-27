"""Replay task rw-011: parse_text_calls() recovers a tool call whose JSON string holds a literal newline (offline)."""
import json
import os
import sys

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)

TEXT = ('<tool_call>{"name": "write_note", "arguments": {"title": "Plan", '
        '"body": "line one\n'
        'line two"}}</tool_call>')


def main():
    import gateway.loop as loop

    calls = loop.parse_text_calls(TEXT, {"write_note"})
    if len(calls) != 1:
        print("FAIL: expected one recovered call, got %d" % len(calls))
        return 1
    call = calls[0]
    if call.function.name != "write_note":
        print("FAIL: wrong tool name %r" % call.function.name)
        return 1
    args = json.loads(call.function.arguments)
    if args.get("title") != "Plan" or args.get("body") != "line one\nline two":
        print("FAIL: arguments not recovered intact: %r" % (args,))
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
