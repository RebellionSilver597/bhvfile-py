"""诊断脚本：测试 basenormal.bhv 读取每个阶段"""
import sys, os, struct, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from model.binary_reader import BhvBinaryReader

BHV_PATH = r"E:\modfile\ModEngine-2.1.0.0-rc1-win64\me3\config\profiles\AC6mod\chr\c0001-behbnd-dcx\basenormal.bhv"

def main():
    print(f"Reading: {BHV_PATH}")
    print(f"File size: {os.path.getsize(BHV_PATH)} bytes")
    
    try:
        reader = BhvBinaryReader(BHV_PATH)
        f = reader.load()
        h = f.Header
        print(f"\n=== Header ===")
        print(f"Version: {h.Version}")
        print(f"Unk02: {h.Unk02}")
        print(f"FileSize: {h.FileSize}")
        print(f"StatesOffset: 0x{h.StatesOffset:X}")
        print(f"StateCount: {h.StateCount}")
        print(f"OffsetB: 0x{h.OffsetB:X}, CountB: {h.CountB}")
        print(f"OffsetC: 0x{h.OffsetC:X}, CountC: {h.CountC}, SizeC: {h.SizeC}")
        print(f"OffsetD: 0x{h.OffsetD:X}, CountD: {h.CountD}")
        print(f"MysteryBlock size: {len(h.MysteryBlock)} (0x{len(h.MysteryBlock):X})")
        print(f"\nStates: {len(f.States)}")
        print(f"StructBs: {len(f.StructBs)}")
        print(f"StructCs: {len(f.StructCs)}")
        print(f"StructDs: {len(f.StructDs)}")
        print(f"Strings: {len(f.Strings) if f.Strings else 0}")
        print(f"FileType: {f.file_type}")
        
        if f.States:
            s0 = f.States[0]
            print(f"\n=== First State ===")
            print(f"Index: {s0.Index}")
            print(f"StructBid: {s0.StructBid}")
            print(f"Transitions: {len(s0.Transitions)}")
            print(f"Data len: {len(s0.Data)}")
            if s0.Transitions:
                t0 = s0.Transitions[0]
                print(f"  T0 -> StateIndex={t0.StateIndex}, Conditions={len(t0.Conditions)}")
        
        print("\n=== SUCCESS ===")
        
    except Exception as e:
        print(f"\n=== ERROR ===")
        traceback.print_exc()

if __name__ == "__main__":
    main()
