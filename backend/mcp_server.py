"""BHV Editor MCP Server - 通过 BhvEditor 后端 API 操作 BHV 文件

所有操作走 http://127.0.0.1:8000 的 BhvEditor API，
改动实时同步到网页界面（无需手动 reload）。

使用前先确保 BhvEditor 后端运行中：
  cd ~/Desktop/EXVS/BhvFile/BHVEditor/bhvfile-py
  python run.py

通过 MCP (Model Context Protocol) over stdio 暴露 BHV 编辑工具。
配合 Hermes Agent 或其他 MCP 客户端使用。

注册方式：在 ~/.hermes/config.yaml 中：
  mcp_servers:
    bhv-editor:
      command: "python3"
      args: ["/path/to/mcp_server.py"]
      timeout: 120
"""

import sys
import os
import json
import traceback
import urllib.request
import urllib.error
from pathlib import Path

# ============================================================
#  Add backend to path for model imports (local fallback)
# ============================================================
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPT_DIR)  # bhvfile-py/
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from backend.model.bhv_file import BHVFile, State, Transition, Condition, StructABB, StructB
from backend.model.binary_reader import BhvBinaryReader
from backend.model.binary_writer import BhvBinaryWriter


# ============================================================
#  BhvEditor Backend API Client
# ============================================================
BACKEND_URL = "http://127.0.0.1:8000"


def _api_get(path: str) -> dict:
    """GET request to backend API."""
    url = f"{BACKEND_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API GET {path} failed ({e.code}): {body[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot connect to BhvEditor backend at {BACKEND_URL}. "
            f"Make sure 'python run.py' is running. Error: {e.reason}"
        )


def _api_post(path: str, body: dict = None, files: list = None) -> dict:
    """POST request to backend API."""
    url = f"{BACKEND_URL}{path}"

    if files:
        # Multipart upload (for file upload endpoints)
        import uuid
        boundary = "----" + uuid.uuid4().hex
        data_bytes = b""
        for field_name, filename, content in files:
            data_bytes += f"--{boundary}\r\n".encode()
            data_bytes += f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode()
            data_bytes += b"Content-Type: application/octet-stream\r\n\r\n"
            data_bytes += content if isinstance(content, bytes) else content.encode()
            data_bytes += b"\r\n"
        data_bytes += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=data_bytes, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    else:
        data_bytes = json.dumps(body).encode("utf-8") if body else b"{}"
        req = urllib.request.Request(url, data=data_bytes, method="POST")
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API POST {path} failed ({e.code}): {body[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot connect to BhvEditor backend at {BACKEND_URL}. "
            f"Make sure 'python run.py' is running. Error: {e.reason}"
        )


def _api_put(path: str, body) -> dict:
    """PUT request to backend API."""
    url = f"{BACKEND_URL}{path}"
    data_bytes = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, method="PUT")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
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
    """DELETE request to backend API."""
    url = f"{BACKEND_URL}{path}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API DELETE {path} failed ({e.code}): {body[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot connect to BhvEditor backend at {BACKEND_URL}. "
            f"Make sure 'python run.py' is running. Error: {e.reason}"
        )


def _api_download(path: str) -> bytes:
    """Download binary data from backend."""
    url = f"{BACKEND_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API download {path} failed ({e.code})")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot connect to BhvEditor backend: {e.reason}")


