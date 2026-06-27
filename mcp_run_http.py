"""BHV Editor MCP HTTP Server - Standalone

Run the MCP server in StreamableHTTP mode on port 8001.

Usage:
    python mcp_run_http.py
    
Then configure Hermes:
    mcp_servers:
      bhv-editor:
        url: "http://127.0.0.1:8001/mcp"
        timeout: 120
"""

import os
import sys

# Add backend to path
root = os.path.dirname(os.path.abspath(__file__))
backend = os.path.join(root, "backend")
sys.path.insert(0, backend)

from mcp_http_server import mcp

if __name__ == "__main__":
    print("=" * 60)
    print("  BHV Editor MCP HTTP Server")
    print("  StreamableHTTP mode on port 8001")
    print("  Config: url: http://127.0.0.1:8001/mcp")
    print("=" * 60)
    mcp.run(transport="streamable-http")
