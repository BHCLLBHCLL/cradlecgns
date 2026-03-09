#!/usr/bin/env python3
"""
将读入的 CGNS 文件转换为符合 CGNS 4.2 标准的版本。

CGNS 4.2 主要要求：
  - CGNSLibraryVersion = 4.2
  - NGON_n / NFACE_n：使用偏移数组格式（ElementConnectivity + ElementStartOffset）
  - 支持 int64 大整数
  - PointList 的 shape 应为 (n, 1)
  - BCType 不能为 Null/NULL，应为 BCTypeNull

本脚本执行以下转换：
  1. 设置 CGNSLibraryVersion 为 4.2
  2. NGON_n / NFACE_n：若为 3.x 内联格式，转为 4.x 偏移格式
  3. 整数连接性数据 -> int64
  4. PointList shape (n,) -> (n, 1)
  5. BCType Null/NULL -> BCTypeNull

用法：
  python upgrade_to_cgns_42.py input.cgns                 # 原地修改
  python upgrade_to_cgns_42.py input.cgns -o output.cgns  # 输出到新文件
  python upgrade_to_cgns_42.py input.cgns -n              # 仅预览，不修改
"""

import argparse
import shutil
import sys
from pathlib import Path

try:
    import h5py
    import numpy as np
except ImportError as e:
    print(f"请先安装依赖: pip install h5py numpy  ({e})")
    sys.exit(1)


DATA_DSET = " data"
TARGET_VERSION = 4.2

# CGNS 整型 ElementType 编号 -> 名称
ETYPE_INT_TO_NAME = {
    2: "NODE", 3: "BAR_2", 4: "BAR_3", 5: "TRI_3", 6: "TRI_6",
    7: "QUAD_4", 8: "QUAD_8", 9: "QUAD_9", 10: "TETRA_4", 11: "TETRA_10",
    12: "PYRA_5", 13: "PYRA_14", 14: "PENTA_6", 15: "PENTA_15", 16: "PENTA_18",
    17: "HEXA_8", 18: "HEXA_20", 19: "HEXA_27", 20: "MIXED",
    21: "NGON_n", 22: "NGON_n", 23: "NFACE_n",
}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def read_data(node):
    """从 Group（含 ' data' 子集）或 Dataset 读取数组数据。"""
    if isinstance(node, h5py.Dataset):
        return node[()]
    if isinstance(node, h5py.Group) and DATA_DSET in node:
        return node[DATA_DSET][()]
    return None


def decode_etype(arr):
    """从 ElementType 的 data 数组解析类型名称。"""
    arr = np.asarray(arr).ravel()
    if arr.dtype.kind in ("S", "U", "O"):
        if arr.dtype.kind == "S":
            s = b"".join(arr).decode(errors="replace")
        else:
            s = "".join(str(c) for c in arr)
        return s.strip().rstrip("\x00")
    if arr.size >= 1:
        return ETYPE_INT_TO_NAME.get(int(arr.flat[0]))
    return None


def get_etype(elements_group):
    """从 Elements_t Group 读取元素类型名称。"""
    et = elements_group.get("ElementType")
    if et is not None:
        data = read_data(et)
        if data is not None:
            result = decode_etype(data)
            if result:
                return result
    data_node = elements_group.get(DATA_DSET)
    if data_node is not None and isinstance(data_node, h5py.Dataset):
        arr = np.asarray(data_node[()]).ravel()
        if arr.dtype.kind in ("i", "u") and arr.size >= 1:
            return ETYPE_INT_TO_NAME.get(int(arr.flat[0]))
    return None


# ---------------------------------------------------------------------------
# 步骤 1：设置 CGNSLibraryVersion
# ---------------------------------------------------------------------------

def step_set_version(f, dry_run):
    """将 CGNSLibraryVersion 设置为 4.2。"""
    name = "CGNSLibraryVersion"
    version_data = np.array([TARGET_VERSION], dtype=np.float32)

    if name not in f:
        print(f"[版本] {name} 节点不存在，将创建并设为 {TARGET_VERSION}")
        if not dry_run:
            grp = f.create_group(name)
            grp.create_dataset(DATA_DSET, data=version_data)
        return

    grp = f[name]
    if DATA_DSET not in grp:
        print(f"[版本] {name} 存在但无 data，将写入 {TARGET_VERSION}")
        if not dry_run:
            grp.create_dataset(DATA_DSET, data=version_data)
        return

    current = float(grp[DATA_DSET][()].flat[0])
    if current == TARGET_VERSION:
        print(f"[版本] CGNSLibraryVersion 已为 {TARGET_VERSION}，无需修改。")
        return

    print(f"[版本] CGNSLibraryVersion: {current} -> {TARGET_VERSION}")
    if not dry_run:
        del grp[DATA_DSET]
        grp.create_dataset(DATA_DSET, data=version_data)


# ---------------------------------------------------------------------------
# 步骤 2：NGON_n / NFACE_n 内联格式 -> 4.x 偏移格式
# ---------------------------------------------------------------------------

