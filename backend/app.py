"""BHV Editor - FastAPI Backend Server"""

import json
import os
import tempfile
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from model.bhv_file import BHVFile
from model.binary_reader import BhvBinaryReader
from model.binary_writer import BhvBinaryWriter

app = FastAPI(title="BHV Editor API")

# Allow CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage (simple: one file at a time)
current_file: Optional[BHVFile] = None
current_path: Optional[str] = None
debug_states: list = []


# ================================================================
#  File Operations
# ================================================================

@app.post("/api/file/open")
async def open_file(file: UploadFile = File(...)):
    """Open a .bhv binary file"""
    global current_file, current_path
    try:
        content = await file.read()
        # Write to temp file for the reader
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bhv") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        reader = BhvBinaryReader(tmp_path)
        current_file = reader.load()
        current_path = file.filename
        os.unlink(tmp_path)
        return {"status": "ok", "filename": file.filename, "data": current_file.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to open BHV file: {str(e)}")


@app.post("/api/file/import-json")
async def import_json(file: UploadFile = File(...)):
    """Import a JSON file as the current model"""
    global current_file, current_path
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8-sig"))
        current_file = BHVFile.from_dict(data)
        current_path = None
        return {"status": "ok", "data": current_file.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import JSON: {str(e)}")


@app.post("/api/file/load-debug-json")
async def load_debug_json(file: UploadFile = File(...)):
    """Load a debug JSON with state name info"""
    global debug_states
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8-sig"))
        debug_states = data.get("AllStates", [])
        return {"status": "ok", "count": len(debug_states), "states": debug_states}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load debug JSON: {str(e)}")


@app.post("/api/file/save")
async def save_file():
    """Save the current model to a .bhv binary file, returns it for download"""
    global current_file, current_path
    if current_file is None:
        raise HTTPException(status_code=400, detail="No file loaded")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bhv") as tmp:
            tmp_path = tmp.name
        writer = BhvBinaryWriter(current_file)
        writer.save(tmp_path)
        filename = current_path or "output.bhv"
        async def cleanup():
            os.unlink(tmp_path)
        return FileResponse(tmp_path, media_type="application/octet-stream",
                           filename=filename, background=cleanup)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


@app.post("/api/file/export-json")
async def export_json():
    """Export current model as JSON"""
    global current_file
    if current_file is None:
        raise HTTPException(status_code=400, detail="No file loaded")
    try:
        data = current_file.to_dict()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            tmp_path = tmp.name
        filename = (current_path or "output").replace(".bhv", ".json")
        async def cleanup():
            os.unlink(tmp_path)
        return FileResponse(tmp_path, media_type="application/json",
                           filename=filename, background=cleanup)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export JSON: {str(e)}")


# ================================================================
#  Data Query APIs
# ================================================================

@app.get("/api/data")
async def get_data():
    """Get the full current model"""
    global current_file
    if current_file is None:
        return {"status": "empty", "data": None}
    return {"status": "ok", "data": current_file.to_dict()}


@app.put("/api/data")
async def update_data(body: dict):
    """Update the full current model from JSON"""
    global current_file
    try:
        current_file = BHVFile.from_dict(body)
        return {"status": "ok"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Invalid data: {str(e)}")


@app.get("/api/debug")
async def get_debug():
    """Get loaded debug info"""
    global debug_states
    return {"states": debug_states}


@app.get("/api/debug/state-names")
async def get_debug_state_names():
    """Get mapping of state index -> name"""
    global debug_states
    names = {}
    for i, s in enumerate(debug_states):
        names[str(i)] = s.get("StateName", f"State{i}")
    return names


@app.get("/api/debug/transitions/{state_index}")
async def get_debug_transitions(state_index: int):
    """Get debug transitions for a state index"""
    global debug_states
    if state_index < 0 or state_index >= len(debug_states):
        return []
    state_info = debug_states[state_index]
    result = []
    for ns in state_info.get("NextStates", []):
        name = ns.get("NextStateName", "")
        # Parse target index
        digits = "".join(c for c in name if c.isdigit())
        target = int(digits) if digits else -1
        if target >= 0:
            result.append({
                "targetIndex": target,
                "conditions": ns.get("Conditions", [])
            })
    return result


# ================================================================
#  State CRUD
# ================================================================

@app.post("/api/state")
async def add_state():
    global current_file
    if current_file is None:
        raise HTTPException(status_code=400, detail="No file loaded")
    from model.bhv_file import State
    new_state = State()
    new_state.Index = len(current_file.States)
    current_file.States.append(new_state)
    return {"status": "ok", "data": new_state.to_dict()}


@app.put("/api/state/{index}")
async def update_state(index: int, body: dict):
    global current_file
    if current_file is None or index >= len(current_file.States):
        raise HTTPException(status_code=404, detail="State not found")
    from model.bhv_file import State
    current_file.States[index] = State.from_dict(body)
    return {"status": "ok"}


@app.delete("/api/state/{index}")
async def delete_state(index: int):
    global current_file
    if current_file is None or index >= len(current_file.States):
        raise HTTPException(status_code=404, detail="State not found")
    current_file.States.pop(index)
    # Reindex
    for i, st in enumerate(current_file.States):
        st.Index = i
    return {"status": "ok"}


@app.post("/api/state/duplicate/{index}")
async def duplicate_state(index: int):
    global current_file
    if current_file is None or index >= len(current_file.States):
        raise HTTPException(status_code=404, detail="State not found")
    from model.bhv_file import State
    import copy
    new_state = State.from_dict(current_file.States[index].to_dict())
    new_state.Index = len(current_file.States)
    current_file.States.append(new_state)
    return {"status": "ok", "data": new_state.to_dict()}


# ================================================================
#  Transition CRUD
# ================================================================

@app.post("/api/state/{state_index}/transition")
async def add_transition(state_index: int, body: dict):
    global current_file
    if current_file is None or state_index >= len(current_file.States):
        raise HTTPException(status_code=404, detail="State not found")
    from model.bhv_file import Transition, StructABB
    tr = Transition()
    tr.StateIndex = body.get("StateIndex", 0)
    tr.StructAbb = StructABB()
    tr.StructAbb.Unk01 = 1
    current_file.States[state_index].Transitions.append(tr)
    return {"status": "ok", "data": tr.to_dict()}


@app.delete("/api/state/{state_index}/transition/{transition_index}")
async def delete_transition(state_index: int, transition_index: int):
    global current_file
    st = current_file.States[state_index]
    st.Transitions.pop(transition_index)
    return {"status": "ok"}


@app.put("/api/state/{state_index}/transition/{transition_index}")
async def update_transition(state_index: int, transition_index: int, body: dict):
    global current_file
    from model.bhv_file import Transition
    st = current_file.States[state_index]
    st.Transitions[transition_index] = Transition.from_dict(body)
    return {"status": "ok"}


@app.post("/api/state/{state_index}/transitions/paste")
async def paste_transitions(state_index: int, body: dict):
    """Paste transitions from clipboard"""
    global current_file
    from model.bhv_file import Transition
    st = current_file.States[state_index]
    for tdata in body.get("transitions", []):
        st.Transitions.append(Transition.from_dict(tdata))
    return {"status": "ok"}


# ================================================================
#  StructB CRUD
# ================================================================

@app.put("/api/structb")
async def update_structb_list(body: list):
    global current_file
    from model.bhv_file import StructB
    current_file.StructBs = [StructB.from_dict(s) for s in body]
    return {"status": "ok"}


# ================================================================
#  StructC CRUD
# ================================================================

@app.put("/api/structc")
async def update_structc_list(body: list):
    global current_file
    current_file.StructCs = body  # List of lists of ints
    return {"status": "ok"}


# ================================================================
#  Strings CRUD
# ================================================================

@app.put("/api/strings")
async def update_strings(body: list):
    global current_file
    current_file.Strings = body
    return {"status": "ok"}


# ================================================================
#  Mystery Block
# ================================================================

@app.put("/api/mystery")
async def update_mystery(body: dict):
    global current_file
    hex_str = body.get("hex", "")
    try:
        current_file.Header.MysteryBlock = bytes.fromhex(hex_str.replace(" ", ""))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid hex string")


# ================================================================
#  Static Files (frontend)
# ================================================================

@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


# Mount static files LAST
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
