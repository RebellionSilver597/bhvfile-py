# BHV File Editor

A Python implementation of a BHV file editor with FastAPI backend, Web UI, and MCP (Model Context Protocol) server integration.

## Overview

BHV files are binary animation/data files used in game modding. This tool provides:

- **Binary Parser** — Read and parse `.bhv` files with full data structure support
- **Binary Writer** — Write modified BHV files back to disk
- **Web UI** — Browser-based visual editor
- **REST API** — FastAPI backend with 20+ endpoints
- **MCP Server** — AI agent integration via Model Context Protocol (stdio & HTTP)

## Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn python-multipart

# Start the server
python run.py

# Open in browser
# http://localhost:8000
```

## Project Structure

```
bhvfile-py/
├── run.py                     # One-click launcher (uvicorn + FastAPI)
├── mcp_run_http.py            # Standalone MCP HTTP server
├── test_read.py               # Diagnostic read script
├── output.bhv                 # Sample output file
├── backend/
│   ├── app.py                 # FastAPI backend (REST API)
│   ├── mcp_server.py          # MCP server (stdio mode)
│   ├── mcp_http_server.py     # MCP server (HTTP/StreamableHTTP mode)
│   └── model/
│       ├── bhv_file.py        # Data models (BHVFile, Header, State, etc.)
│       ├── binary_reader.py   # BHV binary file reader/parser
│       └── binary_writer.py   # BHV binary file writer
├── frontend/                  # Web frontend
└── backend/requirements.txt   # Python dependencies
```

## Architecture

### Data Model (`backend/model/bhv_file.py`)
Fully mirrors the C# BHVEditor data structures, including:
- `BHVFile` — Root container with Header, States, StructBs/Cs/Ds
- `Header` — 0x20 byte file header
- `State` — Animation states with Transitions and Conditions
- `Transition`, `Condition`, `StructABB`, `StructB`, `StructD`, `StructDA`

### Binary Parser (`backend/model/binary_reader.py`)
- Reads BHV files from offset 0x20
- Detects file type (basenormal, weapon, generic)
- Parses states, transitions, conditions, and all binary structures

### Binary Writer (`backend/model/binary_writer.py`)
- Two-phase: first calculates all offsets, then writes in C# compatible order
- Produces byte-identical output to the original C# implementation

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/file/open` | Open a BHV file |
| POST | `/api/file/save` | Save current file |
| POST | `/api/file/export-json` | Export as JSON |
| POST | `/api/file/import-json` | Import from JSON |
| GET | `/api/data` | Get current file data |
| PUT | `/api/data` | Update file data |
| POST | `/api/state` | Add new state |
| PUT/DELETE | `/api/state/{index}` | Update/delete state |
| POST | `/api/state/duplicate/{index}` | Duplicate state |
| POST/DELETE | `/api/state/{index}/transition` | Manage transitions |
| PUT | `/api/structb`, `/api/structc` | Update binary structures |
| GET | `/api/debug` | Debug information |

### MCP Integration

The project supports AI agent integration via Model Context Protocol:

- **stdio mode**: `backend/mcp_server.py` — for local AI agents
- **HTTP mode**: `mcp_run_http.py` — StreamableHTTP transport on port 8001

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Frontend**: HTML/CSS/JS (built-in)
- **MCP**: FastMCP library
- **File Format**: Custom BHV binary format

## License

MIT
