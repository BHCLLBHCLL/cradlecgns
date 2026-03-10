#!/usr/bin/env python3
"""
CGNS 汇总修复脚本，整合以下功能：

  1. CGNS 版本改为 4.2
  2. ZoneBC 边界条件名称下 data 统一改为 BCWall（不修改 GridLocation）
  3. PointList shape 由 (n,) 改为 (n, 1)
  4. 删除以 @ 开头的 group
  5. 删除 PointList 没有 data 数据集的边界 group

用法：
  python cgns_repair_summary.py input.cgns                 # 原地修改
  python cgns_repair_summary.py input.cgns -o output.cgns  # 输出到新文件
  python cgns_repair_summary.py input.cgns -n              # 仅预览
"""

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
TARGET_VERSION = 4.2
BC_TYPE_WALL = "BCWall"


# ---------------------------------------------------------------------------
# 步骤 1：CGNS 版本改为 4.2
# ---------------------------------------------------------------------------

def step_set_version(f, dry_run):
    """将 CGNSLibraryVersion 设置为 4.2。"""
    name = "CGNSLibraryVersion"
    version_data = np.array([TARGET_VERSION], dtype=np.float32)

    if name not in f:
        print(f"[1 版本] 创建 {name} = {TARGET_VERSION}")
        if not dry_run:
            grp = f.create_group(name)
            grp.create_dataset(DATA_DSET, data=version_data)
        return

    grp = f[name]
    if DATA_DSET not in grp:
        print(f"[1 版本] 写入 {name} = {TARGET_VERSION}")
        if not dry_run:
            grp.create_dataset(DATA_DSET, data=version_data)
        return

    current = float(grp[DATA_DSET][()].flat[0])
    if abs(current - TARGET_VERSION) < 1e-5:
        print(f"[1 版本] CGNSLibraryVersion 已为 {TARGET_VERSION}，跳过。")
        return

    print(f"[1 版本] CGNSLibraryVersion: {current} -> {TARGET_VERSION}")
    if not dry_run:
        del grp[DATA_DSET]
        grp.create_dataset(DATA_DSET, data=version_data)


# ---------------------------------------------------------------------------
# 步骤 2：ZoneBC 边界条件 data 统一改为 BCWall
# ---------------------------------------------------------------------------

def step_bc_to_bcwall(f, dry_run):
    """将 ZoneBC 下边界条件名称下的 data 统一设为 BCWall（不修改 GridLocation 等）。"""
    to_fix = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Dataset):
            return
        if "ZoneBC" not in name or not name.endswith("/" + DATA_DSET):
            return
        parent = obj.parent
        if "PointList" in parent.name or "GridLocation" in parent.name:
            return
        to_fix.append((obj, name))

    f.visititems(visit)

    if not to_fix:
        print("[2 BCWall] 未发现需修改的 ZoneBC 边界条件。")
        return

    val = BC_TYPE_WALL.encode("ascii")[:6]  # 保持 6 字节
    arr = np.frombuffer(val, dtype=np.int8)

    for ds, path in to_fix:
        print(f"[2 BCWall] {path}")
        if not dry_run:
            parent = ds.parent
            key = ds.name.split("/")[-1]
            del parent[key]
            parent.create_dataset(key, data=arr.copy(), dtype=np.int8)


# ---------------------------------------------------------------------------
# 步骤 3：PointList shape (n,) -> (n, 1)
# ---------------------------------------------------------------------------

def step_fix_pointlist_shape(f, dry_run):
    """将 ZoneBC 下 PointList 的 data shape 从 (n,) 改为 (n, 1)。"""
    to_fix = []

    def visit(name, obj):
        if (
            isinstance(obj, h5py.Dataset)
            and obj.name.endswith("/PointList/" + DATA_DSET)
            and "ZoneBC" in obj.name
            and len(obj.shape) == 1
        ):
            to_fix.append((obj.parent, obj.name))

    f.visititems(visit)

    if not to_fix:
        print("[3 PointList] 未发现需修正的 shape。")
        return

    for pointlist_grp, path in to_fix:
        shape = pointlist_grp[DATA_DSET].shape
        print(f"[3 PointList] {path}: {shape} -> ({shape[0]}, 1)")
        if not dry_run:
            data = np.asarray(pointlist_grp[DATA_DSET][()]).reshape(-1, 1)
            del pointlist_grp[DATA_DSET]
            pointlist_grp.create_dataset(DATA_DSET, data=data)


