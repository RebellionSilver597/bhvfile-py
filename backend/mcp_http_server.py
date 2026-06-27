"""BHV Editor MCP HTTP Server (FastMCP + Starlette)

Provides all BHV editing tools via StreamableHTTP transport.
Mount this on the FastAPI backend for HTTP-mode MCP access.

Usage:
    from mcp_http_server import mcp_app
    app.mount("/mcp", mcp_app)
"""

import json
import os
import sys
import urllib.request
import urllib.error
import traceback
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

# ============================================================
#  Backend API Client (talks to FastAPI backend at port 8000)
# ============================================================
BACKEND_URL = "http://127.0.0.1:8000"


def _api_get(path: str) -> dict:
    url = f"{BACKEND_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot connect to BhvEditor backend at {BACKEND_URL}. "
            f"Make sure 'python run.py' is running. Error: {e.reason}"
        )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API GET {path} failed ({e.code}): {body[:200]}")


def _api_post(path: str, body: dict = None) -> dict:
    url = f"{BACKEND_URL}{path}"
    data_bytes = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API POST {path} failed ({e.code}): {body_err[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot connect to BhvEditor backend at {BACKEND_URL}. "
            f"Make sure 'python run.py' is running. Error: {e.reason}"
        )


def _api_put(path: str, body) -> dict:
    url = f"{BACKEND_URL}{path}"
    data_bytes = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, method="PUT")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API PUT {path} failed ({e.code}): {body_err[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot connect to BhvEditor backend at {BACKEND_URL}. "
            f"Make sure 'python run.py' is running. Error: {e.reason}"
        )


def _api_delete(path: str) -> dict:
    url = f"{BACKEND_URL}{path}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API DELETE {path} failed ({e.code}): {body_err[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot connect to BhvEditor backend at {BACKEND_URL}. "
            f"Make sure 'python run.py' is running. Error: {e.reason}"
        )


def _api_download(path: str) -> bytes:
    url = f"{BACKEND_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API download {path} failed ({e.code})")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot connect to BhvEditor backend: {e.reason}")


# ============================================================
#  Data helpers
# ============================================================

def _backend_data() -> dict:
    """Get current model data from backend."""
    resp = _api_get("/api/data")
    if resp.get("status") == "empty":
        return {}
    return resp.get("data", {})


def _state_summaries(data: dict) -> list[dict]:
    states = data.get("States", [])
    structbs = data.get("StructBs", [])
    result = []
    for st in states:
        sb_name = ""
        sb_id = st.get("StructBid", -1)
        if 0 <= sb_id < len(structbs):
            sb_name = f"A1:{structbs[sb_id].get('Unk00', -1)}"
        result.append({
            "index": st.get("Index", -1),
            "transition_count": len(st.get("Transitions", [])),
            "struct_bid": sb_id,
            "struct_b_info": sb_name,
            "left_hand_anim": st.get("LeftHandAnimationId", -1),
            "weapon_anim": st.get("WeaponAnimationCallingId", 0),
        })
    return result


# ============================================================
#  Create FastMCP server
# ============================================================

mcp = FastMCP("bhv-editor", instructions="BHV file editor for EXVS game data.",
               port=8001, log_level="INFO")


@mcp.tool(description="Load a BHV file (.bhv or .json) into the BhvEditor backend. "
                       "Results visible in web UI instantly.")
