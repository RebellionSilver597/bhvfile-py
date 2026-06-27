# BHV File Editor for Armored Core 6

A Python-based editor for **Armored Core 6 (AC6) behavior BHV files** — the binary animation/state machine files that control enemy behavior, boss phases, and action sequences in the game.

This tool provides a **Web UI**, a **REST API**, and an **MCP (Model Context Protocol) server** for editing BHV files, fully compatible with the C# BHVEditor format.

---

## Table of Contents

- [What is a BHV File?](#what-is-a-bhv-file)
- [Quick Start](#quick-start)
- [Web UI (Browser)](#web-ui-browser)
- [REST API (curl / Python / any HTTP client)](#rest-api-curl--python--any-http-client)
- [MCP Server (AI Agent Integration)](#mcp-server-ai-agent-integration)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Tech Stack](#tech-stack)

---

## What is a BHV File?

BHV files are binary behavior files from **Armored Core 6 (AC6)**, typically located in the game's `chr/` directories (e.g., `c0001-behbnd-dcx/chr/c0001.bhv` or `basenormal.bhv`). They define:

- **State Machine** — Each state represents a behavior (idle, attack, stagger, death, etc.)
- **Transitions** — Rules for moving between states based on conditions
- **Conditions** — Triggers like HP thresholds, distance to player, timer, etc.
- **StructB / StructC / StructD** — Additional binary configuration data

Three file types:
| Type | File Name | Description |
|------|-----------|-------------|
| `basenormal.bhv` | `basenormal.bhv` | Base enemy/soldier behavior |
| `weapon.bhv` | `weapon.bhv` | Weapon behavior |
| `w.bhv` | `w.bhv` | Generic/world behavior |

---

## Quick Start

```bash
# 1. Install dependencies
pip install fastapi uvicorn python-multipart

# 2. Start the server
python run.py

# 3. Open in browser
#    http://localhost:8000
```

### Shut Down

Press `Ctrl+C` in the terminal where the server is running.

---

## Web UI (Browser)

Open **http://localhost:8000** in your browser to access the visual editor.

### Workflow

```
1. Click "Open BHV"  →  Select a .bhv file from your computer
2. Edit states, transitions, conditions in the visual interface
3. Click "Save BHV"  →  Download the modified .bhv file
```

### Web UI Features

- **State List** — View all states with their indices
- **Transition Editor** — Add/edit/delete transitions between states
- **Condition Editor** — Set conditions for each transition
- **Binary Preview** — View raw hex data of StructB/StructC/StructD
- **JSON Import/Export** — For batch editing or backup
- **Debug Overlay** — Load debug JSON to see state names

### Quick Actions

| Action | How |
|--------|-----|
| Open a BHV file | Click "Open BHV" button, select `.bhv` |
| Save as BHV | Click "Save BHV" — downloads modified file |
| Export as JSON | Click "Export JSON" — for inspection/backup |
| Import from JSON | Click "Import JSON" — restore from export |
| Add a state | Click "Add State" |
| Delete a state | Click the delete icon on the state card |
| Duplicate a state | Click the duplicate icon |
| Add a transition | Click "Add Transition" on a state |
| Delete a transition | Click the X on the transition card |

---

## REST API (curl / Python / any HTTP client)

The backend runs on `http://127.0.0.1:8000`. You can interact with it programmatically.

### File Operations

```bash
# Open a BHV file
curl -X POST http://127.0.0.1:8000/api/file/open \
  -F "file=@basenormal.bhv"

# Export current file as JSON
curl -X POST http://127.0.0.1:8000/api/file/export-json \
  -o output.json

# Import from JSON
curl -X POST http://127.0.0.1:8000/api/file/import-json \
  -F "file=@output.json"

# Save as BHV (download)
curl -X POST http://127.0.0.1:8000/api/file/save \
  -o modified.bhv
```

### Data Operations

```bash
# Get current file data (as JSON)
curl http://127.0.0.1:8000/api/data

# Update full data
curl -X PUT http://127.0.0.1:8000/api/data \
  -H "Content-Type: application/json" \
  -d @your_data.json
```

### State Management

```bash
# Add a new state
curl -X POST http://127.0.0.1:8000/api/state

# Update a state (replace index 2)
curl -X PUT http://127.0.0.1:8000/api/state/2 \
  -H "Content-Type: application/json" \
  -d '{"Index":2,"Unk04":0,...}'

# Delete state at index 2
curl -X DELETE http://127.0.0.1:8000/api/state/2

# Duplicate state at index 2
curl -X POST http://127.0.0.1:8000/api/state/duplicate/2
```

### Transition Management

```bash
# Add a transition to state 2 (targeting state 5)
curl -X POST http://127.0.0.1:8000/api/state/2/transition \
  -H "Content-Type: application/json" \
  -d '{"StateIndex":5}'

# Update transition 0 on state 2
curl -X PUT http://127.0.0.1:8000/api/state/2/transition/0 \
  -H "Content-Type: application/json" \
  -d '{"StateIndex":3,"StructAbb":{"Unk01":1}}'

# Delete transition 0 from state 2
curl -X DELETE http://127.0.0.1:8000/api/state/2/transition/0

# Paste multiple transitions from clipboard
curl -X POST http://127.0.0.1:8000/api/state/2/transitions/paste \
  -H "Content-Type: application/json" \
  -d '{"transitions":[{"StateIndex":3},{"StateIndex":5}]}'
```

### Binary Structure Operations

```bash
# Update StructB list
curl -X PUT http://127.0.0.1:8000/api/structb \
  -H "Content-Type: application/json" \
  -d '[{"Unk04":0,"Unk08":0,"Unk0C":0,"Unk10":0}]'

# Update StructC list
curl -X PUT http://127.0.0.1:8000/api/structc \
  -H "Content-Type: application/json" \
  -d '[[0,0,0,0]]'

# Update strings list
curl -X PUT http://127.0.0.1:8000/api/strings \
  -H "Content-Type: application/json" \
  -d '["idle","attack","stagger"]'

# Update MysteryBlock (hex)
curl -X PUT http://127.0.0.1:8000/api/mystery \
  -H "Content-Type: application/json" \
  -d '{"hex":"00 01 02 FF"}'
```

### Debug

```bash
# Load debug JSON (state name info)
curl -X POST http://127.0.0.1:8000/api/file/load-debug-json \
  -F "file=@debug_states.json"

# Get debug info
curl http://127.0.0.1:8000/api/debug

# Get state name mapping
curl http://127.0.0.1:8000/api/debug/state-names

# Get transitions for state 2 from debug data
curl http://127.0.0.1:8000/api/debug/transitions/2
```

### API Documentation

When the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## MCP Server (AI Agent Integration)

The project provides two MCP modes for AI agent integration via the Model Context Protocol.

### stdio Mode (for local AI agents)

```bash
python backend/mcp_server.py
```

Configure in your MCP client (e.g., `~/.hermes/config.yaml`):
```yaml
mcp_servers:
  bhv-editor:
    command: "python"
    args: ["D:/Materials/bhvfile-py/backend/mcp_server.py"]
    timeout: 120
```

### HTTP Mode (for remote AI agents)

```bash
python mcp_run_http.py
# Runs on http://127.0.0.1:8001/mcp
```

Configure:
```yaml
mcp_servers:
  bhv-editor:
    url: "http://127.0.0.1:8001/mcp"
    timeout: 120
```

### MCP Available Tools

| Tool | Description |
|------|-------------|
| `open_bhv` | Open a BHV file for editing |
| `save_bhv` | Save the current file as BHV |
| `export_json` | Export as JSON |
| `import_json` | Import from JSON |
| `get_data` | Get current file data |
| `update_data` | Update full data |
| `add_state` | Add a new state |
| `update_state` | Update a state by index |
| `delete_state` | Delete a state by index |
| `duplicate_state` | Duplicate a state |
| `add_transition` | Add a transition to a state |
| `update_transition` | Update a transition |
| `delete_transition` | Delete a transition |
| `paste_transitions` | Paste multiple transitions |
| `update_structb` | Update StructB list |
| `update_structc` | Update StructC list |
| `update_strings` | Update strings list |
| `update_mystery` | Update MysteryBlock |

---

## Project Structure

```
bhvfile-py/
├── run.py                     # One-click launcher (starts FastAPI on port 8000)
├── mcp_run_http.py            # Standalone MCP HTTP server (port 8001)
├── test_read.py               # Diagnostic script to test BHV file reading
├── output.bhv                 # Sample output file
├── .gitignore
├── README.md                  # This file (English)
├── README.zh-CN.md            # Chinese README
├── backend/
│   ├── app.py                 # FastAPI backend — all REST API endpoints
│   ├── mcp_server.py          # MCP server — stdio transport mode
│   ├── mcp_http_server.py     # MCP server — HTTP/StreamableHTTP transport
│   ├── requirements.txt       # Python dependencies
│   └── model/
│       ├── __init__.py
│       ├── bhv_file.py        # Data model: BHVFile, Header, State, Transition, Condition, etc.
│       ├── binary_reader.py   # Binary parser: reads .bhv from offset 0x20
│       └── binary_writer.py   # Binary writer: two-phase offset calculation + C#-compatible output
├── frontend/
│   └── index.html             # Single-page web UI
```

---

## Architecture

### Data Model (`backend/model/bhv_file.py`)
Fully mirrors the C# BHVEditor data structures used by the AC6 modding community:
- `BHVFile` — Root container: Header + States + StructBs/Cs/Ds + Strings + MysteryBlock
- `Header` — 32-byte file header (version, flags, offsets, counts)
- `State` — Animation behavior state with transitions and conditions
- `Transition` — Links from one state to another with conditions
- `Condition` — Trigger rules (HP, distance, timer, random, etc.)
- `StructABB` / `StructB` / `StructD` / `StructDA` — Additional binary structures

### Binary Parser (`backend/model/binary_reader.py`)
- Reads BHV files starting from offset `0x20`
- Auto-detects file type: `basenormal`, `weapon`, or generic `w`
- Parses all states, transitions, conditions, and binary substructures
- Produces a `BHVFile` object in memory

### Binary Writer (`backend/model/binary_writer.py`)
- **Phase 1**: Calculates all offsets starting from the end of the state table
- **Phase 2**: Writes in C#-compatible order (sequential writes, no seeking to old offsets)
- Output is byte-for-byte identical to the original C# BHVEditor

---

## API Reference

### File Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/file/open` | Upload and open a `.bhv` binary file |
| POST | `/api/file/save` | Save current file as `.bhv` (download) |
| POST | `/api/file/export-json` | Export current model as JSON |
| POST | `/api/file/import-json` | Import from a JSON file |
| POST | `/api/file/load-debug-json` | Load debug JSON with state names |

### Data Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/data` | Get the full current model data |
| PUT | `/api/data` | Replace the full model data |

### State Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/state` | Add a new empty state |
| PUT | `/api/state/{index}` | Update state at index |
| DELETE | `/api/state/{index}` | Delete state at index |
| POST | `/api/state/duplicate/{index}` | Duplicate state at index |

### Transition Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/state/{si}/transition` | Add transition to state `si` |
| PUT | `/api/state/{si}/transition/{ti}` | Update transition `ti` on state `si` |
| DELETE | `/api/state/{si}/transition/{ti}` | Delete transition `ti` from state `si` |
| POST | `/api/state/{si}/transitions/paste` | Paste multiple transitions from clipboard |

### Binary Data Endpoints

| Method | Path | Description |
|--------|------|-------------|
| PUT | `/api/structb` | Update the StructB list |
| PUT | `/api/structc` | Update the StructC list |
| PUT | `/api/strings` | Update the strings list |
| PUT | `/api/mystery` | Update the MysteryBlock (hex string) |

### Debug Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/debug` | Get loaded debug info |
| GET | `/api/debug/state-names` | Get state index → name mapping |
| GET | `/api/debug/transitions/{index}` | Get debug transitions for a state |

---

## Tech Stack

- **Backend**: Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/)
- **Frontend**: Vanilla HTML/CSS/JS (dark theme, single-page app)
- **MCP**: [FastMCP](https://github.com/jlowin/fastmcp) — Model Context Protocol
- **Binary Format**: Custom BHV — Armored Core 6 behavior state machine format

---

## License

MIT
