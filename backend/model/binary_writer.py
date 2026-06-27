"""BHV 二进制文件写出器 - 完全对应 C# BHVFile.Save / Write 逻辑

Phase 1: 计算所有偏移（从 state table 结束位置开始重新计算）
Phase 2: 按 C# 顺序写入（顺序写入，不 seek 到旧偏移）
"""

import struct
from typing import BinaryIO
from .bhv_file import (
    BHVFile, FileType, State, Transition, Condition,
    StructABB, StructB, StructD, StructDA, Header
)

DATA_START = 0x20


class BhvBinaryWriter:
    def __init__(self, file: BHVFile):
        self.file = file

    def save(self, path: str):
        with open(path, "wb") as f:
            self._write(f)

    def _write(self, bw: BinaryIO):
        file = self.file
        h = file.Header

        # Detect file type
        if h.MysteryBlock and len(h.MysteryBlock) == 0xE0:
            file.file_type = FileType.BASENORMAL

        state_entry_size = 0xA0 if h.Version >= 10 else 0x80
        sb_entry_size = 0x60 if h.Version >= 10 else (0x50 if h.Version >= 6 else 0x40)

        # ========== Phase 1: Calculate ALL relative offsets from scratch ==========
        # This matches C# Write(): start data after state entries table,
        # assign everything sequentially. Do NOT preserve old offsets.

        # Pre-pass: ensure StructAbb.Type matches Unk01 (matching C# Write)
        for st in (file.States or []):
            for tr in (st.Transitions or []):
                if tr.StructAbb is None:
                    tr.StructAbb = StructABB()
                abb = tr.StructAbb
                abb.Type = abb.Unk01 if abb.Unk01 in (1, 3, 4) else 0
                if abb.Type == 1:
                    abb.Unk01 = 1  # ensure consistency

        # Header placeholder (0x40 = 64 bytes)
        header_start = 0
        bw.write(b"\x00" * 0x40)

        # Mystery Block
        mb = h.MysteryBlock or b""
        bw.write(mb)

        # States start right after mystery
        h.StatesOffset = int(bw.tell() - DATA_START)
        h.StateCount = len(file.States) if file.States else 0

        # ---- 1) State Data area (Offset04) ----
        # Start AFTER the state entries table (matching C# line 576)
        data_rel = h.StatesOffset + h.StateCount * state_entry_size
        for st in (file.States or []):
            if st.Data and len(st.Data) > 0:
                st.Offset04 = data_rel
                data_rel += len(st.Data)
            else:
                st.Offset04 = data_rel  # point to end of data area (C# backfill)

        # ---- 2) Transition table (32 bytes each, sequential) ----
        trans_rel = data_rel
        for st in (file.States or []):
            st.TransitionCount = len(st.Transitions) if st.Transitions else 0
            if st.TransitionCount > 0:
                st.TransitionsOffset = trans_rel
                trans_rel += st.TransitionCount * 32
            else:
                st.TransitionsOffset = 0

        # ---- 3) StructABB area (each aligned to 32 bytes) ----
        abb_rel = trans_rel
        for st in (file.States or []):
            for tr in (st.Transitions or []):
                abb = tr.StructAbb or StructABB()
                content_size = {1: 28, 3: 32, 4: 36}.get(abb.Type, 4)
                alloc_size = ((content_size + 31) // 32) * 32
                tr.Offset0C = abb_rel
                abb_rel += alloc_size

        # ---- 4) Condition structures (16 bytes each) ----
        cond_rel = abb_rel
        all_conds = []
        for st in (file.States or []):
            for tr in (st.Transitions or []):
                tr.ConditionCount = len(tr.Conditions) if tr.Conditions else 0
                if tr.ConditionCount > 0:
                    tr.ConditionsOffset = cond_rel
                    cond_rel += tr.ConditionCount * 16
                    for c in tr.Conditions:
                        all_conds.append(c)
                else:
                    tr.ConditionsOffset = 0

        # ---- 5) Condition data area ----
        cond_data_rel = cond_rel
        for cond in all_conds:
            dlen = len(cond.Data) if cond.Data else 0
            cond.DataOffset = cond_data_rel if dlen > 0 else cond_data_rel
            cond.DataLength = dlen
            if dlen > 0:
                cond_data_rel += dlen

        # ---- 6) StructB offsets ----
        h.OffsetB = cond_data_rel
        h.CountB = len(file.StructBs) if file.StructBs else 0

        # ---- 7) StructC offsets ----
        h.OffsetC = h.OffsetB + h.CountB * sb_entry_size
        h.CountC = len(file.StructCs) if file.StructCs else 0
        # Preserve original SizeC if StructCs is empty (e.g. w393.bhv)
        if file.StructCs:
            h.SizeC = len(file.StructCs[0])
        # else keep original h.SizeC from reader

        # ---- 8) StructD offset ----
        c_data_end = h.OffsetC + h.CountC * h.SizeC
        h.OffsetD = c_data_end
        h.CountD = len(file.StructDs) if file.StructDs else 0

        # ========== Phase 2: Write everything SEQUENTIALLY ==========
        # Matching C#: no seeking between sections after state entries

        # --- State entries ---
        bw.seek(DATA_START + h.StatesOffset)
        for st in (file.States or []):
            self._write_state_entry(bw, st, h)

        # --- State Data (sequential write — matching C# line 767-774) ---
        for st in (file.States or []):
            if st.Data and len(st.Data) > 0:
                bw.write(bytes(st.Data))

        # --- Transitions (sequential write — matching C# line 776-790) ---
        for st in (file.States or []):
            for tr in (st.Transitions or []):
                bw.write(struct.pack("<i", tr.StateIndex))
                bw.write(struct.pack("<i", tr.ConditionsOffset))
                bw.write(struct.pack("<i", tr.ConditionCount))
                bw.write(struct.pack("<i", tr.Offset0C))
                bw.write(struct.pack("<i", tr.Unk10 or 0))
                bw.write(struct.pack("<i", tr.Unk14 or 0))
                bw.write(struct.pack("<i", tr.Unk18 or 0))
                bw.write(struct.pack("<i", tr.Unk1C or 0))

        # --- StructABB data (sequential, aligned blocks) ---
        for st in (file.States or []):
            for tr in (st.Transitions or []):
                abb = tr.StructAbb or StructABB()
                content_size = {1: 28, 3: 32, 4: 36}.get(abb.Type, 4)
                alloc_size = ((content_size + 31) // 32) * 32
                bw.write(bytes([abb.Unk00, abb.Unk01, abb.Unk02, abb.Unk03]))
                if abb.Type == 1:
                    bw.write(struct.pack("<f", abb.BehaviorMatrixParam_f))
                    bw.write(struct.pack("<i", abb.Unk08_int))
                    bw.write(struct.pack("<i", abb.Unk0C))
                    bw.write(struct.pack("<i", abb.Unk10_int))
                    bw.write(struct.pack("<i", abb.Unk14_int))
                    bw.write(struct.pack("<i", abb.Unk18_int))
                elif abb.Type == 3:
                    bw.write(struct.pack("<i", abb.BehaviorMatrixParam_i))
                    bw.write(struct.pack("<f", abb.Unk08_f))
                    bw.write(struct.pack("<i", abb.Unk0C))
                    bw.write(struct.pack("<i", abb.Unk10_int))
                    bw.write(struct.pack("<i", abb.Unk14_int))
                    bw.write(struct.pack("<i", abb.Unk18_int))
                    bw.write(struct.pack("<i", abb.Unk1C_int))
                elif abb.Type == 4:
                    bw.write(struct.pack("<i", abb.Unk04))
                    bw.write(struct.pack("<f", abb.Unk08_f))
                    bw.write(struct.pack("<i", abb.Unk0C))
                    bw.write(struct.pack("<i", abb.Unk10_int))
                    bw.write(struct.pack("<i", abb.Unk14_int))
                    bw.write(struct.pack("<i", abb.Unk18_int))
                    bw.write(struct.pack("<i", abb.Unk1C_int))
                    bw.write(struct.pack("<i", abb.Unk20_int))
                pad = alloc_size - content_size
                if pad > 0:
                    bw.write(b"\x00" * pad)

        # --- Condition structures (sequential) ---
        for st in (file.States or []):
            for tr in (st.Transitions or []):
                for cond in (tr.Conditions or []):
                    bw.write(bytes([cond.Id, cond.Unk01, cond.Unk02, cond.Unk03]))
                    bw.write(struct.pack("<i", cond.DataOffset))
                    bw.write(bytes([cond.Unk08, cond.Unk09, cond.Unk0A, cond.Unk0B]))
                    bw.write(struct.pack("<i", cond.Unk0C))

        # --- Condition data (sequential) ---
        for cond in all_conds:
            if cond.Data and len(cond.Data) > 0:
                bw.write(bytes(cond.Data))

        # --- StructB (sequential) ---
        for sb in (file.StructBs or []):
            bw.write(struct.pack("<i", sb.Unk00))
            bw.write(struct.pack("<h", sb.Unk04))
            bw.write(struct.pack("<h", sb.IsLooped))
            bw.write(bytes([sb.Unk08, sb.Unk09, sb.Unk0A, sb.Unk0B]))
            bw.write(struct.pack("<i", sb.Unk0C))
            bw.write(struct.pack("<i", sb.Unk10))
            bw.write(struct.pack("<i", sb.Unk14))
            bw.write(struct.pack("<i", sb.Unk18))
            bw.write(struct.pack("<i", sb.Unk1C))
            bw.write(struct.pack("<f", sb.Unk20))
            bw.write(bytes([sb.FacingLocked, sb.Unk25, sb.Unk26, sb.Unk27]))
            bw.write(struct.pack("<f", sb.Unk28))
            bw.write(struct.pack("<f", sb.Unk2C))
            bw.write(struct.pack("<i", sb.Unk30))
            bw.write(struct.pack("<i", sb.Unk34))
            bw.write(struct.pack("<i", sb.Unk38))
            bw.write(struct.pack("<i", sb.Unk3C))
            if h.Version >= 6:
                bw.write(struct.pack("<i", sb.Unk40))
                bw.write(struct.pack("<h", sb.Unk44))
                bw.write(struct.pack("<h", sb.Unk46))
                bw.write(struct.pack("<h", sb.Unk48))
                bw.write(struct.pack("<h", sb.Unk4A))
                bw.write(struct.pack("<h", sb.Unk4C))
                bw.write(struct.pack("<h", sb.Unk4E))
            if h.Version >= 10:
                bw.write(struct.pack("<h", sb.Unk50))
                bw.write(struct.pack("<h", sb.Unk52))
                bw.write(struct.pack("<h", sb.Unk54))
                bw.write(struct.pack("<h", sb.Unk56))
                bw.write(struct.pack("<i", 0))  # dummy58
                bw.write(struct.pack("<i", 0))  # dummy5C

        # --- StructC (sequential) ---
        for row in (file.StructCs or []):
            bw.write(bytes(row))

        # --- StructD headers + DABlocks ---
        for sd in (file.StructDs or []):
            bw.write(struct.pack("<i", sd.Offset00))
            bw.write(struct.pack("<i", sd.Count04))
            bw.write(struct.pack("<i", sd.Unk08))
            bw.write(struct.pack("<i", sd.Unk0C))
            bw.write(struct.pack("<i", sd.Unk10))
            bw.write(struct.pack("<i", sd.Unk14))
            bw.write(struct.pack("<i", sd.Unk18))
            bw.write(struct.pack("<i", sd.Unk1C))
        for sd in (file.StructDs or []):
            for da in (sd.DABlocks or []):
                bw.write(struct.pack("<h", da.Unk00))
                bw.write(struct.pack("<h", da.Unk02))
                bw.write(struct.pack("<i", da.Unk04))
                bw.write(struct.pack("<f", da.Unk08))
                bw.write(struct.pack("<f", da.Unk0C))
                bw.write(struct.pack("<f", da.Unk10))
                bw.write(struct.pack("<f", da.Unk14))
                bw.write(struct.pack("<f", da.Unk18))
                bw.write(struct.pack("<f", da.Unk1C))
                if h.Version >= 10:
                    bw.write(struct.pack("<i", da.Unk20))
                    bw.write(struct.pack("<i", da.Unk24))
                    bw.write(struct.pack("<i", da.Unk28))
                    bw.write(struct.pack("<i", da.Unk2C))

        # --- Strings (basenormal only) ---
        if file.file_type == FileType.BASENORMAL:
            strings = file.Strings or []
            bw.write(struct.pack("<H", len(strings)))
            if strings:
                offset_table = bw.tell()
                bw.write(b"\x00" * (2 * len(strings)))
                offsets = []
                data_start = bw.tell()
                for s in strings:
                    offsets.append(bw.tell() - data_start)
                    bw.write((s or "").encode("utf-8") + b"\x00")
                end_pos = bw.tell()
                bw.seek(offset_table)
                for off in offsets:
                    bw.write(struct.pack("<H", off))
                bw.seek(end_pos)

        # --- Update Header ---
        file_size = bw.tell()
        h.FileSize = file_size
        bw.seek(header_start)
        self._write_header(bw, h, file_size)

    def _write_header(self, bw: BinaryIO, h: Header, file_size: int):
        bw.write(struct.pack("<hh", h.Version, h.Unk02))
        bw.write(struct.pack("<i", file_size))
        uh = h.UnknownHeader if len(h.UnknownHeader) == 24 else bytes(24)
        bw.write(uh)
        bw.write(struct.pack("<i", h.StatesOffset))
        bw.write(struct.pack("<i", h.StateCount))
        bw.write(struct.pack("<i", h.OffsetB))
        bw.write(struct.pack("<i", h.CountB))
        bw.write(struct.pack("<i", h.OffsetC))
        bw.write(struct.pack("<h", h.CountC))
        bw.write(struct.pack("<h", h.SizeC))
        bw.write(struct.pack("<i", h.OffsetD))
        bw.write(struct.pack("<i", h.CountD))

    def _write_state_entry(self, bw: BinaryIO, st: State, h: Header):
        bw.write(struct.pack("<h", st.Unk00))
        bw.write(struct.pack("<h", st.BoostParamSection))
        bw.write(struct.pack("<i", st.Offset04))
        bw.write(struct.pack("<i", st.TransitionsOffset))
        bw.write(struct.pack("<i", len(st.Transitions)))
        bw.write(struct.pack("<h", st.StructBid))
        bw.write(struct.pack("<h", st.Unk10))
        bw.write(struct.pack("<i", st.Unk14))
        bw.write(struct.pack("<h", st.Unk18_A))
        bw.write(struct.pack("<h", st.Unk18_B))
        bw.write(struct.pack("<i", st.Unk1C))
        bw.write(struct.pack("<i", st.Unk20))
        bw.write(struct.pack("<f", st.Unk24))
        bw.write(struct.pack("<f", st.Unk28))
        bw.write(struct.pack("<f", st.Unk2C))
        bw.write(struct.pack("<i", st.Unk30))
        bw.write(struct.pack("<i", st.Unk34))
        bw.write(struct.pack("<i", st.Unk38))
        bw.write(struct.pack("<i", st.Unk3C))
        bw.write(struct.pack("<f", st.Unk40))
        bw.write(struct.pack("<f", st.Unk44))
        bw.write(struct.pack("<f", st.Unk48))
        bw.write(struct.pack("<f", st.RootmotionStatus))
        bw.write(struct.pack("<i", st.Unk50))
        bw.write(struct.pack("<B", st.BodyPartControlA))
        bw.write(struct.pack("<B", st.BodyPartControlB))
        bw.write(struct.pack("<B", st.BodyPartControlC))
        bw.write(struct.pack("<B", st.BodyPartControlD))
        bw.write(struct.pack("<i", st.Unk58))
        bw.write(struct.pack("<i", st.Unk5C))
        raw_unk60 = (st.LeftHandAnimationId << 16) & 0xFFFFFFFF
        if raw_unk60 > 0x7FFFFFFF:
            raw_unk60 = raw_unk60 - 0x100000000
        bw.write(struct.pack("<i", raw_unk60))
        bw.write(struct.pack("<h", st.StructBsid2))
        bw.write(struct.pack("<B", st.UnkBsControlId_A))
        bw.write(struct.pack("<B", st.UnkBsControlId_B))
        bw.write(struct.pack("<i", st.WeaponAnimationCallingId))
        bw.write(struct.pack("<i", st.Unk6C))
        bw.write(struct.pack("<B", st.BladeHomingControl_A))
        bw.write(struct.pack("<B", st.BladeHomingControl_B))
        bw.write(struct.pack("<B", st.BladeHomingControl_C))
        bw.write(struct.pack("<B", st.BladeHomingControl_D))
        bw.write(struct.pack("<i", st.Unk74))
        bw.write(struct.pack("<i", st.Unk78))
        bw.write(struct.pack("<i", st.Unk7C))
        if h.Version >= 10:
            bw.write(struct.pack("<i", st.Unk80))
            bw.write(struct.pack("<i", st.WeaponRailAnimationCallingId))
            bw.write(struct.pack("<i", st.Unk88))
            bw.write(struct.pack("<i", st.Unk8C))
            bw.write(struct.pack("<i", st.Unk90))
            bw.write(struct.pack("<i", st.Unk94))
            bw.write(struct.pack("<i", st.Unk98))
            bw.write(struct.pack("<i", st.Unk9C))
