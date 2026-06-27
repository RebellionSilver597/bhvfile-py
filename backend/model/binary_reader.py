"""BHV 二进制文件解析器 - 完全对应 C# BHVFile.Load / Parse 逻辑"""

import struct
import os
from typing import BinaryIO
from .bhv_file import (
    BHVFile, Header, State, Transition, Condition, StructABB,
    StructB, StructD, StructDA, FileType
)

DATA_START = 0x20


class BhvBinaryReader:
    """读取 .bhv 二进制文件"""

    def __init__(self, path: str):
        self.path = path
        self.filename = os.path.basename(path)

    def load(self) -> BHVFile:
        with open(self.path, "rb") as f:
            return self._parse(f)

    def _parse(self, br: BinaryIO) -> BHVFile:
        file = BHVFile()
        file.file_type = self._detect_file_type(self.filename)

        # ---------- Header (0x00-0x1F) ----------
        h = file.Header
        h.Version = struct.unpack("<h", br.read(2))[0]
        h.Unk02 = struct.unpack("<h", br.read(2))[0]
        h.FileSize = struct.unpack("<i", br.read(4))[0]
        h.UnknownHeader = br.read(24)  # 6 ints 0x08-0x1C
        h.StatesOffset = struct.unpack("<i", br.read(4))[0]
        h.StateCount = struct.unpack("<i", br.read(4))[0]
        h.OffsetB = struct.unpack("<i", br.read(4))[0]
        h.CountB = struct.unpack("<i", br.read(4))[0]
        h.OffsetC = struct.unpack("<i", br.read(4))[0]
        h.CountC = struct.unpack("<h", br.read(2))[0]
        h.SizeC = struct.unpack("<h", br.read(2))[0]
        h.OffsetD = struct.unpack("<i", br.read(4))[0]
        h.CountD = struct.unpack("<i", br.read(4))[0]

        # ---------- Mystery Block ----------
        pos_after_header = br.tell()
        expected_states_abs = DATA_START + h.StatesOffset
        mystery_size = int(expected_states_abs - pos_after_header)
        if mystery_size < 0:
            raise ValueError(
                f"StatesOffset < current pos: 0x{h.StatesOffset:X} < 0x{pos_after_header:X}"
            )
        h.MysteryBlock = br.read(mystery_size) if mystery_size > 0 else b""

        # Refine file type by mystery block size
        if mystery_size >= 0xE0:
            file.file_type = FileType.BASENORMAL
        elif mystery_size >= 0x40:
            file.file_type = FileType.W
        else:
            file.file_type = FileType.WEAPON

        # ---------- States ----------
        self._read_states(br, file, h)

        # ---------- StructB ----------
        self._read_struct_bs(br, file, h)

        # ---------- StructC ----------
        self._read_struct_cs(br, file, h)

        # ---------- StructD ----------
        self._read_struct_ds(br, file, h)

        # ---------- Transitions ----------
        self._read_transitions(br, file, h)

        # ---------- State Data ----------
        self._read_state_data(br, file, h)

        # ---------- Strings (basenormal only) ----------
        if file.file_type == FileType.BASENORMAL:
            self._read_strings(br, file, h)

        return file

    # ================================================================
    #  Helpers
    # ================================================================
    @staticmethod
    def _detect_file_type(filename: str) -> FileType:
        name_lower = filename.lower()
        if name_lower == "basenormal.bhv":
            return FileType.BASENORMAL
        elif name_lower == "weapon.bhv":
            return FileType.WEAPON
        else:
            return FileType.W

    def _seek(self, br: BinaryIO, offset: int):
        br.seek(DATA_START + offset)

    # ================================================================
    #  State reader
    # ================================================================
    def _read_states(self, br: BinaryIO, file: BHVFile, h: Header):
        if h.StateCount <= 0:
            return
        state_entry_size = 0xA0 if h.Version >= 10 else 0x80
        self._seek(br, h.StatesOffset)

        for i in range(h.StateCount):
            base = br.tell()
            st = State()
            st.Index = i
            st.Unk00 = struct.unpack("<h", br.read(2))[0]
            st.BoostParamSection = struct.unpack("<h", br.read(2))[0]
            st.Offset04 = struct.unpack("<i", br.read(4))[0]
            st.TransitionsOffset = struct.unpack("<i", br.read(4))[0]
            st.TransitionCount = struct.unpack("<i", br.read(4))[0]
            st.StructBid = struct.unpack("<h", br.read(2))[0]
            st.Unk10 = struct.unpack("<h", br.read(2))[0]
            st.Unk14 = struct.unpack("<i", br.read(4))[0]
            st.Unk18_A = struct.unpack("<h", br.read(2))[0]
            st.Unk18_B = struct.unpack("<h", br.read(2))[0]
            st.Unk1C = struct.unpack("<i", br.read(4))[0]
            st.Unk20 = struct.unpack("<i", br.read(4))[0]
            st.Unk24 = struct.unpack("<f", br.read(4))[0]
            st.Unk28 = struct.unpack("<f", br.read(4))[0]
            st.Unk2C = struct.unpack("<f", br.read(4))[0]
            st.Unk30 = struct.unpack("<i", br.read(4))[0]
            st.Unk34 = struct.unpack("<i", br.read(4))[0]
            st.Unk38 = struct.unpack("<i", br.read(4))[0]
            st.Unk3C = struct.unpack("<i", br.read(4))[0]
            st.Unk40 = struct.unpack("<f", br.read(4))[0]
            st.Unk44 = struct.unpack("<f", br.read(4))[0]  # was Unk44_A/B/C split — actually one float32
            st.Unk48 = struct.unpack("<f", br.read(4))[0]  # actually float -1.0
            st.RootmotionStatus = struct.unpack("<f", br.read(4))[0]
            st.Unk50 = struct.unpack("<i", br.read(4))[0]
            st.BodyPartControlA = struct.unpack("<B", br.read(1))[0]
            st.BodyPartControlB = struct.unpack("<B", br.read(1))[0]
            st.BodyPartControlC = struct.unpack("<B", br.read(1))[0]
            st.BodyPartControlD = struct.unpack("<B", br.read(1))[0]
            st.Unk58 = struct.unpack("<i", br.read(4))[0]
            st.Unk5C = struct.unpack("<i", br.read(4))[0]
            raw_unk60 = struct.unpack("<i", br.read(4))[0]
            st.LeftHandAnimationId = raw_unk60 >> 16
            st.StructBsid2 = struct.unpack("<h", br.read(2))[0]
            st.UnkBsControlId_A = struct.unpack("<B", br.read(1))[0]
            st.UnkBsControlId_B = struct.unpack("<B", br.read(1))[0]
            st.WeaponAnimationCallingId = struct.unpack("<i", br.read(4))[0]
            st.Unk6C = struct.unpack("<i", br.read(4))[0]
            st.BladeHomingControl_A = struct.unpack("<B", br.read(1))[0]  # u8×4: byte0 flag
            st.BladeHomingControl_B = struct.unpack("<B", br.read(1))[0]  # byte1 param
            st.BladeHomingControl_C = struct.unpack("<B", br.read(1))[0]  # byte2
            st.BladeHomingControl_D = struct.unpack("<B", br.read(1))[0]  # byte3
            st.Unk74 = struct.unpack("<i", br.read(4))[0]  # was float, actual data is small ints
            st.Unk78 = struct.unpack("<i", br.read(4))[0]
            st.Unk7C = struct.unpack("<i", br.read(4))[0]

            if h.Version >= 10:
                st.Unk80 = struct.unpack("<i", br.read(4))[0]
                st.WeaponRailAnimationCallingId = struct.unpack("<i", br.read(4))[0]
                st.Unk88 = struct.unpack("<i", br.read(4))[0]
                st.Unk8C = struct.unpack("<i", br.read(4))[0]
                st.Unk90 = struct.unpack("<i", br.read(4))[0]
                st.Unk94 = struct.unpack("<i", br.read(4))[0]
                st.Unk98 = struct.unpack("<i", br.read(4))[0]
                st.Unk9C = struct.unpack("<i", br.read(4))[0]

            file.States.append(st)
            # Ensure we are at the next state entry
            br.seek(base + state_entry_size)

    # ================================================================
    #  StructB reader
    # ================================================================
    def _read_struct_bs(self, br: BinaryIO, file: BHVFile, h: Header):
        if h.CountB <= 0:
            return
        self._seek(br, h.OffsetB)
        for i in range(h.CountB):
            sb = StructB()
            sb.Unk00 = struct.unpack("<i", br.read(4))[0]
            sb.Unk04 = struct.unpack("<h", br.read(2))[0]
            sb.IsLooped = struct.unpack("<h", br.read(2))[0]
            sb.Unk08 = struct.unpack("<B", br.read(1))[0]
            sb.Unk09 = struct.unpack("<B", br.read(1))[0]
            sb.Unk0A = struct.unpack("<B", br.read(1))[0]
            sb.Unk0B = struct.unpack("<B", br.read(1))[0]
            sb.Unk0C = struct.unpack("<i", br.read(4))[0]
            sb.Unk10 = struct.unpack("<i", br.read(4))[0]
            sb.Unk14 = struct.unpack("<i", br.read(4))[0]
            sb.Unk18 = struct.unpack("<i", br.read(4))[0]
            sb.Unk1C = struct.unpack("<i", br.read(4))[0]
            sb.Unk20 = struct.unpack("<f", br.read(4))[0]
            sb.FacingLocked = struct.unpack("<B", br.read(1))[0]
            sb.Unk25 = struct.unpack("<B", br.read(1))[0]
            sb.Unk26 = struct.unpack("<B", br.read(1))[0]
            sb.Unk27 = struct.unpack("<B", br.read(1))[0]
            sb.Unk28 = struct.unpack("<f", br.read(4))[0]
            sb.Unk2C = struct.unpack("<f", br.read(4))[0]
            sb.Unk30 = struct.unpack("<i", br.read(4))[0]
            sb.Unk34 = struct.unpack("<i", br.read(4))[0]
            sb.Unk38 = struct.unpack("<i", br.read(4))[0]
            sb.Unk3C = struct.unpack("<i", br.read(4))[0]
            if h.Version >= 6:
                sb.Unk40 = struct.unpack("<i", br.read(4))[0]
                sb.Unk44 = struct.unpack("<h", br.read(2))[0]
                sb.Unk46 = struct.unpack("<h", br.read(2))[0]
                sb.Unk48 = struct.unpack("<h", br.read(2))[0]
                sb.Unk4A = struct.unpack("<h", br.read(2))[0]
                sb.Unk4C = struct.unpack("<h", br.read(2))[0]
                sb.Unk4E = struct.unpack("<h", br.read(2))[0]
            if h.Version >= 10:
                sb.Unk50 = struct.unpack("<h", br.read(2))[0]
                sb.Unk52 = struct.unpack("<h", br.read(2))[0]
                sb.Unk54 = struct.unpack("<h", br.read(2))[0]
                sb.Unk56 = struct.unpack("<h", br.read(2))[0]
                sb._dummy58 = struct.unpack("<i", br.read(4))[0]  # assert 0
                sb._dummy5C = struct.unpack("<i", br.read(4))[0]  # assert 0
            file.StructBs.append(sb)

    # ================================================================
    #  StructC reader
    # ================================================================
    def _read_struct_cs(self, br: BinaryIO, file: BHVFile, h: Header):
        if h.CountC <= 0 or h.SizeC <= 0:
            return
        self._seek(br, h.OffsetC)
        for i in range(h.CountC):
            row = list(br.read(h.SizeC))
            file.StructCs.append(row)

    # ================================================================
    #  StructD reader
    # ================================================================
    def _read_struct_ds(self, br: BinaryIO, file: BHVFile, h: Header):
        if h.CountD <= 0:
            return
        self._seek(br, h.OffsetD)
        for i in range(h.CountD):
            sd = StructD()
            sd.Offset00 = struct.unpack("<i", br.read(4))[0]
            sd.Count04 = struct.unpack("<i", br.read(4))[0]
            sd.Unk08 = struct.unpack("<i", br.read(4))[0]
            sd.Unk0C = struct.unpack("<i", br.read(4))[0]
            sd.Unk10 = struct.unpack("<i", br.read(4))[0]
            sd.Unk14 = struct.unpack("<i", br.read(4))[0]
            sd.Unk18 = struct.unpack("<i", br.read(4))[0]
            sd.Unk1C = struct.unpack("<i", br.read(4))[0]

            # Read DABlocks
            return_pos = br.tell()
            if sd.Count04 > 0:
                self._seek(br, sd.Offset00)
                da_size = 48 if h.Version >= 10 else 32
                for j in range(sd.Count04):
                    da = StructDA()
                    da.Unk00 = struct.unpack("<h", br.read(2))[0]
                    da.Unk02 = struct.unpack("<h", br.read(2))[0]
                    da.Unk04 = struct.unpack("<i", br.read(4))[0]
                    da.Unk08 = struct.unpack("<f", br.read(4))[0]
                    da.Unk0C = struct.unpack("<f", br.read(4))[0]
                    da.Unk10 = struct.unpack("<f", br.read(4))[0]
                    da.Unk14 = struct.unpack("<f", br.read(4))[0]
                    da.Unk18 = struct.unpack("<f", br.read(4))[0]
                    da.Unk1C = struct.unpack("<f", br.read(4))[0]
                    if h.Version >= 10:
                        da.Unk20 = struct.unpack("<i", br.read(4))[0]
                        da.Unk24 = struct.unpack("<i", br.read(4))[0]
                        da.Unk28 = struct.unpack("<i", br.read(4))[0]
                        da.Unk2C = struct.unpack("<i", br.read(4))[0]
                    sd.DABlocks.append(da)
            br.seek(return_pos)
            file.StructDs.append(sd)

    # ================================================================
    #  Transition reader (3-phase: headers → conditions → ABB)
    # ================================================================
    def _read_transitions(self, br: BinaryIO, file: BHVFile, h: Header):
        # Phase 1: Read all transition headers (no seeking to conditions)
        for st in file.States:
            st.Transitions = []
            if st.TransitionCount <= 0:
                continue
            self._seek(br, st.TransitionsOffset)
            for t_idx in range(st.TransitionCount):
                tr = Transition()
                tr.StateIndex = struct.unpack("<i", br.read(4))[0]
                tr.ConditionsOffset = struct.unpack("<i", br.read(4))[0]
                tr.ConditionCount = struct.unpack("<i", br.read(4))[0]
                tr.Offset0C = struct.unpack("<i", br.read(4))[0]
                tr.Unk10 = struct.unpack("<i", br.read(4))[0]
                tr.Unk14 = struct.unpack("<i", br.read(4))[0]
                tr.Unk18 = struct.unpack("<i", br.read(4))[0]
                tr.Unk1C = struct.unpack("<i", br.read(4))[0]
                tr.Conditions = []
                st.Transitions.append(tr)

        # Phase 2: Read condition headers + data
        all_conds = []
        for st in file.States:
            for tr in st.Transitions:
                if tr.ConditionCount <= 0:
                    continue
                self._seek(br, tr.ConditionsOffset)
                for c_idx in range(tr.ConditionCount):
                    cond = Condition()
                    cond.Id = struct.unpack("<B", br.read(1))[0]
                    cond.Unk01 = struct.unpack("<B", br.read(1))[0]
                    cond.Unk02 = struct.unpack("<B", br.read(1))[0]
                    cond.Unk03 = struct.unpack("<B", br.read(1))[0]
                    cond.DataOffset = struct.unpack("<i", br.read(4))[0]
                    # DataLength NOT in binary — computed below
                    cond.Unk08 = struct.unpack("<B", br.read(1))[0]
                    cond.Unk09 = struct.unpack("<B", br.read(1))[0]
                    cond.Unk0A = struct.unpack("<B", br.read(1))[0]
                    cond.Unk0B = struct.unpack("<B", br.read(1))[0]
                    cond.Unk0C = struct.unpack("<i", br.read(4))[0]
                    cond.Data = []
                    tr.Conditions.append(cond)
                    all_conds.append(cond)

        # Read condition data (sorted by DataOffset, length = next offset - current)
        if all_conds:
            all_conds.sort(key=lambda c: c.DataOffset)
            for i, cond in enumerate(all_conds):
                start = cond.DataOffset
                end = (all_conds[i+1].DataOffset if i+1 < len(all_conds)
                       else h.OffsetB)
                length = max(0, end - start)
                cond.DataLength = length
                if length > 0:
                    self._seek(br, start)
                    cond.Data = list(br.read(length))

        # Phase 3: Read StructABB (variable-length)
        for st in file.States:
            for tr in st.Transitions:
                self._seek(br, tr.Offset0C)
                abb = StructABB()
                abb.Unk00 = struct.unpack("<B", br.read(1))[0]
                abb.Unk01 = struct.unpack("<B", br.read(1))[0]
                abb.Unk02 = struct.unpack("<B", br.read(1))[0]
                abb.Unk03 = struct.unpack("<B", br.read(1))[0]
                abb.Type = abb.Unk01
                if abb.Unk01 == 1:
                    abb.BehaviorMatrixParam_f = struct.unpack("<f", br.read(4))[0]
                    abb.Unk08_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk0C = struct.unpack("<i", br.read(4))[0]
                    abb.Unk10_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk14_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk18_int = struct.unpack("<i", br.read(4))[0]
                elif abb.Unk01 == 3:
                    abb.BehaviorMatrixParam_i = struct.unpack("<i", br.read(4))[0]
                    abb.Unk08_f = struct.unpack("<f", br.read(4))[0]
                    abb.Unk0C = struct.unpack("<i", br.read(4))[0]
                    abb.Unk10_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk14_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk18_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk1C_int = struct.unpack("<i", br.read(4))[0]
                elif abb.Unk01 == 4:
                    abb.Unk04 = struct.unpack("<i", br.read(4))[0]
                    abb.Unk08_f = struct.unpack("<f", br.read(4))[0]
                    abb.Unk0C = struct.unpack("<i", br.read(4))[0]
                    abb.Unk10_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk14_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk18_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk1C_int = struct.unpack("<i", br.read(4))[0]
                    abb.Unk20_int = struct.unpack("<i", br.read(4))[0]
                tr.StructAbb = abb

    # ================================================================
    #  State Data reader
    # ================================================================
    def _read_state_data(self, br: BinaryIO, file: BHVFile, h: Header):
        """Read state-specific data blocks. Only states with unique Offset04 get data."""
        states = file.States
        if not states: return
        
        prev_off = -1
        for i, st in enumerate(states):
            if st.Offset04 == 0 or st.Offset04 == prev_off:
                prev_off = st.Offset04
                continue
            # Calculate length to next unique offset
            next_off = h.OffsetB  # default: end at StructB start (matching C#)
            for j in range(i + 1, len(states)):
                if states[j].Offset04 != st.Offset04 and states[j].Offset04 > 0:
                    next_off = states[j].Offset04
                    break
            length = next_off - st.Offset04
            if length <= 0:
                prev_off = st.Offset04
                continue
            self._seek(br, st.Offset04)
            st.Data = list(br.read(length))
            prev_off = st.Offset04

    # ================================================================
    #  Strings reader
    # ================================================================
    def _read_strings(self, br: BinaryIO, file: BHVFile, h: Header):
        file.Strings = []
        strings_start = DATA_START + h.OffsetD
        if h.CountD > 0:
            br.seek(strings_start)
            for sd in file.StructDs:
                br.seek(16, 1)  # skip StructD header
            strings_start = br.tell()
        br.seek(strings_start)

        count = struct.unpack("<H", br.read(2))[0]
        if count <= 0:
            return
        offsets = []
        for i in range(count):
            offsets.append(struct.unpack("<H", br.read(2))[0])
        base = br.tell()
        for off in offsets:
            br.seek(base + off)
            chars = []
            while True:
                ch = br.read(1)
                if not ch or ch == b"\x00":
                    break
                chars.append(ch)
            file.Strings.append(b"".join(chars).decode("utf-8", errors="replace"))
