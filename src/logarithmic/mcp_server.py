"""MCP Server - Exposes log data via Model Context Protocol."""

import asyncio
import logging
import threading
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Resource
from mcp.types import TextContent
from mcp.types import Tool
from starlette.applications import Starlette
from starlette.routing import Route

from logarithmic.mcp_bridge import McpBridge

logger = logging.getLogger(__name__)


class LogarithmicMcpServer:
    """MCP Server for Logarithmic log viewer.

    Exposes log content as resources that can be accessed by MCP clients
    (like Claude Desktop or other AI agents).
    """

    def __init__(
        self, bridge: McpBridge, host: str = "127.0.0.1", port: int = 3000
    ) -> None:
        """Initialize the MCP server.

        Args:
            bridge: MCP bridge for accessing log data
            host: Host address to bind to
            port: Port to bind to
        """
        self._bridge = bridge
        self._host = host
        self._port = port
        self._server = Server("logarithmic-logs")
        self._running = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup MCP server handlers."""

        @self._server.list_resources()
        async def list_resources() -> list[Resource]:
            """List all available log resources."""
            logs = self._bridge.get_all_logs()
            resources = []

            for _path_key, log_info in logs.items():
                resources.append(
                    Resource(
                        uri=f"log://{log_info['id']}",  # type: ignore[arg-type]
                        name=log_info["description"],
                        mimeType="text/plain",
                        description=f"Log content from {log_info['description']}",
                    )
                )

            logger.debug(f"Listed {len(resources)} log resources")
            return resources

        @self._server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a log resource by URI.

            Args:
                uri: Resource URI in format log://<log_id>

            Returns:
                Log content
            """
            if not uri.startswith("log://"):
                raise ValueError(f"Invalid URI format: {uri}")

            log_id = uri[6:]  # Remove "log://" prefix
            log_info = self._bridge.get_log_info(log_id)

            if log_info is None:
                raise ValueError(f"Log not found: {log_id}")

            content: str = str(log_info["content"])
            logger.debug(f"Read resource: {uri} ({len(content)} chars)")
            return content

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="get_log_content",
                    description="Get the current content of a specific log",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "log_id": {
                                "type": "string",
                                "description": "The ID of the log to retrieve",
                            }
                        },
                        "required": ["log_id"],
                    },
                ),
                Tool(
                    name="list_logs",
                    description="List all available logs with their IDs and descriptions",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="search_logs",
                    description="Search for a pattern across all logs",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "The pattern to search for",
                            },
                            "case_sensitive": {
                                "type": "boolean",
                                "description": "Whether the search should be case sensitive",
                                "default": False,
                            },
                        },
                        "required": ["pattern"],
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle tool calls.

            Args:
                name: Tool name
                arguments: Tool arguments

            Returns:
                List of text content results
            """
            if name == "get_log_content":
                log_id = arguments.get("log_id")
                if not log_id:
                    return [TextContent(type="text", text="Error: log_id is required")]

                log_info = self._bridge.get_log_info(log_id)
                if log_info is None:
                    return [
                        TextContent(
                            type="text", text=f"Error: Log '{log_id}' not found"
                        )
                    ]

                return [
                    TextContent(
                        type="text",
                        text=f"Log: {log_info['description']}\n\n{log_info['content']}",
                    )
                ]

            elif name == "list_logs":
                logs = self._bridge.get_all_logs()
                if not logs:
                    return [
                        TextContent(
                            type="text", text="No logs are currently being tracked."
                        )
                    ]

                result = "Available logs:\n\n"
                for _path_key, log_info in logs.items():
                    result += f"- ID: {log_info['id']}\n"
                    result += f"  Description: {log_info['description']}\n"
                    result += f"  Path: {log_info['path']}\n"
                    result += f"  Size: {len(log_info['content'])} characters\n\n"

                return [TextContent(type="text", text=result)]

            elif name == "search_logs":
                pattern = arguments.get("pattern")
                case_sensitive = arguments.get("case_sensitive", False)

                if not pattern:
                    return [TextContent(type="text", text="Error: pattern is required")]

                logs = self._bridge.get_all_logs()
                results = []

                for _path_key, log_info in logs.items():
                    content = log_info["content"]
                    search_content = content if case_sensitive else content.lower()
                    search_pattern = pattern if case_sensitive else pattern.lower()

                    if search_pattern in search_content:
                        # Find matching lines
                        lines = content.split("\n")
                        matching_lines = []
                        for i, line in enumerate(lines, 1):
                            check_line = line if case_sensitive else line.lower()
                            if search_pattern in check_line:
                                matching_lines.append(f"  Line {i}: {line}")

                        if matching_lines:
                            results.append(
                                f"Log: {log_info['description']}\n"
                                + f"Matches found: {len(matching_lines)}\n"
                                + "\n".join(
                                    matching_lines[:10]
                                )  # Limit to first 10 matches
                            )

                if not results:
                    return [
                        TextContent(
                            type="text", text=f"No matches found for pattern: {pattern}"
                        )
                    ]

                result_text = f"Search results for '{pattern}':\n\n" + "\n\n".join(
                    results
                )
                return [TextContent(type="text", text=result_text)]

            else:
                return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

    def start(self) -> None:
        """Start the MCP server in a background thread."""
        if self._running:
            logger.warning("MCP server is already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        logger.info(f"MCP server started on {self._host}:{self._port}")

    def stop(self) -> None:
        """Stop the MCP server."""
        if not self._running:
            return

        self._running = False

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=5.0)

        logger.info("MCP server stopped")

    def _run_server(self) -> None:
        """Run the MCP server (called in background thread)."""
        try:
            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            # Run the server
            logger.info(f"Starting MCP server on {self._host}:{self._port}")
            self._loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error(f"MCP server error: {e}", exc_info=True)
        finally:
            if self._loop:
                self._loop.close()
            self._loop = None

    async def _serve(self) -> None:
        """Serve the MCP server using SSE transport."""
        import uvicorn

        # Create SSE transport
        sse = SseServerTransport("/messages")

        # Create Starlette app with SSE endpoint
        app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=sse.handle_sse),  # type: ignore[attr-defined]
                Route("/messages", endpoint=sse.handle_post_message, methods=["POST"])
            ],
        )

        # Configure uvicorn
        config = uvicorn.Config(app, host=self._host, port=self._port, log_level="info")
        server = uvicorn.Server(config)

        # Connect MCP server to transport
        async with sse.connect_sse(self._server):  # type: ignore[call-arg,arg-type]
            logger.info(f"MCP server running on http://{self._host}:{self._port}")
            await server.serve()

    def is_running(self) -> bool:
        """Check if the server is running.

        Returns:
            True if running
        """
        return self._running