# ============================================================
#  Session (local cache, synced with backend)
# ============================================================
class Session:
    """In-memory BHV editing session, synced with backend API."""
    def __init__(self):
        self.file: BHVFile | None = None
        self.filepath: str | None = None
        self.filename: str | None = None
        self._last_json: dict | None = None

    def ensure_loaded(self):
        if self.file is None:
            raise RuntimeError("No BHV file loaded. Use bhv_load first.")

    def sync_from_backend(self):
        """Pull current model from backend into local session."""
        resp = _api_get("/api/data")
        if resp.get("status") == "empty":
            self.file = None
            return
        data = resp["data"]
        self.file = BHVFile.from_dict(data)
        self._last_json = data

    def sync_to_backend(self):
        """Push local session model to backend."""
        data = self.file.to_dict()
        _api_put("/api/data", data)
        self._last_json = data

    def to_summary(self) -> dict:
        if self.file is None:
            return {"loaded": False}
        return {
            "loaded": True,
            "filename": self.filename or "untitled",
            "state_count": len(self.file.States),
            "structb_count": len(self.file.StructBs),
            "file_type": self.file.file_type.name,
        }

    def state_summaries(self) -> list[dict]:
        self.ensure_loaded()
        result = []
        for st in self.file.States:
            sb_name = ""
            if self.file.StructBs and st.StructBid < len(self.file.StructBs):
                sb = self.file.StructBs[st.StructBid]
                sb_name = f"A1:{sb.Unk00}"
            result.append({
                "index": st.Index,
                "transition_count": len(st.Transitions),
                "struct_bid": st.StructBid,
                "struct_b_info": sb_name,
                "left_hand_anim": st.LeftHandAnimationId,
                "weapon_anim": st.WeaponAnimationCallingId,
            })
        return result

    def get_transition_detail(self, si: int, ti: int) -> dict:
        self.ensure_loaded()
        st = self.file.States[si]
        tr = st.Transitions[ti]
        return {
            "state_index": si,
            "transition_index": ti,
            "target_state": tr.StateIndex,
            "unk10": tr.Unk10,
            "unk14": tr.Unk14,
            "unk18": tr.Unk18,
            "unk1c": tr.Unk1C,
            "condition_count": len(tr.Conditions),
            "conditions": [self._cond_summary(c, ci) for ci, c in enumerate(tr.Conditions)],
            "struct_abb": tr.StructAbb.to_dict(),
        }

    def _cond_summary(self, c: Condition, ci: int) -> dict:
        return {
            "index": ci,
            "id": c.Id,
            "unk01": c.Unk01,
            "unk02": c.Unk02,
            "unk03": c.Unk03,
            "expression": c.Expression,
            "data_hex": bytes(c.Data).hex(" ").upper(),
            "data_length": len(c.Data),
        }


_session = Session()


# ============================================================
#  Tool implementations (all operations go through backend API)
# ============================================================

def tool_bhv_load(arguments: dict) -> str:
    """Load a BHV file into the backend editor.

    Reads the file locally, then uploads to backend via API.
    Results instantly visible in BhvEditor web UI.

    Args:
        path: Absolute path to the .bhv or .json file
    """
    path = arguments["path"]
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return f"Error: file not found: {path}"

    ext = os.path.splitext(path)[1].lower()
    try:
        # Read file locally
        if ext == ".json":
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            file_obj = BHVFile.from_dict(data)
        else:
            reader = BhvBinaryReader(path)
            file_obj = reader.load()

        # Upload to backend via import-json
        json_str = json.dumps(file_obj.to_dict(), ensure_ascii=False)
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write(json_str)
            tmp_path = tmp.name
        _api_post("/api/file/import-json", files=[
            ("file", os.path.basename(path).replace(".bhv", ".json"), json_str.encode("utf-8"))
        ])
        os.unlink(tmp_path)

        # Update local session
        _session.file = file_obj
        _session.filepath = path
        _session.filename = os.path.basename(path)
        summary = _session.to_summary()
        return (f"Loaded {_session.filename} into BhvEditor: "
                f"{summary['state_count']} states, {summary['structb_count']} StructBs "
                f"— visible in web UI now")
    except Exception as e:
        traceback.print_exc()
        return f"Error loading file: {e}"


def tool_bhv_save(arguments: dict) -> str:
    """Save the current BHV from backend to a binary .bhv file.

    Args:
        path: Output path (optional, defaults to loaded file path)
    """
    _session.ensure_loaded()
    path = arguments.get("path", _session.filepath)
    if not path:
        return "Error: no output path specified and no loaded file path to overwrite"
    path = os.path.expanduser(path)

    try:
        # Download binary from backend's save endpoint
        binary_data = _api_download("/api/file/save")
        with open(path, "wb") as f:
            f.write(binary_data)
        _session.filepath = path
        _session.filename = os.path.basename(path)
        return f"Saved to {path} ({len(binary_data)} bytes) — downloaded from BhvEditor"
    except Exception as e:
        # Fallback: save locally
        try:
            writer = BhvBinaryWriter(_session.file)
            writer.save(path)
            return f"Saved locally to {path} ({os.path.getsize(path)} bytes)"
        except Exception as e2:
            return f"Error saving: {e} | fallback: {e2}"


