from fastmcp import FastMCP

from app.mcp.tools import register_tools

mcp = FastMCP("Workout Agent")
register_tools(mcp)


def create_mcp_http_app():
    return mcp.http_app(path="/")
