import asyncio
import contextlib
import os
import tempfile
import unittest
from unittest import mock

os.environ["GATEWAY_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")

from gateway import mcp_client  # noqa: E402


class OpenRoleProfiles(unittest.TestCase):
    def test_list_profile_opens_one_session_per_profile(self):
        opened = []

        @contextlib.asynccontextmanager
        async def fake_open_profile(profile):
            opened.append(profile)
            yield object()

        async def run():
            with mock.patch.object(mcp_client, "open_profile", side_effect=fake_open_profile) as m:
                async with mcp_client.open_role(["build", "analyze"]) as router:
                    self.assertEqual(len(router._sessions), 2)
                return m

        m = asyncio.run(run())
        self.assertEqual(m.call_count, 2)
        self.assertEqual([c.args[0] for c in m.call_args_list], ["build", "analyze"])
        self.assertEqual(opened, ["build", "analyze"])

    def test_string_profile_still_opens_one_session(self):
        @contextlib.asynccontextmanager
        async def fake_open_profile(profile):
            yield object()

        async def run():
            with mock.patch.object(mcp_client, "open_profile", side_effect=fake_open_profile) as m:
                async with mcp_client.open_role("build") as router:
                    self.assertEqual(len(router._sessions), 1)
                return m

        m = asyncio.run(run())
        self.assertEqual([c.args[0] for c in m.call_args_list], ["build"])


if __name__ == "__main__":
    unittest.main()