def tool_bhv_export_json(arguments: dict) -> str:
    """Export the current BHV as a JSON file.

    Args:
        path: Output .json path (optional)
    """
    _session.ensure_loaded()
    path = arguments.get("path")
    if not path:
        base = _session.filepath or "output"
        path = base.replace(".bhv", ".json") if ".bhv" in str(base) else base + ".json"
    path = os.path.expanduser(path)
    try:
        data = _session.file.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return f"Exported JSON to {path}"
    except Exception as e:
        return f"Error exporting: {e}"


def tool_bhv_info(arguments: dict) -> str:
    """Get summary info about the currently loaded BHV file."""
    # Refresh from backend
    try:
        _session.sync_from_backend()
    except Exception:
        pass

    if _session.file is None:
        return json.dumps({"loaded": False}, indent=2)
    info = _session.to_summary()
    info["header"] = _session.file.Header.to_dict()
    return json.dumps(info, indent=2, ensure_ascii=False)


def tool_bhv_list_states(arguments: dict) -> str:
    """List all states with basic info."""
    # Refresh from backend
    try:
        _session.sync_from_backend()
    except Exception:
        pass
    _session.ensure_loaded()
    states = _session.state_summaries()
    return json.dumps(states, indent=2, ensure_ascii=False)


def tool_bhv_add_state(arguments: dict) -> str:
    """Add a new state to the BHV via backend API.

    Results instantly visible in BhvEditor web UI.

    Args:
        copy_from: (optional) State index to copy from
    """
    _session.ensure_loaded()
    copy_from = arguments.get("copy_from")

    if copy_from is not None:
        result = _api_post(f"/api/state/duplicate/{copy_from}")
    else:
        result = _api_post("/api/state")

    # Refresh local cache
    _session.sync_from_backend()
    return f"Added state — now {len(_session.file.States)} states total (visible in web UI)"


def tool_bhv_delete_state(arguments: dict) -> str:
    """Delete a state via backend API.

    Results instantly visible in BhvEditor web UI.

    Args:
        index: State index to delete
    """
    _session.ensure_loaded()
    idx = arguments["index"]
    if idx < 0 or idx >= len(_session.file.States):
        return f"Error: state {idx} out of range (0..{len(_session.file.States)-1})"

    _api_delete(f"/api/state/{idx}")
    _session.sync_from_backend()
    return f"Deleted state {idx}. Remaining: {len(_session.file.States)} (visible in web UI)"


def tool_bhv_update_state(arguments: dict) -> str:
    """Update fields of a state via backend API.

    Results instantly visible in BhvEditor web UI.

    Args:
        index: State index to modify
        fields: Dict of field names to new values
    """
    _session.ensure_loaded()
    idx = arguments["index"]
    fields = arguments.get("fields", {})
    if idx < 0 or idx >= len(_session.file.States):
        return f"Error: state {idx} out of range"

    # Get current state dict, merge fields, push back
    st_dict = _session.file.States[idx].to_dict()
    st_dict.update(fields)
    _api_put(f"/api/state/{idx}", st_dict)
    _session.sync_from_backend()
    return f"Updated state {idx} (visible in web UI)"


def tool_bhv_add_transition(arguments: dict) -> str:
    """Add a transition from one state to another via backend API.

    Results instantly visible in BhvEditor web UI.

    Args:
        state_index: Source state index
        target_state_index: Target state index
        unk10/unk14/unk18/unk1c: optional fields
        struct_abb: optional StructABB field overrides
    """
    _session.ensure_loaded()
    si = arguments["state_index"]
    target = arguments["target_state_index"]
    if si < 0 or si >= len(_session.file.States):
        return f"Error: state {si} out of range"

    body = {"StateIndex": target}
    for k in ["unk10", "unk14", "unk18", "unk1c"]:
        if k in arguments:
            body[k[0].upper() + k[1:]] = arguments[k]  # unk10 → Unk10

    result = _api_post(f"/api/state/{si}/transition", body)
    _session.sync_from_backend()
    ti = len(_session.file.States[si].Transitions) - 1
    return f"Added transition #{ti} on state {si} -> state {target} (visible in web UI)"


