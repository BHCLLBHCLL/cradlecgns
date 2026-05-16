#!/usr/bin/env python3
"""
分析 CGNS 中 ZoneBC 边界条件在 ANSA 中单元数为 0 的可能原因。

用法示例：
  python analyze_ansa_bc.py tr03_new_fix.cgns \
    /Base/FPHPARTS.Rotate/ZoneBC/Rotate_Cylinder \
    /Base/FPHPARTS.Rotate/ZoneBC/Rotate_Cylinder_Moving
"""

import sys
from pathlib import Path

import h5py
import numpy as np

DATA_DSET = " data"


def decode_bytes(arr) -> str:
    arr = np.asarray(arr)
    return arr.tobytes().decode("ascii", errors="replace").strip("\x00").strip()


def describe_bc(f: h5py.File, bc_path: str) -> None:
    print(f"\n=== BC: {bc_path} ===")
    if bc_path not in f:
        print("  [!] 路径不存在")
        return
    g = f[bc_path]

    # 1. BCType（直接在 BC group 下的 " data"）
    if DATA_DSET in g:
        raw = g[DATA_DSET][()]
        print(f"  BC data: {repr(decode_bytes(raw))}  shape={raw.shape} dtype={raw.dtype}")
    else:
        print("  [!] BC group 下没有 ' data' 数据集（可能缺失 BCType）")

    # 2. GridLocation
    if "GridLocation" in g and DATA_DSET in g["GridLocation"]:
        gl_raw = g["GridLocation"][DATA_DSET][()]
        print(f"  GridLocation: {repr(decode_bytes(gl_raw))}")
    else:
        print("  GridLocation: <无>")

    # 3. PointList
    if "PointList" in g:
        pl_grp = g["PointList"]
        if DATA_DSET in pl_grp:
            pl = np.asarray(pl_grp[DATA_DSET][()])
            flat = pl.reshape(-1)
            print(
                f"  PointList/ data: shape={pl.shape} dtype={pl.dtype} "
                f"size={flat.size}"
            )
            if flat.size > 0:
                print(
                    f"    min={int(flat.min())} max={int(flat.max())} "
                    f"first 10={flat[:10].tolist()}"
                )
        else:
            print("  [!] PointList group 存在，但没有 ' data' 数据集")
    else:
        print("  [!] BC group 下没有 PointList group")

    # 4. 对应 Zone 的 Elements 范围（粗略检查索引是否落在范围内）
    parts = bc_path.strip("/").split("/")
    try:
        zone_idx = parts.index("ZoneBC") - 1
        zone_path = "/" + "/".join(parts[: zone_idx + 1])
    except ValueError:
        zone_path = None

    if not zone_path or zone_path not in f:
        print("  Zone: <无法解析>")
        return

    zone = f[zone_path]
    print(f"  Zone: {zone_path}")
    if "ZoneType" in zone and DATA_DSET in zone["ZoneType"]:
        zt = decode_bytes(zone["ZoneType"][DATA_DSET][()])
        print(f"    ZoneType: {zt}")

    # 收集 Elements_t 的 ElementRange
    if "Elements" in zone:
        print("    Elements groups:")
        for name, obj in zone["Elements"].items():
            if not isinstance(obj, h5py.Group):
                continue
            er = obj.get("ElementRange")
            et = obj.get("ElementType")
            et_str = None
            if et is not None:
                et_data = et.get(DATA_DSET, et)
                et_str = decode_bytes(et_data[()])
            if er is not None and DATA_DSET in er:
                er_arr = np.asarray(er[DATA_DSET][()])
                if er_arr.size >= 2:
                    start, end = int(er_arr.flat[0]), int(er_arr.flat[1])
                    print(
                        f"      {name}: ElementType={et_str}, "
                        f"ElementRange=[{start}, {end}]"
                    )
            else:
                print(f"      {name}: ElementType={et_str}, ElementRange=<无>")


def main():
    if len(sys.argv) < 3:
        print(
            "用法:\n"
            "  python analyze_ansa_bc.py file.cgns "
            "/Base/.../ZoneBC/BC1 /Base/.../ZoneBC/BC2 ..."
        )
        sys.exit(1)

    fn = Path(sys.argv[1])
    bc_paths = sys.argv[2:]

    if not fn.exists():
        print("文件不存在:", fn)
        sys.exit(1)

    with h5py.File(fn, "r") as f:
        for p in bc_paths:
            describe_bc(f, p)


if __name__ == "__main__":
    main()

