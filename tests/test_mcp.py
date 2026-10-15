import unittest
import sys
import tempfile
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from canvas_bridge.config import ROOT


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_json_account_works_over_real_stdio_without_echoing_key(self):
        with tempfile.TemporaryDirectory() as temp:
            account = Path(temp) / "canvas-account.local.json"
            account.write_text(json.dumps({"base_url": "https://canvas.example.edu", "api_key": "json-stdio-fixture", "timezone": "UTC"}))
            parameters = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=tempfile.gettempdir(),
                                              env={"CANVAS_CONFIG": str(account), "CANVAS_TOKEN": "", "CANVAS_BASE_URL": "https://canvas.example.edu"})
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self.assertEqual(len((await session.list_tools()).tools), 14)
                    result = await session.call_tool("get_assignment", {"course_id": "../1", "assignment_id": "2"})
                    self.assertTrue(result.isError)
                    self.assertIn("ID", result.content[0].text)
                    self.assertNotIn("json-stdio-fixture", result.content[0].text)

    async def test_real_stdio_initialization_and_tool_schemas(self):
        parameters = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=tempfile.gettempdir(),
                                          env={"CANVAS_TOKEN": "test-token", "CANVAS_BASE_URL": "https://canvas.example.edu"})
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.initialize()
                tools = (await session.list_tools()).tools
                names = {tool.name for tool in tools}
                self.assertEqual(result.serverInfo.name, "Canvas Agent Bridge")
                self.assertEqual(len(names), 14)
                self.assertTrue({"list_courses", "read_material", "get_assignment", "get_upcoming_work", "get_assignment_context"} <= names)
                schemas = {tool.name: tool.inputSchema for tool in tools}
                self.assertIn("offset", schemas["read_material"]["properties"])
                self.assertIn("start_date", schemas["list_announcements"]["properties"])
                self.assertFalse(any("submit" in name or "delete" in name for name in names))
                # Invalid inputs must fail before any network request.
                result = await session.call_tool("get_assignment", {"course_id": "../1", "assignment_id": "2"})
                self.assertTrue(result.isError)
                self.assertIn("ID", result.content[0].text)


if __name__ == "__main__":
    unittest.main()