def tool_bhv_delete_transition(arguments: dict) -> str:
    """Delete a transition from a state via backend API.

    Args:
        state_index: Source state index
        transition_index: Transition index to delete
    """
    _session.ensure_loaded()
    si = arguments["state_index"]
    ti = arguments["transition_index"]
    _api_delete(f"/api/state/{si}/transition/{ti}")
    _session.sync_from_backend()
    return f"Deleted transition #{ti} from state {si} (visible in web UI)"


def tool_bhv_update_transition(arguments: dict) -> str:
    """Update transition fields via backend API.

    Args:
        state_index: Source state index
        transition_index: Transition index
        fields: Dict: StateIndex, Unk10, Unk14, Unk18, Unk1C
        struct_abb: optional StructABB field overrides
    """
    _session.ensure_loaded()
    si = arguments["state_index"]
    ti = arguments["transition_index"]
    fields = arguments.get("fields", {})

    # Get current transition, merge, push
    tr_dict = _session.file.States[si].Transitions[ti].to_dict()
    for k, v in fields.items():
        tr_dict[k] = v
    abb_updates = arguments.get("struct_abb", {})
    if abb_updates:
        tr_dict.setdefault("StructAbb", {}).update(abb_updates)

    _api_put(f"/api/state/{si}/transition/{ti}", tr_dict)
    _session.sync_from_backend()
    return f"Updated transition #{ti} on state {si} (visible in web UI)"


def tool_bhv_get_transition(arguments: dict) -> str:
    """Get detailed info about a specific transition including all conditions."""
    # Refresh from backend
    try:
        _session.sync_from_backend()
    except Exception:
        pass
    _session.ensure_loaded()
    si = arguments["state_index"]
    ti = arguments["transition_index"]
    detail = _session.get_transition_detail(si, ti)
    return json.dumps(detail, indent=2, ensure_ascii=False)


def tool_bhv_add_condition(arguments: dict) -> str:
    """Add a condition to a transition via backend API.

    Since the backend doesn't have a dedicated condition add endpoint,
    we modify the local model and push the full transition.

    Results instantly visible in BhvEditor web UI.

    Args:
        state_index / transition_index: position
        id/unk01/unk02/unk03/expression/data_hex/unk08/unk09/unk0A/unk0B/unk0C
    """
    _session.ensure_loaded()
    si = arguments["state_index"]
    ti = arguments["transition_index"]

    # Build condition
    c = Condition()
    c.Id = arguments.get("id", 0)
    c.Unk01 = arguments.get("unk01", 0)
    c.Unk02 = arguments.get("unk02", 0)
    c.Unk03 = arguments.get("unk03", 0)
    c.Expression = arguments.get("expression", "")
    c.Unk08 = arguments.get("unk08", 0)
    c.Unk09 = arguments.get("unk09", 0)
    c.Unk0A = arguments.get("unk0A", 0)
    c.Unk0B = arguments.get("unk0B", 0)
    c.Unk0C = arguments.get("unk0C", 0)
    dh = arguments.get("data_hex", "")
    if dh:
        c.Data = list(bytes.fromhex(dh.replace(" ", "")))
    c.DataLength = len(c.Data)

    # Add locally and push full transition
    _session.file.States[si].Transitions[ti].Conditions.append(c)
    tr_dict = _session.file.States[si].Transitions[ti].to_dict()
    _api_put(f"/api/state/{si}/transition/{ti}", tr_dict)
    _session.sync_from_backend()

    ci = len(_session.file.States[si].Transitions[ti].Conditions) - 1
    return f"Added condition #{ci} to transition #{ti} on state {si} (visible in web UI)"