def _collect_ngon_nface_inline(f):
    """
    收集 NGON_n / NFACE_n 类型且仅有 ElementConnectivity（无 ElementStartOffset）
    的 Elements_t Group，即 3.x 内联格式。
    """
    results = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Group):
            return
        keys = set(obj.keys())
        if "ElementConnectivity" not in keys or "ElementStartOffset" in keys:
            return
        etype = get_etype(obj)
        if etype in ("NGON_n", "NFACE_n"):
            results.append(obj)

    f.visititems(visit)
    return results


def _build_offset_format(conn_inline):
    """
    将 CGNS 3.x 内联格式转换为 CGNS 4.x 偏移格式。

    3.x 内联：[n0, v0, v1, ..., n1, v0, v1, ...]
    4.x 偏移：ElementConnectivity = [v0, v1, ..., v0, v1, ...]
             ElementStartOffset = [0, n0, n0+n1, ...]
    """
    conn = np.asarray(conn_inline).ravel()
    offsets = [0]
    conn_flat = []
    i = 0
    while i < len(conn):
        nv = int(conn[i])
        if i + 1 + nv > len(conn):
            raise ValueError(f"内联格式解析错误：位置 {i} 处 count={nv} 超出数组长度")
        seg = conn[i + 1 : i + 1 + nv]
        conn_flat.append(seg)
        offsets.append(offsets[-1] + nv)
        i += 1 + nv

    new_conn = np.concatenate(conn_flat) if conn_flat else np.array([], dtype=np.int64)
    new_offsets = np.array(offsets, dtype=np.int64)
    return new_conn, new_offsets


def step_convert_ngon_nface_to_offset(f, dry_run):
    """将 NGON_n / NFACE_n 从 3.x 内联格式转换为 4.x 偏移格式。"""
    targets = _collect_ngon_nface_inline(f)

    if not targets:
        print("[NGON/NFACE] 未发现需转换的 3.x 内联格式（或已是 4.x 偏移格式）。")
        return

    for grp in targets:
        path = grp.name
        etype = get_etype(grp)
        conn_node = grp["ElementConnectivity"]
        conn_data = read_data(conn_node)

        if conn_data is None:
            print(f"[NGON/NFACE] {path}: 无法读取 ElementConnectivity，跳过。")
            continue

        try:
            new_conn, new_offsets = _build_offset_format(conn_data)
        except ValueError as exc:
            print(f"[NGON/NFACE] {path}: 转换失败 - {exc}")
            continue

        n_elem = len(new_offsets) - 1
        print(f"[NGON/NFACE] {path} ({etype}): {n_elem} 个元素，内联 -> 偏移格式")

        if dry_run:
            print(f"  -> [预览] 新 conn 长度 {len(new_conn)}，将创建 ElementStartOffset 长度 {len(new_offsets)}")
            continue

        # 写入新 ElementConnectivity 和 ElementStartOffset（保持 CGNS DataArray_t 结构）
        conn_node = grp["ElementConnectivity"]
        if isinstance(conn_node, h5py.Group):
            del conn_node[DATA_DSET]
            conn_node.create_dataset(DATA_DSET, data=new_conn, dtype=np.int64)
        else:
            del grp["ElementConnectivity"]
            grp.create_group("ElementConnectivity").create_dataset(DATA_DSET, data=new_conn, dtype=np.int64)
        if "ElementStartOffset" in grp:
            off_node = grp["ElementStartOffset"]
            if isinstance(off_node, h5py.Group):
                del off_node[DATA_DSET]
                off_node.create_dataset(DATA_DSET, data=new_offsets, dtype=np.int64)
            else:
                del grp["ElementStartOffset"]
                grp.create_group("ElementStartOffset").create_dataset(DATA_DSET, data=new_offsets, dtype=np.int64)
        else:
            grp.create_group("ElementStartOffset").create_dataset(DATA_DSET, data=new_offsets, dtype=np.int64)
        print(f"  -> 转换完成")


# ---------------------------------------------------------------------------
# 步骤 3：int32 连接性数据 -> int64
# ---------------------------------------------------------------------------


def step_upgrade_int64_simple(f, dry_run):
    """将 ElementConnectivity/ElementRange/ElementStartOffset/Zone data 等 int32 升级为 int64。不含 PointList。"""
    to_convert = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Dataset) or obj.dtype not in (np.int32, np.dtype("int32")):
            return
        if not name.endswith("/" + DATA_DSET):
            return
        if "ElementConnectivity" in name or "ElementRange" in name or "ElementStartOffset" in name:
            to_convert.append((obj, name))
        elif "box_vol" in name and "PointList" not in name:
            to_convert.append((obj, name))

    f.visititems(visit)
    seen = set()
    unique = [(obj, p) for obj, p in to_convert if p not in seen and not seen.add(p)]

    if not unique:
        print("[int64] 未发现需升级的 int32 数据集。")
        return

    for ds, path in unique:
        print(f"[int64] {path}")
        if not dry_run:
            data = np.asarray(ds[()], dtype=np.int64)
            parent = ds.parent
            key = ds.name.split("/")[-1]
            del parent[key]
            parent.create_dataset(key, data=data, dtype=np.int64)

    action = "[预览] 将转换" if dry_run else "已转换"
    print(f"[int64] {action} {len(unique)} 个数据集")


