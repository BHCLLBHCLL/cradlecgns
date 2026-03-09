#!/usr/bin/env python3
"""将 CGNS 文件中 ZoneBC 边界条件的 data 为 Null 的，全部转换为 BCWall。"""

import argparse
import shutil
import sys
from pathlib import Path

try:
    import h5py
    import numpy as np
except ImportError:
    print("pip install h5py numpy")
    sys.exit(1)

DATA_DSET = " data"
BC_TYPE_WALL = "BCWall"


def collect_bc_with_null(f):
    """收集 ZoneBC 下 data 为 Null/NULL 的 BC 节点。"""
    result = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Dataset):
            return
        if "ZoneBC" not in name:
            return
        if not name.endswith("/" + DATA_DSET):
            return
        arr = np.asarray(obj[()])
        if arr.dtype.kind not in ("S", "U", "i", "u") or arr.dtype.itemsize != 1:
            return
        s = arr.tobytes().decode("ascii", errors="replace").strip().rstrip("\x00")
        if s.lower() == "null":
            result.append((obj, name))

    f.visititems(visit)
    return result


def fix_one(ds, new_val=BC_TYPE_WALL):
    """将 Null 替换为 BCWall（CGNS 32 字节约定）。"""
    val = new_val.encode("ascii").ljust(32, b"\x00")[:32]
    arr = np.frombuffer(val, dtype=np.int8)
    parent = ds.parent
    key = ds.name.split("/")[-1]
    del parent[key]
    parent.create_dataset(key, data=arr, dtype=np.int8)


def main():
    parser = argparse.ArgumentParser(
        description="将 ZoneBC 中 data 为 Null 的边界条件全部转换为 BCWall"
    )
    parser.add_argument("file", help="CGNS/HDF5 文件路径")
    parser.add_argument("-o", "--output", help="输出到新文件（避免源文件被占用时出错）")
    parser.add_argument("-n", "--dry-run", action="store_true", help="仅列出，不修改")
    args = parser.parse_args()

    input_path = Path(args.file)
    if not input_path.exists():
        print(f"错误：文件不存在: {input_path}")
        sys.exit(1)

    target = input_path
    if args.output and not args.dry_run:
        target = Path(args.output)
        shutil.copy2(input_path, target)
        print(f"已复制到: {target}")

    try:
        mode = "r" if args.dry_run else "r+"
        f = h5py.File(target, mode)
    except OSError as e:
        print(f"错误：无法打开文件 '{target}'")
        print("  若文件被其他程序占用，请使用 -o 输出到新文件，或先关闭占用程序。")
        print(f"  详情: {e}")
        sys.exit(1)

    with f:
        to_fix = collect_bc_with_null(f)
        if not to_fix:
            print("未发现 ZoneBC 中 data 为 Null 的边界条件。")
            return

        if args.dry_run:
            print("以下将 Null -> BCWall:")
            for _, path in to_fix:
                print(" ", path)
            return

        for ds, path in to_fix:
            fix_one(ds)
            print(f"已修改: {path} -> {BC_TYPE_WALL}")


if __name__ == "__main__":
    main()