# ---------------------------------------------------------------------------
# 步骤 4：删除以 @ 开头的 group
# ---------------------------------------------------------------------------

def step_delete_at_groups(f, dry_run):
    """删除名称以 @ 开头的 group（含子节点）。"""
    to_delete = []

    def visit(name, obj):
        if isinstance(obj, h5py.Group):
            key = name.rsplit("/", 1)[-1] if "/" in name else name
            if key.startswith("@"):
                to_delete.append(name)

    f.visititems(visit)

    if not to_delete:
        print("[4 @group] 未发现以 @ 开头的 group。")
        return

    for path in sorted(to_delete, key=len, reverse=True):
        print(f"[4 @group] 删除: {path}")
        if not dry_run:
            p = path.strip("/").split("/")
            key = p[-1]
            parent = f
            for seg in p[:-1]:
                parent = parent[seg]
            del parent[key]


# ---------------------------------------------------------------------------
# 步骤 5：删除 PointList 为空的边界 group
# ---------------------------------------------------------------------------

def step_delete_empty_pointlist_bc(f, dry_run):
    """删除 PointList 没有 data 数据集的边界条件 group。"""
    to_delete = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Group):
            return
        if "ZoneBC" not in name:
            return
        if not name.endswith("/PointList"):
            return
        pointlist = obj
        if DATA_DSET not in pointlist:
            bc_grp = pointlist.parent
            zonebc = bc_grp.parent
            bc_key = bc_grp.name.rsplit("/", 1)[-1]
            to_delete.append((zonebc, bc_key))

    f.visititems(visit)

    if not to_delete:
        print("[5 空BC] 未发现 PointList 无 data 的边界 group。")
        return

    for zonebc, bc_key in to_delete:
        path = f"{zonebc.name}/{bc_key}"
        print(f"[5 空BC] 删除（PointList 无 data）: {path}")
        if not dry_run:
            del zonebc[bc_key]


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CGNS 汇总修复：版本、BCWall、PointList、@group、空BC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
步骤：
  1. CGNSLibraryVersion = 4.2
  2. ZoneBC 边界条件名称下 data -> BCWall（不修改 GridLocation）
  3. PointList shape (n,) -> (n, 1)
  4. 删除以 @ 开头的 group
  5. 删除 PointList 没有 data 的边界 group

示例：
  python cgns_repair_summary.py input.cgns
  python cgns_repair_summary.py input.cgns -o output.cgns
  python cgns_repair_summary.py input.cgns -n
""",
    )
    parser.add_argument("file", help="输入 CGNS/HDF5 文件")
    parser.add_argument("-o", "--output", help="输出到新文件")
    parser.add_argument("-n", "--dry-run", action="store_true", help="仅预览")
    args = parser.parse_args()

    input_path = Path(args.file)
    if not input_path.exists():
        print(f"错误：文件不存在: {input_path}")
        sys.exit(1)

    target = input_path
    if args.output and not args.dry_run:
        target = Path(args.output)
        shutil.copy2(input_path, target)
        print(f"已复制到: {target}\n")

    mode = "r" if args.dry_run else "r+"
    label = "[预览]" if args.dry_run else ""
    print(f"{label} 处理: {target}\n")

    try:
        with h5py.File(target, mode) as f:
            step_set_version(f, args.dry_run)
            print()
            step_bc_to_bcwall(f, args.dry_run)
            print()
            step_fix_pointlist_shape(f, args.dry_run)
            print()
            step_delete_at_groups(f, args.dry_run)
            print()
            step_delete_empty_pointlist_bc(f, args.dry_run)
    except OSError as e:
        print(f"错误：无法打开 '{target}'")
        if "lock" in str(e).lower() or "33" in str(e):
            print("  文件可能被占用，请使用 -o 输出到新文件。")
        print(f"  {e}")
        sys.exit(1)

    print()
    if args.dry_run:
        print("预览完成，未修改。")
    else:
        print(f"完成: {target}")


if __name__ == "__main__":
    main()