# ---------------------------------------------------------------------------
# 步骤 4：PointList shape (n,) -> (n, 1)
# ---------------------------------------------------------------------------


def step_fix_pointlist_shape(f, dry_run):
    """将 ZoneBC 下 PointList 的 data shape 从 (n,) 修正为 (n, 1)。"""
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
        print("[PointList] 未发现需修正的 shape。")
        return

    for pointlist_group, path in to_fix:
        shape = pointlist_group[DATA_DSET].shape
        print(f"[PointList] {path}: {shape} -> ({shape[0]}, 1)")
        if not dry_run:
            ds = pointlist_group[DATA_DSET]
            data = ds[()]
            new_data = np.asarray(data).reshape(-1, 1)
            del pointlist_group[DATA_DSET]
            pointlist_group.create_dataset(DATA_DSET, data=new_data)

    action = "[预览] 将修正" if dry_run else "已修正"
    print(f"[PointList] {action} {len(to_fix)} 个 PointList")


# ---------------------------------------------------------------------------
# 步骤 5：BCType Null/NULL -> BCTypeNull
# ---------------------------------------------------------------------------

BC_TYPE_NULL = "BCTypeNull"


def step_fix_bc_type_null(f, dry_run):
    """将 ZoneBC 下 BCType 的 Null/NULL 改为 BCTypeNull。"""
    to_fix = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Dataset) or "ZoneBC" not in name or not name.endswith("/" + DATA_DSET):
            return
        arr = np.asarray(obj[()])
        if arr.dtype.kind not in ("S", "U", "i", "u") or (hasattr(arr.dtype, "itemsize") and arr.dtype.itemsize != 1):
            return
        s = arr.tobytes().decode("ascii", errors="replace").strip().rstrip("\x00")
        if s.lower() == "null":
            to_fix.append((obj, name))

    f.visititems(visit)

    if not to_fix:
        print("[BCType] 未发现 Null/NULL 类型的 BCType。")
        return

    for ds, path in to_fix:
        print(f"[BCType] {path}: Null -> {BC_TYPE_NULL}")
        if not dry_run:
            new_val = BC_TYPE_NULL.encode("ascii").ljust(32, b"\x00")[:32]
            arr = np.frombuffer(new_val, dtype=np.int8)
            parent = ds.parent
            key = ds.name.split("/")[-1]
            del parent[key]
            parent.create_dataset(key, data=arr, dtype=np.int8)

    action = "[预览] 将修正" if dry_run else "已修正"
    print(f"[BCType] {action} {len(to_fix)} 个 BCType")


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="将 CGNS 文件转换为 CGNS 4.2 标准格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
转换步骤：
  1. 设置 CGNSLibraryVersion = 4.2
  2. NGON_n/NFACE_n：3.x 内联格式 -> 4.x 偏移格式（若适用）
  3. 连接性整数数据 int32 -> int64（不含 PointList）
  4. PointList shape (n,) -> (n, 1)
  5. BCType Null/NULL -> BCTypeNull

示例：
  python upgrade_to_cgns_42.py input.cgns                 # 原地修改
  python upgrade_to_cgns_42.py input.cgns -o output.cgns  # 输出到新文件
  python upgrade_to_cgns_42.py input.cgns -n              # 仅预览
""",
    )
    parser.add_argument("file", help="输入 CGNS/HDF5 文件路径")
    parser.add_argument(
        "-o", "--output", default=None,
        help="输出文件路径（不指定则原地修改）",
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="仅预览，不修改文件",
    )
    args = parser.parse_args()

    input_path = Path(args.file)
    if not input_path.exists():
        print(f"错误：文件不存在: {input_path}")
        sys.exit(1)

    if args.output and not args.dry_run:
        target = Path(args.output)
        shutil.copy2(input_path, target)
        print(f"已复制到: {target}")
    else:
        target = input_path

    mode = "r" if args.dry_run else "r+"
    label = "[预览模式]" if args.dry_run else "[修改模式]"
    print(f"\n{label} 处理文件: {target}\n")

    try:
        with h5py.File(target, mode) as f:
            print("── 步骤 1：设置 CGNSLibraryVersion ──")
            step_set_version(f, args.dry_run)

            print("\n── 步骤 2：NGON_n/NFACE_n 转为 4.x 偏移格式 ──")
            step_convert_ngon_nface_to_offset(f, args.dry_run)

            print("\n── 步骤 3：int32 -> int64 ──")
            step_upgrade_int64_simple(f, args.dry_run)

            print("\n── 步骤 4：PointList shape 修正 ──")
            step_fix_pointlist_shape(f, args.dry_run)

            print("\n── 步骤 5：BCType Null -> BCTypeNull ──")
            step_fix_bc_type_null(f, args.dry_run)

    except OSError as e:
        print(f"\n错误：无法打开文件 '{target}': {e}")
        sys.exit(1)

    print()
    if args.dry_run:
        print("预览完成，未作任何修改。")
    else:
        print(f"转换完成: {target}")


if __name__ == "__main__":
    main()
