import asyncio
import json
from pathlib import Path
import unittest

from router import server

FIXTURE = Path(__file__).parent / "fixtures" / "tool_surface.json"


def tool_surface():
    return [{"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
            for tool in (item.to_mcp_tool() for item in asyncio.run(server.mcp.list_tools()))]


class ToolSurface(unittest.TestCase):
    def test_tool_surface_matches_fixture(self):
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
        actual = sorted(tool_surface(), key=lambda item: item["name"])
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(sorted(tool_surface(), key=lambda item: item["name"]), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    else:
        unittest.main()