def tool_bhv_update_condition(arguments: dict) -> str:
    """Update condition fields via backend API.

    Args:
        state_index / transition_index / condition_index: position
        fields: Dict of fields to update
        data_hex: (optional) Replace condition data bytes
    """
    _session.ensure_loaded()
    si = arguments["state_index"]
    ti = arguments["transition_index"]
    ci = arguments["condition_index"]
    fields = arguments.get("fields", {})
    dh = arguments.get("data_hex")

    c = _session.file.States[si].Transitions[ti].Conditions[ci]
    for k, v in fields.items():
        if hasattr(c, k):
            setattr(c, k, v)
    if dh:
        c.Data = list(bytes.fromhex(dh.replace(" ", "")))
        c.DataLength = len(c.Data)

    # Push full transition
    tr_dict = _session.file.States[si].Transitions[ti].to_dict()
    _api_put(f"/api/state/{si}/transition/{ti}", tr_dict)
    _session.sync_from_backend()
    return f"Updated condition #{ci} on transition #{ti}, state {si} (visible in web UI)"


def tool_bhv_delete_condition(arguments: dict) -> str:
    """Delete a condition from a transition via backend API.

    Args:
        state_index / transition_index / condition_index
    """
    _session.ensure_loaded()
    si = arguments["state_index"]
    ti = arguments["transition_index"]
    ci = arguments["condition_index"]

    tr = _session.file.States[si].Transitions[ti]
    if ci < 0 or ci >= len(tr.Conditions):
        return f"Error: condition {ci} out of range"
    tr.Conditions.pop(ci)

    # Push full transition
    tr_dict = tr.to_dict()
    _api_put(f"/api/state/{si}/transition/{ti}", tr_dict)
    _session.sync_from_backend()
    return f"Deleted condition #{ci} from transition #{ti}, state {si} (visible in web UI)"


def tool_bhv_chain(arguments: dict) -> str:
    """HIGH-LEVEL: Create a chain of states linked in sequence.

    Each new state has 1 transition to the next.
    Operates locally then pushes full model to backend.

    Results instantly visible in BhvEditor web UI.

    Args:
        start_index: Existing state index where chain starts
        count: Number of new states to add
        struct_bid: StructBid for all new states (optional)
        transition_fields: Dict of transition field overrides (optional)
        condition_template: Dict to auto-create condition (optional)
    """
    _session.ensure_loaded()
    start = arguments["start_index"]
    count = arguments.get("count", 1)
    struct_bid = arguments.get("struct_bid", 0)
    tr_fields = arguments.get("transition_fields", {})
    cond_tmpl = arguments.get("condition_template", None)

    if start < 0 or start >= len(_session.file.States):
        return f"Error: start_index {start} out of range"

    new_indices = []
    for i in range(count):
        ns = State()
        ns.StructBid = struct_bid
        ns.Index = len(_session.file.States)
        _session.file.States.append(ns)
        new_indices.append(ns.Index)

        if i == 0:
            prev_idx = start
        else:
            prev_idx = new_indices[i - 1]

        tr = Transition()
        tr.StateIndex = ns.Index
        tr.StructAbb.Unk01 = 1
        tr.StructAbb.Type = 1
        for k, v in tr_fields.items():
            if hasattr(tr, k):
                setattr(tr, k, v)
        _session.file.States[prev_idx].Transitions.append(tr)

        if cond_tmpl:
            c = Condition()
            c.Id = cond_tmpl.get("id", 0)
            dh = cond_tmpl.get("data_hex", "")
            if dh:
                c.Data = list(bytes.fromhex(dh.replace(" ", "")))
                c.DataLength = len(c.Data)
            tr.Conditions.append(c)

    # Reindex
    for i, st in enumerate(_session.file.States):
        st.Index = i

    # Push to backend
    _session.sync_to_backend()
    return (f"Created chain: state {start} -> {new_indices[0]} -> ... -> {new_indices[-1]} "
            f"({count} new states) — visible in web UI")