def bhv_load(path: str) -> str:
    """Load a BHV file into the backend editor.

    Args:
        path: Absolute path to the .bhv or .json file
    """
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return f"Error: file not found: {path}"

    try:
        with open(path, "rb") as f:
            file_content = f.read()

        import tempfile
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            upload_path = path
        else:
            upload_path = path

        # Upload via backend API
        import uuid
        boundary = "----" + uuid.uuid4().hex
        data_bytes = b""
        field_name = "file"
        filename = os.path.basename(path)
        data_bytes += f"--{boundary}\r\n".encode()
        data_bytes += f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode()
        if ext == ".json":
            data_bytes += b"Content-Type: application/json\r\n\r\n"
        else:
            data_bytes += b"Content-Type: application/octet-stream\r\n\r\n"
        data_bytes += file_content
        data_bytes += b"\r\n"
        data_bytes += f"--{boundary}--\r\n".encode()

        api_path = "/api/file/open" if ext != ".json" else "/api/file/import-json"
        url = f"{BACKEND_URL}{api_path}"
        req = urllib.request.Request(url, data=data_bytes, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        data = _backend_data()
        states = data.get("States", [])
        structbs = data.get("StructBs", [])
        return (f"Loaded {os.path.basename(path)} into BhvEditor: "
                f"{len(states)} states, {len(structbs)} StructBs "
                f"— visible in web UI now")
    except Exception as e:
        traceback.print_exc()
        return f"Error loading file: {e}"


@mcp.tool(description="Get summary info about the currently loaded BHV file.")
def bhv_info() -> str:
    """Get summary info about the currently loaded BHV file."""
    data = _backend_data()
    if not data:
        return json.dumps({"loaded": False}, indent=2)
    info = {
        "loaded": True,
        "filename": data.get("Header", {}).get("_filename", "unknown"),
        "state_count": len(data.get("States", [])),
        "structb_count": len(data.get("StructBs", [])),
        "file_type": data.get("FileType", "?"),
        "header": data.get("Header", {}),
    }
    return json.dumps(info, indent=2, ensure_ascii=False)


@mcp.tool(description="List all states with basic info (index, transitions count, struct info).")
def bhv_list_states() -> str:
    """List all states with basic info."""
    data = _backend_data()
    if not data:
        return "[]"
    states = _state_summaries(data)
    return json.dumps(states, indent=2, ensure_ascii=False)


@mcp.tool(description="Get detailed info about a transition including all conditions.")
def bhv_get_transition(state_index: int, transition_index: int) -> str:
    """Get detailed info about a transition."""
    data = _backend_data()
    states = data.get("States", [])
    if state_index < 0 or state_index >= len(states):
        return f"Error: state {state_index} out of range"
    st = states[state_index]
    trans = st.get("Transitions", [])
    if transition_index < 0 or transition_index >= len(trans):
        return f"Error: transition {transition_index} out of range"
    tr = trans[transition_index]
    return json.dumps(tr, indent=2, ensure_ascii=False)


@mcp.tool(description="Add a new state. Results visible in web UI instantly.")
def bhv_add_state(copy_from: int = None) -> str:
    """Add a new state.

    Args:
        copy_from: State index to copy from (optional)
    """
    try:
        if copy_from is not None:
            result = _api_post(f"/api/state/duplicate/{copy_from}")
        else:
            result = _api_post("/api/state")
        data = _backend_data()
        return f"Added state — now {len(data.get('States', []))} states total (visible in web UI)"
    except Exception as e:
        return f"Error adding state: {e}"


@mcp.tool(description="Delete a state by index. Results visible in web UI instantly.")
def bhv_delete_state(index: int) -> str:
    """Delete a state.

    Args:
        index: State index to delete
    """
    try:
        _api_delete(f"/api/state/{index}")
        data = _backend_data()
        return f"Deleted state {index}. Remaining: {len(data.get('States', []))} (visible in web UI)"
    except Exception as e:
        return f"Error deleting state: {e}"


@mcp.tool(description="Update fields on a state. Results visible in web UI instantly.")
def bhv_update_state(index: int, fields: dict) -> str:
    """Update fields on a state.

    Args:
        index: State index to modify
        fields: Dict of field names to new values
    """
    try:
        data = _backend_data()
        states = data.get("States", [])
        if index < 0 or index >= len(states):
            return f"Error: state {index} out of range"
        st_dict = states[index].copy()
        st_dict.update(fields)
        _api_put(f"/api/state/{index}", st_dict)
        return f"Updated state {index} (visible in web UI)"
    except Exception as e:
        return f"Error updating state: {e}"


@mcp.tool(description="Add a transition from one state to another. Results visible in web UI instantly.")
def bhv_add_transition(state_index: int, target_state_index: int,
                        unk10: int = None, unk14: int = None,
                        unk18: int = None, unk1c: int = None) -> str:
    """Add a transition.

    Args:
        state_index: Source state index
        target_state_index: Target state index
        unk10/unk14/unk18/unk1c: optional fields
    """
    try:
        body = {"StateIndex": target_state_index}
        if unk10 is not None: body["Unk10"] = unk10
        if unk14 is not None: body["Unk14"] = unk14
        if unk18 is not None: body["Unk18"] = unk18
        if unk1c is not None: body["Unk1C"] = unk1c
        result = _api_post(f"/api/state/{state_index}/transition", body)
        return f"Added transition on state {state_index} -> state {target_state_index} (visible in web UI)"
    except Exception as e:
        return f"Error adding transition: {e}"


@mcp.tool(description="Delete a transition from a state. Results visible in web UI instantly.")
def bhv_delete_transition(state_index: int, transition_index: int) -> str:
    """Delete a transition.

    Args:
        state_index: Source state index
        transition_index: Transition index to delete
    """
    try:
        _api_delete(f"/api/state/{state_index}/transition/{transition_index}")
        return f"Deleted transition #{transition_index} from state {state_index} (visible in web UI)"
    except Exception as e:
        return f"Error deleting transition: {e}"


@mcp.tool(description="Update transition fields. Results visible in web UI instantly.")
def bhv_update_transition(state_index: int, transition_index: int,
                           fields: dict = None) -> str:
    """Update transition fields.

    Args:
        state_index: Source state index
        transition_index: Transition index
        fields: Dict: StateIndex, Unk10, Unk14, Unk18, Unk1C
    """
    try:
        data = _backend_data()
        st = data["States"][state_index]
        tr = st["Transitions"][transition_index]
        tr.update(fields or {})
        _api_put(f"/api/state/{state_index}/transition/{transition_index}", tr)
        return f"Updated transition #{transition_index} on state {state_index} (visible in web UI)"
    except Exception as e:
        return f"Error updating transition: {e}"


@mcp.tool(description="Update or add a StructB entry (animation parameters). Results visible in web UI instantly.")
def bhv_set_structb(index: int, fields: dict) -> str:
    """Update or add a StructB entry.

    Args:
        index: StructB index (0-based)
        fields: Dict of StructB fields to set
    """
    try:
        data = _backend_data()
        structbs = data.get("StructBs", [])
        from backend.model.bhv_file import StructB

        # Extend list if needed
        while index >= len(structbs):
            structbs.append(StructB().to_dict())

        entry = structbs[index].copy()
        entry.update(fields)

        # Update the structbs list on the backend
        structbs[index] = entry
        _api_put("/api/structb", structbs)
        return f"Updated StructB[{index}] with {list(fields.keys())} (visible in web UI)"
    except Exception as e:
        return f"Error updating StructB: {e}"


@mcp.tool(description="HIGH-LEVEL: Create a chain of states linked in sequence. Results visible in web UI instantly.")
def bhv_chain(start_index: int, count: int, struct_bid: int = 0) -> str:
    """Create a chain of states linked in sequence.

    Args:
        start_index: Existing state index where chain starts
        count: Number of new states to add
        struct_bid: StructBid for all new states
    """
    try:
        data = _backend_data()
        states = data.get("States", [])

        if start_index < 0 or start_index >= len(states):
            return f"Error: start state {start_index} out of range"
        if count < 1:
            return "Error: count must be at least 1"

        created_indices = []
        prev_idx = start_index

        for i in range(count):
            # Add a new state
            _api_post("/api/state")
            data = _backend_data()
            new_idx = len(data["States"]) - 1

            # Add transition from previous to new
            _api_post(f"/api/state/{prev_idx}/transition", {"StateIndex": new_idx})

            # Update StructBid
            st_dict = data["States"][new_idx].copy()
            st_dict["StructBid"] = struct_bid
            _api_put(f"/api/state/{new_idx}", st_dict)

            created_indices.append(new_idx)
            prev_idx = new_idx

        return (f"Created chain: state {start_index} -> {' -> '.join(map(str, created_indices))} "
                f"({count} new states) — visible in web UI")
    except Exception as e:
        return f"Error creating chain: {e}"


@mcp.tool(description="Export the current BHV as a JSON file.")
def bhv_export_json(path: str = None) -> str:
    """Export the current BHV as a JSON file.

    Args:
        path: Output .json path (optional)
    """
    data = _backend_data()
    if not data:
        return "Error: no file loaded"
    if not path:
        path = os.path.expanduser("~/Desktop/output.json")
    path = os.path.expanduser(path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return f"Exported JSON to {path}"
    except Exception as e:
        return f"Error exporting: {e}"


@mcp.tool(description="Save the current BHV from backend to a binary .bhv file.")
def bhv_save(path: str = None) -> str:
    """Save the current BHV to a binary .bhv file.

    Args:
        path: Output path (optional, defaults to loaded file path)
    """
    try:
        binary_data = _api_download("/api/file/save")
        if not path:
            path = os.path.expanduser("~/Desktop/output.bhv")
        path = os.path.expanduser(path)
        with open(path, "wb") as f:
            f.write(binary_data)
        return f"Saved to {path} ({len(binary_data)} bytes)"
    except Exception as e:
        return f"Error saving: {e}"


@mcp.tool(description="Reindex all states. Results visible in web UI instantly.")
def bhv_reindex() -> str:
    """Reindex all states (sequential 0..N-1)."""
    try:
        data = _backend_data()
        states = data.get("States", [])
        for i, st in enumerate(states):
            st["Index"] = i
        _api_put("/api/data", data)
        return f"Reindexed {len(states)} states (visible in web UI)"
    except Exception as e:
        return f"Error reindexing: {e}"


# ============================================================
#  Expose the Starlette ASGI app for mounting
# ============================================================
mcp_app = mcp.streamable_http_app()
