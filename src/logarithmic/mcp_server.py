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
from starlette.routing import Mount
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
        self._uvicorn_server: Any | None = None

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
                    name="get_log_last_lines",
                    description="Get the last N lines from a specific log. Useful for getting recent log entries without retrieving the entire log.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "log_id": {
                                "type": "string",
                                "description": "The ID of the log to retrieve",
                            },
                            "num_lines": {
                                "type": "integer",
                                "description": "Number of lines to retrieve (500, 1000, or 5000)",
                                "enum": [500, 1000, 5000],
                            },
                        },
                        "required": ["log_id", "num_lines"],
                    },
                ),
                Tool(
                    name="list_logs",
                    description="List all available logs with their IDs and descriptions",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="list_groups",
                    description="List all log groups with their metadata. Groups can contain multiple logs and may have a combined view.",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="get_group_content",
                    description="Get content from a log group. Prioritizes combined view if available, otherwise returns concatenated individual logs.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_name": {
                                "type": "string",
                                "description": "Name of the log group",
                            },
                            "num_lines": {
                                "type": "integer",
                                "description": "Optional: limit to last N lines (500, 1000, or 5000). If not specified, returns all content.",
                                "enum": [500, 1000, 5000],
                            },
                        },
                        "required": ["group_name"],
                    },
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

            elif name == "get_log_last_lines":
                log_id = arguments.get("log_id")
                num_lines = arguments.get("num_lines")

                if not log_id:
                    return [TextContent(type="text", text="Error: log_id is required")]
                if not num_lines:
                    return [
                        TextContent(type="text", text="Error: num_lines is required")
                    ]
                if num_lines not in [500, 1000, 5000]:
                    return [
                        TextContent(
                            type="text",
                            text="Error: num_lines must be 500, 1000, or 5000",
                        )
                    ]

                content = self._bridge.get_last_n_lines(log_id, num_lines)
                if content is None:
                    return [
                        TextContent(
                            type="text", text=f"Error: Log '{log_id}' not found"
                        )
                    ]

                log_info = self._bridge.get_log_info(log_id)
                desc = log_info["description"] if log_info else log_id
                return [
                    TextContent(
                        type="text",
                        text=f"Last {num_lines} lines from: {desc}\n\n{content}",
                    )
                ]

            elif name == "list_groups":
                groups = self._bridge.get_groups()
                if not groups:
                    return [
                        TextContent(
                            type="text", text="No log groups are currently defined."
                        )
                    ]

                result = "Available log groups:\n\n"
                for group_name, group_info in groups.items():
                    result += f"- Group: {group_name}\n"
                    result += f"  Logs: {group_info['log_count']}\n"
                    result += (
                        f"  Combined View: "
                        f"{'Yes' if group_info['has_combined_view'] else 'No'}\n"
                    )
                    result += f"  Log paths: {', '.join(group_info['logs'])}\n\n"

                return [TextContent(type="text", text=result)]

            elif name == "get_group_content":
                grp_name = arguments.get("group_name")
                line_limit = arguments.get("num_lines")  # Optional

                if not grp_name:
                    return [
                        TextContent(type="text", text="Error: group_name is required")
                    ]
                if line_limit and line_limit not in [500, 1000, 5000]:
                    return [
                        TextContent(
                            type="text",
                            text="Error: num_lines must be 500, 1000, or 5000",
                        )
                    ]

                group_content = self._bridge.get_group_content(grp_name, line_limit)
                if group_content is None:
                    return [
                        TextContent(
                            type="text",
                            text=f"Error: Group '{grp_name}' not found",
                        )
                    ]

                source = group_content["source"]
                grp_content = group_content["content"]
                log_count = group_content["log_count"]

                header = f"Group: {grp_name} ({log_count} logs)\n"
                header += f"Source: {source}\n"
                if line_limit:
                    header += f"Lines: last {line_limit}\n"
                header += "\n"

                return [TextContent(type="text", text=header + grp_content)]

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
        logger.info("Stopping MCP server...")

        # Gracefully shutdown uvicorn server
        if self._uvicorn_server and self._loop and self._loop.is_running():
            try:
                # Set should_exit flag to trigger graceful shutdown
                self._uvicorn_server.should_exit = True
                logger.debug("Signaled uvicorn server to exit")
            except Exception as e:
                logger.warning(f"Error signaling uvicorn shutdown: {e}")

        # Wait for thread to finish (uvicorn will exit gracefully)
        if self._thread:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("MCP server thread did not exit cleanly")

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
        from starlette.responses import Response

        # Create SSE transport
        sse = SseServerTransport("/messages")

        # Create SSE handler endpoint
        async def handle_sse(request):
            """Handle SSE connection requests."""
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self._server.run(
                    streams[0], streams[1], self._server.create_initialization_options()
                )
            # Return empty response to avoid NoneType error
            return Response()

        # Create Starlette app with SSE endpoint
        # Use Mount for the POST endpoint since handle_post_message is an ASGI app
        app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse, methods=["GET"]),
                Mount("/messages", app=sse.handle_post_message),
            ],
        )

        # Configure uvicorn
        config = uvicorn.Config(app, host=self._host, port=self._port, log_level="info")
        self._uvicorn_server = uvicorn.Server(config)

        logger.info(f"MCP server running on http://{self._host}:{self._port}")
        await self._uvicorn_server.serve()

    def is_running(self) -> bool:
        """Check if the server is running.

        Returns:
            True if running
        """
        return self._running