def tool_bhv_set_structb(arguments: dict) -> str:
    """Update or add a StructB entry via backend API.

    Args:
        index: StructB index (0-based)
        fields: Dict of StructB fields to set
        auto_extend: Auto-extend list if index out of range (default: true)
    """
    _session.ensure_loaded()
    idx = arguments["index"]
    fields = arguments.get("fields", {})
    auto_extend = arguments.get("auto_extend", True)

    if auto_extend and idx >= len(_session.file.StructBs):
        while len(_session.file.StructBs) <= idx:
            _session.file.StructBs.append(StructB())

    sb = _session.file.StructBs[idx]
    for k, v in fields.items():
        if hasattr(sb, k):
            setattr(sb, k, v)

    # Push all StructBs
    sb_list = [s.to_dict() for s in _session.file.StructBs]
    _api_put("/api/structb", sb_list)
    _session.sync_from_backend()
    return f"Updated StructB[{idx}] (visible in web UI)"


def tool_bhv_reindex(arguments: dict) -> str:
    """Reindex all states and update backend."""
    _session.ensure_loaded()
    for i, st in enumerate(_session.file.States):
        st.Index = i
    _session.sync_to_backend()
    return f"Reindexed {len(_session.file.States)} states (visible in web UI)"


# ============================================================
#  Tool registry
# ============================================================
TOOLS = [
    {
        "name": "bhv_load",
        "description": "Load a BHV file (.bhv or .json) into the BhvEditor backend. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to .bhv or .json file"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "bhv_save",
        "description": "Save the current BHV from backend to a binary .bhv file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Output path (optional, defaults to loaded file path)"}
            }
        }
    },
    {
        "name": "bhv_export_json",
        "description": "Export the current BHV as a JSON file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Output .json path (optional)"}
            }
        }
    },
    {
        "name": "bhv_info",
        "description": "Get summary info about the currently loaded BHV file",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "bhv_list_states",
        "description": "List all states with basic info (index, transitions count, struct info)",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "bhv_add_state",
        "description": "Add a new state. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "copy_from": {"type": "integer", "description": "State index to copy from (optional)"}
            }
        }
    },
    {
        "name": "bhv_delete_state",
        "description": "Delete a state by index. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "State index to delete"}
            },
            "required": ["index"]
        }
    },
    {
        "name": "bhv_update_state",
        "description": "Update fields on a state. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "State index to modify"},
                "fields": {"type": "object", "description": "Dict of field names to new values"}
            },
            "required": ["index", "fields"]
        }
    },
    {
        "name": "bhv_add_transition",
        "description": "Add a transition from one state to another. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state_index": {"type": "integer", "description": "Source state index"},
                "target_state_index": {"type": "integer", "description": "Target state index"},
                "unk10": {"type": "integer", "description": "Unk10 field (optional)"},
                "unk14": {"type": "integer", "description": "Unk14 field (optional)"},
                "unk18": {"type": "integer", "description": "Unk18 field (optional)"},
                "unk1c": {"type": "integer", "description": "Unk1C field (optional)"},
                "struct_abb": {"type": "object", "description": "Optional StructABB field overrides"}
            },
            "required": ["state_index", "target_state_index"]
        }
    },
    {
        "name": "bhv_delete_transition",
        "description": "Delete a transition from a state. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state_index": {"type": "integer", "description": "Source state index"},
                "transition_index": {"type": "integer", "description": "Transition index to delete"}
            },
            "required": ["state_index", "transition_index"]
        }
    },
    {
        "name": "bhv_update_transition",
        "description": "Update transition fields. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state_index": {"type": "integer", "description": "Source state index"},
                "transition_index": {"type": "integer", "description": "Transition index"},
                "fields": {"type": "object", "description": "Dict: StateIndex, Unk10, Unk14, Unk18, Unk1C"},
                "struct_abb": {"type": "object", "description": "Optional StructABB field overrides"}
            },
            "required": ["state_index", "transition_index"]
        }
    },
    {
        "name": "bhv_get_transition",
        "description": "Get detailed info about a transition including all conditions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state_index": {"type": "integer", "description": "Source state index"},
                "transition_index": {"type": "integer", "description": "Transition index"}
            },
            "required": ["state_index", "transition_index"]
        }
    },
    {
        "name": "bhv_add_condition",
        "description": "Add a condition to a transition. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state_index": {"type": "integer", "description": "Source state index"},
                "transition_index": {"type": "integer", "description": "Transition index"},
                "id": {"type": "integer", "description": "Condition ID (byte)"},
                "unk01": {"type": "integer", "description": "Unk01 (byte)"},
                "unk02": {"type": "integer", "description": "Unk02 (byte)"},
                "unk03": {"type": "integer", "description": "Unk03 (byte)"},
                "expression": {"type": "string", "description": "Debug label (optional)"},
                "data_hex": {"type": "string", "description": "Hex string e.g. '01 02 03'"},
                "unk08": {"type": "integer", "description": "Unk08 (byte)"},
                "unk09": {"type": "integer", "description": "Unk09 (byte)"},
                "unk0A": {"type": "integer", "description": "Unk0A (byte)"},
                "unk0B": {"type": "integer", "description": "Unk0B (byte)"},
                "unk0C": {"type": "integer", "description": "Unk0C (int)"}
            },
            "required": ["state_index", "transition_index"]
        }
    },
    {
        "name": "bhv_update_condition",
        "description": "Update condition fields and/or data. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state_index": {"type": "integer", "description": "Source state index"},
                "transition_index": {"type": "integer", "description": "Transition index"},
                "condition_index": {"type": "integer", "description": "Condition index"},
                "fields": {"type": "object", "description": "Dict of fields to update"},
                "data_hex": {"type": "string", "description": "Replace data bytes via hex string"}
            },
            "required": ["state_index", "transition_index", "condition_index"]
        }
    },
    {
        "name": "bhv_delete_condition",
        "description": "Delete a condition from a transition. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state_index": {"type": "integer", "description": "Source state index"},
                "transition_index": {"type": "integer", "description": "Transition index"},
                "condition_index": {"type": "integer", "description": "Condition index to delete"}
            },
            "required": ["state_index", "transition_index", "condition_index"]
        }
    },
    {
        "name": "bhv_chain",
        "description": "HIGH-LEVEL: Create a chain of states linked in sequence. Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_index": {"type": "integer", "description": "Existing state index where chain starts"},
                "count": {"type": "integer", "description": "Number of new states to add"},
                "struct_bid": {"type": "integer", "description": "StructBid for all new states"},
                "transition_fields": {"type": "object", "description": "Transition field overrides"},
                "condition_template": {"type": "object", "description": "Auto-create a condition on each transition"}
            },
            "required": ["start_index"]
        }
    },
    {
        "name": "bhv_set_structb",
        "description": "Update or add a StructB entry (animation parameters). Results visible in web UI instantly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "StructB index (0-based)"},
                "fields": {"type": "object", "description": "Dict of StructB fields to set"},
                "auto_extend": {"type": "boolean", "description": "Auto-extend list if index out of range (default: true)"}
            },
            "required": ["index", "fields"]
        }
    },
    {
        "name": "bhv_reindex",
        "description": "Reindex all states. Results visible in web UI instantly.",
        "inputSchema": {"type": "object", "properties": {}}
    },
]

_TOOL_MAP = {t["name"]: globals()[f"tool_{t['name']}"] for t in TOOLS}


# ============================================================
#  MCP Protocol handler
# ============================================================

def handle_request(request: dict) -> dict | None:
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "bhv-editor-mcp", "version": "1.0.0"}
            }
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        handler = _TOOL_MAP.get(tool_name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
            }
        try:
            result_text = handler(arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}]
                }
            }
        except Exception as e:
            traceback.print_exc()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)}
            }

    if method in ("notifications/initialized", "$/cancelRequest"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    }


def main():
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8")

    buffer = ""
    for line in sys.stdin:
        buffer += line
        try:
            while buffer.strip():
                request = json.loads(buffer.strip())
                buffer = ""
                response = handle_request(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except Exception as e:
            traceback.print_exc()
            sys.stdout.write(json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            }) + "\n")
            sys.stdout.flush()
            buffer = ""


if __name__ == "__main__":
    main()
