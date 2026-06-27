"""BHVFile 完整数据模型 - 完全对应 C# BHVEditor 项目的数据结构"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from enum import IntEnum
import math


def _json_float(v):
    """Convert NaN/Inf to string representation for JSON compliance."""
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
    return v


class FileType(IntEnum):
    BASENORMAL = 0   # basenormal.bhv
    WEAPON = 1       # weapon.bhv
    W = 2            # w.bhv / generic


# ============================================================
# Header
# ============================================================
@dataclass
class Header:
    Version: int = 10          # short (2 bytes)
    Unk02: int = 0             # short (2 bytes)
    FileSize: int = 0          # int (4 bytes)
    UnknownHeader: bytes = field(default_factory=lambda: bytes(24))  # 6 ints from 0x08-0x1C
    StatesOffset: int = 0      # int
    StateCount: int = 0        # int
    OffsetB: int = 0           # int
    CountB: int = 0            # int
    OffsetC: int = 0           # int
    CountC: int = 0            # short
    SizeC: int = 0             # short
    OffsetD: int = 0           # int
    CountD: int = 0            # int
    MysteryBlock: bytes = field(default_factory=lambda: bytes())  # variable length

    def to_dict(self) -> dict:
        return {
            "Version": self.Version,
            "Unk02": self.Unk02,
            "FileSize": self.FileSize,
            "UnknownHeaderHex": self.UnknownHeader.hex(" ").upper(),
            "StatesOffset": self.StatesOffset,
            "StateCount": self.StateCount,
            "OffsetB": self.OffsetB,
            "CountB": self.CountB,
            "OffsetC": self.OffsetC,
            "CountC": self.CountC,
            "SizeC": self.SizeC,
            "OffsetD": self.OffsetD,
            "CountD": self.CountD,
            "MysteryBlockHex": self.MysteryBlock.hex(" ").upper(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Header":
        h = cls()
        h.Version = d.get("Version", 10)
        h.Unk02 = d.get("Unk02", 0)
        h.FileSize = d.get("FileSize", 0)
        uh = d.get("UnknownHeaderHex", "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00")
        h.UnknownHeader = bytes.fromhex(uh.replace(" ", ""))
        h.StatesOffset = d.get("StatesOffset", 0)
        h.StateCount = d.get("StateCount", 0)
        h.OffsetB = d.get("OffsetB", 0)
        h.CountB = d.get("CountB", 0)
        h.OffsetC = d.get("OffsetC", 0)
        h.CountC = d.get("CountC", 0)
        h.SizeC = d.get("SizeC", 0)
        h.OffsetD = d.get("OffsetD", 0)
        h.CountD = d.get("CountD", 0)
        mb = d.get("MysteryBlockHex", "")
        h.MysteryBlock = bytes.fromhex(mb.replace(" ", "")) if mb else bytes()
        return h


# ============================================================
# Condition
# ============================================================
@dataclass
class Condition:
    Id: int = 0                # byte
    Unk01: int = 0             # byte
    Unk02: int = 0             # byte
    Unk03: int = 0             # byte
    DataOffset: int = 0        # int (not serialized to JSON)
    Expression: str = ""       # string (used for debug / JSON interchange)
    DataLength: int = 0        # int (not serialized to JSON)
    Unk08: int = 0             # byte
    Unk09: int = 0             # byte
    Unk0A: int = 0             # byte
    Unk0B: int = 0             # byte
    Unk0C: int = 0             # int
    Data: List[int] = field(default_factory=list)  # byte list

    def to_dict(self) -> dict:
        return {
            "Id": self.Id,
            "Unk01": self.Unk01,
            "Unk02": self.Unk02,
            "Unk03": self.Unk03,
            "DataOffset": self.DataOffset,
            "Expression": self.Expression,
            "Unk08": self.Unk08,
            "Unk09": self.Unk09,
            "Unk0A": self.Unk0A,
            "Unk0B": self.Unk0B,
            "Unk0C": self.Unk0C,
            "Data": list(self.Data),  # list of int bytes
            "DataHex": bytes(self.Data).hex(" ").upper(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Condition":
        c = cls()
        c.Id = d.get("Id", 0)
        c.Unk01 = d.get("Unk01", 0)
        c.Unk02 = d.get("Unk02", 0)
        c.Unk03 = d.get("Unk03", 0)
        c.DataOffset = d.get("DataOffset", 0)
        c.Expression = d.get("Expression", "")
        c.Unk08 = d.get("Unk08", 0)
        c.Unk09 = d.get("Unk09", 0)
        c.Unk0A = d.get("Unk0A", 0)
        c.Unk0B = d.get("Unk0B", 0)
        c.Unk0C = d.get("Unk0C", 0)
        # DataHex takes priority since the frontend edits it directly
        dh = d.get("DataHex", "")
        if dh:
            c.Data = list(bytes.fromhex(dh.replace(" ", "")))
        else:
            raw_data = d.get("Data")
            if raw_data is not None:
                c.Data = list(raw_data)
            else:
                c.Data = []
        c.DataLength = len(c.Data)
        return c


# ============================================================
# StructABB
# ============================================================
@dataclass
class StructABB:
    Unk00: int = 0             # byte
    Unk01: int = 0             # byte
    Unk02: int = 0             # byte
    Unk03: int = 0             # byte
    Type: int = 0              # int
    BehaviorMatrixParam_f: float = 0.0  # float
    BehaviorMatrixParam_i: int = 0      # int
    Unk08_int: int = 0         # int
    Unk08_f: float = 0.0       # float
    Unk0C: int = 0             # int
    Unk10_int: int = 0         # int
    Unk14_int: int = 0         # int
    Unk18_int: int = 0         # int
    Unk1C_int: int = 0         # int
    Unk04: int = 0             # int
    Unk20_int: int = 0         # int

    def to_dict(self) -> dict:
        return {
            "Unk00": self.Unk00, "Unk01": self.Unk01, "Unk02": self.Unk02, "Unk03": self.Unk03,
            "Type": self.Type,
            "BehaviorMatrixParam_f": _json_float(self.BehaviorMatrixParam_f),
            "BehaviorMatrixParam_i": self.BehaviorMatrixParam_i,
            "Unk08_int": self.Unk08_int, "Unk08_f": _json_float(self.Unk08_f),
            "Unk0C": self.Unk0C,
            "Unk10_int": self.Unk10_int, "Unk14_int": self.Unk14_int,
            "Unk18_int": self.Unk18_int, "Unk1C_int": self.Unk1C_int,
            "Unk04": self.Unk04, "Unk20_int": self.Unk20_int,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StructABB":
        s = cls()
        for k in ["Unk00","Unk01","Unk02","Unk03","Type","BehaviorMatrixParam_f","BehaviorMatrixParam_i",
                  "Unk08_int","Unk08_f","Unk0C","Unk10_int","Unk14_int","Unk18_int","Unk1C_int","Unk04","Unk20_int"]:
            if k in d:
                setattr(s, k, d[k])
        return s


# ============================================================
# Transition
# ============================================================
@dataclass
class Transition:
    StateIndex: int = 0                          # int
    ConditionsOffset: int = 0                    # int (not serialized)
    ConditionCount: int = 0                      # int (not serialized)
    Offset0C: int = 0                            # int (not serialized)
    Unk10: int = 0                               # int
    Unk14: int = 0                               # int
    Unk18: int = 0                               # int
    Unk1C: int = 0                               # int
    Conditions: List[Condition] = field(default_factory=list)
    StructAbb: StructABB = field(default_factory=StructABB)

    def to_dict(self) -> dict:
        return {
            "StateIndex": self.StateIndex,
            "ConditionsOffset": self.ConditionsOffset,
            "ConditionCount": self.ConditionCount,
            "Offset0C": self.Offset0C,
            "Unk10": self.Unk10, "Unk14": self.Unk14, "Unk18": self.Unk18, "Unk1C": self.Unk1C,
            "Conditions": [c.to_dict() for c in self.Conditions],
            "StructAbb": self.StructAbb.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Transition":
        t = cls()
        t.StateIndex = d.get("StateIndex", 0)
        t.ConditionsOffset = d.get("ConditionsOffset", 0)
        t.Offset0C = d.get("Offset0C", 0)
        t.Unk10 = d.get("Unk10", 0); t.Unk14 = d.get("Unk14", 0)
        t.Unk18 = d.get("Unk18", 0); t.Unk1C = d.get("Unk1C", 0)
        t.Conditions = [Condition.from_dict(c) for c in d.get("Conditions", [])]
        t.ConditionCount = len(t.Conditions)
        if "StructAbb" in d:
            t.StructAbb = StructABB.from_dict(d["StructAbb"])
        return t


# ============================================================
# State
# ============================================================
@dataclass
class State:
    Index: int = 0                      # int
    Unk00: int = 0                      # short
    BoostParamSection: int = 0          # short
    Offset04: int = 0                   # int (not serialized)
    TransitionsOffset: int = 0          # int (not serialized)
    TransitionCount: int = 0            # int (not serialized)
    StructBid: int = 0                  # short
    Unk10: int = 0                      # short
    Unk14: int = 0                      # int
    Unk18_A: int = 0                    # short
    Unk18_B: int = 0                    # short
    Unk1C: int = 0                      # int
    Unk20: int = 0                      # int
    Unk24: float = 0.0                  # float
    Unk28: float = 0.0                  # float
    Unk2C: float = 0.0                  # float
    Unk30: int = 0                      # int
    Unk34: int = 0                      # int
    Unk38: int = 0                      # int
    Unk3C: int = 0                      # int
    Unk40: float = 0.0                  # float
    Unk44: float = 0.0                  # float (was Unk44_A/B/C split)
    Unk48: float = 0.0                 # float -1.0
    RootmotionStatus: float = 0.0       # float
    Unk50: int = 0                      # int
    BodyPartControlA: int = 0           # byte
    BodyPartControlB: int = 0           # byte
    BodyPartControlC: int = 0           # byte
    BodyPartControlD: int = 0           # byte
    Unk58: int = 0                      # int
    Unk5C: int = 0                      # int
    LeftHandAnimationId: int = 0        # int (derived from rawUnk60 >> 16)
    StructBsid2: int = 0                # short
    UnkBsControlId_A: int = 0           # byte
    UnkBsControlId_B: int = 0           # byte
    WeaponAnimationCallingId: int = 0   # int
    Unk6C: int = 0                      # int
    BladeHomingControl_A: int = 0       # byte (u8×4)
    BladeHomingControl_B: int = 0       # byte
    BladeHomingControl_C: int = 0       # byte
    BladeHomingControl_D: int = 0       # byte
    Unk74: int = 0                      # int (was float, data is small ints)
    Unk78: int = 0                      # int
    Unk7C: int = 0                      # int
    Unk80: int = 0                      # int (Version >= 10)
    WeaponRailAnimationCallingId: int = 0  # int (Version >= 10)
    Unk88: int = 0                      # int (Version >= 10)
    Unk8C: int = 0                      # int (Version >= 10)
    Unk90: int = 0                      # int (Version >= 10)
    Unk94: int = 0                      # int (Version >= 10)
    Unk98: int = 0                      # int (Version >= 10)
    Unk9C: int = 0                      # int (Version >= 10)
    Transitions: List[Transition] = field(default_factory=list)
    Data: List[int] = field(default_factory=list)  # byte list (raw state data)

    _json_omit = {"ConditionsOffset", "ConditionCount", "Offset0C", "DataOffset", "DataLength"}

    def to_dict(self) -> dict:
        return {
            "Index": self.Index,
            "Unk00": self.Unk00, "BoostParamSection": self.BoostParamSection,
            "StructBid": self.StructBid, "Unk10": self.Unk10, "Unk14": self.Unk14,
            "Unk18_A": self.Unk18_A, "Unk18_B": self.Unk18_B,
            "Unk1C": self.Unk1C, "Unk20": self.Unk20,
            "Unk24": _json_float(self.Unk24), "Unk28": _json_float(self.Unk28), "Unk2C": _json_float(self.Unk2C),
            "Unk30": self.Unk30, "Unk34": self.Unk34, "Unk38": self.Unk38, "Unk3C": self.Unk3C,
            "Unk40": _json_float(self.Unk40),
            "Unk44": _json_float(self.Unk44),
            "Unk48": _json_float(self.Unk48), "RootmotionStatus": _json_float(self.RootmotionStatus),
            "Unk50": self.Unk50,
            "BodyPartControlA": self.BodyPartControlA, "BodyPartControlB": self.BodyPartControlB,
            "BodyPartControlC": self.BodyPartControlC, "BodyPartControlD": self.BodyPartControlD,
            "Unk58": self.Unk58, "Unk5C": self.Unk5C,
            "LeftHandAnimationId": self.LeftHandAnimationId,
            "StructBsid2": self.StructBsid2,
            "UnkBsControlId_A": self.UnkBsControlId_A, "UnkBsControlId_B": self.UnkBsControlId_B,
            "WeaponAnimationCallingId": self.WeaponAnimationCallingId,
            "Unk6C": self.Unk6C,
            "BladeHomingControl_A": self.BladeHomingControl_A,
            "BladeHomingControl_B": self.BladeHomingControl_B,
            "BladeHomingControl_C": self.BladeHomingControl_C,
            "BladeHomingControl_D": self.BladeHomingControl_D,
            "Unk74": self.Unk74, "Unk78": self.Unk78, "Unk7C": self.Unk7C,
            "Unk80": self.Unk80, "WeaponRailAnimationCallingId": self.WeaponRailAnimationCallingId,
            "Unk88": self.Unk88, "Unk8C": self.Unk8C,
            "Unk90": self.Unk90, "Unk94": self.Unk94, "Unk98": self.Unk98, "Unk9C": self.Unk9C,
            "Offset04": self.Offset04, "TransitionsOffset": self.TransitionsOffset, "TransitionCount": self.TransitionCount,
            "Transitions": [t.to_dict() for t in self.Transitions],
            "DataHex": bytes(self.Data).hex(" ").upper(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "State":
        s = cls()
        for key in ["Index","Unk00","BoostParamSection","StructBid","Unk10","Unk14",
                    "Unk18_A","Unk18_B","Unk1C","Unk20",
                    "Unk30","Unk34","Unk38","Unk3C",
                    "Unk48",
                    "Unk50",
                    "BodyPartControlA","BodyPartControlB","BodyPartControlC","BodyPartControlD",
                    "Unk58","Unk5C","LeftHandAnimationId","StructBsid2",
                    "UnkBsControlId_A","UnkBsControlId_B",
                    "WeaponAnimationCallingId","Unk6C",
                    "BladeHomingControl_A","BladeHomingControl_B","BladeHomingControl_C","BladeHomingControl_D",
                    "Unk74","Unk78","Unk7C","Unk80","WeaponRailAnimationCallingId",
                    "Unk88","Unk8C","Unk90","Unk94","Unk98","Unk9C",
                    "Offset04","TransitionsOffset","TransitionCount"]:
            if key in d:
                setattr(s, key, d[key])
        # Float fields that may be "NaN"
        for fkey in ["Unk24","Unk28","Unk2C","Unk40","Unk44","Unk48","RootmotionStatus"]:
            if fkey in d:
                v = d[fkey]
                if isinstance(v, str) and v == "NaN":
                    setattr(s, fkey, float('nan'))
                else:
                    setattr(s, fkey, float(v))
        s.Transitions = [Transition.from_dict(t) for t in d.get("Transitions", [])]
        s.TransitionCount = len(s.Transitions)
        dh = d.get("DataHex", "")
        s.Data = list(bytes.fromhex(dh.replace(" ", ""))) if dh else []
        return s


# ============================================================
# StructB
# ============================================================
@dataclass
class StructB:
    Unk00: int = 0          # int (Anim1 ID)
    Unk04: int = 0          # short
    IsLooped: int = 0       # short
    Unk08: int = 0          # byte
    Unk09: int = 0          # byte
    Unk0A: int = 0          # byte
    Unk0B: int = 0          # byte
    Unk0C: int = 0          # int
    Unk10: int = 0          # int
    Unk14: int = 0          # int
    Unk18: int = 0          # int
    Unk1C: int = 0          # int
    Unk20: float = 0.0      # float
    FacingLocked: int = 0   # byte
    Unk25: int = 0          # byte
    Unk26: int = 0          # byte
    Unk27: int = 0          # byte
    Unk28: float = 0.0      # float
    Unk2C: float = 0.0      # float
    Unk30: int = 0          # int
    Unk34: int = 0          # int
    Unk38: int = 0          # int
    Unk3C: int = 0          # int
    Unk40: int = 0          # int (Version >= 6)
    Unk44: int = 0          # short (Version >= 6)
    Unk46: int = 0          # short (Version >= 6)
    Unk48: int = 0          # short (Version >= 6)
    Unk4A: int = 0          # short (Version >= 6)
    Unk4C: int = 0          # short (Version >= 6)
    Unk4E: int = 0          # short (Version >= 6)
    Unk50: int = 0          # short (Version >= 10)
    Unk52: int = 0          # short (Version >= 10)
    Unk54: int = 0          # short (Version >= 10)
    Unk56: int = 0          # short (Version >= 10)
    _dummy58: int = 0       # int, always 0 (Version >= 10)
    _dummy5C: int = 0       # int, always 0 (Version >= 10)

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            d[k] = _json_float(v) if isinstance(v, float) else v
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StructB":
        s = cls()
        for k, v in d.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s


# ============================================================
# StructD / StructDA
# ============================================================
@dataclass
class StructDA:
    Unk00: int = 0          # short
    Unk02: int = 0          # short
    Unk04: int = 0          # int
    Unk08: float = 0.0      # float (was int in Python, but C# reads as Single)
    Unk0C: float = 0.0      # float
    Unk10: float = 0.0      # float
    Unk14: float = 0.0      # float
    Unk18: float = 0.0      # float
    Unk1C: float = 0.0      # float
    Unk20: int = 0          # int (Version >= 10)
    Unk24: int = 0          # int (Version >= 10)
    Unk28: int = 0          # int (Version >= 10)
    Unk2C: int = 0          # int (Version >= 10)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = _json_float(v)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StructDA":
        s = cls()
        for k, v in d.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s


@dataclass
class StructD:
    Offset00: int = 0       # int
    Count04: int = 0        # int
    Unk08: int = 0          # int
    Unk0C: int = 0          # int
    Unk10: int = 0          # int
    Unk14: int = 0          # int
    Unk18: int = 0          # int
    Unk1C: int = 0          # int
    DABlocks: List[StructDA] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "Offset00": self.Offset00, "Count04": self.Count04,
            "Unk08": self.Unk08, "Unk0C": self.Unk0C,
            "Unk10": self.Unk10, "Unk14": self.Unk14,
            "Unk18": self.Unk18, "Unk1C": self.Unk1C,
            "DABlocks": [da.to_dict() for da in self.DABlocks],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StructD":
        s = cls()
        s.Offset00 = d.get("Offset00", 0); s.Count04 = d.get("Count04", 0)
        s.Unk08 = d.get("Unk08", 0); s.Unk0C = d.get("Unk0C", 0)
        s.Unk10 = d.get("Unk10", 0); s.Unk14 = d.get("Unk14", 0)
        s.Unk18 = d.get("Unk18", 0); s.Unk1C = d.get("Unk1C", 0)
        s.DABlocks = [StructDA.from_dict(da) for da in d.get("DABlocks", [])]
        return s


# ============================================================
# BHVFile - 顶层文件容器
# ============================================================
@dataclass
class BHVFile:
    Header: Header = field(default_factory=Header)
    States: List[State] = field(default_factory=list)
    StructBs: List[StructB] = field(default_factory=list)
    StructCs: List[List[int]] = field(default_factory=list)  # List of byte arrays
    StructDs: List[StructD] = field(default_factory=list)
    Strings: List[str] = field(default_factory=list)
    file_type: FileType = FileType.W

    def to_dict(self) -> dict:
        return {
            "Header": self.Header.to_dict(),
            "States": [s.to_dict() for s in self.States],
            "StructBs": [b.to_dict() for b in self.StructBs],
            "StructCs": [list(row) for row in self.StructCs],  # list of byte-int lists
            "StructDs": [d.to_dict() for d in self.StructDs],
            "Strings": self.Strings,
            "FileType": self.file_type.name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BHVFile":
        f = cls()
        if "Header" in d:
            f.Header = Header.from_dict(d["Header"])
        f.States = [State.from_dict(s) for s in d.get("States", [])]
        f.StructBs = [StructB.from_dict(b) for b in d.get("StructBs", [])]
        cs = d.get("StructCs", [])
        if cs and len(cs) > 0:
            if isinstance(cs[0], list) and len(cs[0]) > 0:
                if isinstance(cs[0][0], str):
                    # Hex strings → parse to int lists
                    f.StructCs = [[int(b, 16) for b in row.split()] for row in cs[0]] if isinstance(cs[0], list) and all(isinstance(x, str) for x in cs[0]) else []
                    if not f.StructCs:
                        f.StructCs = [[int(x) for x in row] for row in cs]  # direct int lists
                else:
                    f.StructCs = [[int(x) for x in row] for row in cs]
            else:
                f.StructCs = []
        else:
            f.StructCs = []
        f.StructDs = [StructD.from_dict(dd) for dd in d.get("StructDs", [])]
        f.Strings = d.get("Strings", []) or []
        ft = d.get("FileType", "W")
        f.file_type = FileType[ft] if ft in FileType.__members__ else FileType.W
        return f