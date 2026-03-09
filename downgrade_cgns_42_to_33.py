#!/usr/bin/env python3
"""
将 CGNS 4.2 格式文件向下转换为 CGNS 3.3 格式。

CGNS 4.x 与 3.x 的主要差异：
  - CGNS 4.0 起，NGON_n 和 NFACE_n 的 ElementConnectivity 采用偏移数组格式
    （配合 ElementStartOffset），而 CGNS 3.x 使用内联计数格式（无 ElementStartOffset）。
  - CGNS 4.x 引入了 int64 大整数支持，CGNS 3.3 使用 int32。

本脚本执行以下三步转换：
  1. CGNSLibraryVersion 降为 3.3
  2. NGON_n / NFACE_n：偏移格式 -> 内联计数格式，并删除 ElementStartOffset
  3. int64 连接性数据 -> int32（可用 --keep-int64 跳过）

用法：
  python downgrade_cgns_42_to_33.py mesh.cgns              # 原地修改
  python downgrade_cgns_42_to_33.py mesh.cgns -o out.cgns  # 输出到新文件
  python downgrade_cgns_42_to_33.py mesh.cgns -n           # 仅预览，不修改
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
TARGET_VERSION = 3.3

# CGNS 整型 ElementType 编号 -> 名称（含多版本中 NGON/NFACE 的不同编码）
ETYPE_INT_TO_NAME = {
    2: "NODE",
    3: "BAR_2", 4: "BAR_3",
    5: "TRI_3", 6: "TRI_6",
    7: "QUAD_4", 8: "QUAD_8", 9: "QUAD_9",
    10: "TETRA_4", 11: "TETRA_10",
    12: "PYRA_5", 13: "PYRA_14",
    14: "PENTA_6", 15: "PENTA_15", 16: "PENTA_18",
    17: "HEXA_8", 18: "HEXA_20", 19: "HEXA_27",
    20: "MIXED",
    21: "NGON_n", 22: "NGON_n",   # 不同实现/版本中的编码差异
    23: "NFACE_n",
}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def read_data(node):
    """从 Group（含 ' data' 子集）或 Dataset 直接读取数组数据。"""
    if isinstance(node, h5py.Dataset):
        return node[()]
    if isinstance(node, h5py.Group) and DATA_DSET in node:
        return node[DATA_DSET][()]
    return None


def decode_etype(arr):
    """从 ElementType 的 data 数组解析类型名称（支持字符串或整型编码）。"""
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
    """
    从 Elements_t Group 中读取元素类型名称。
    优先读取 ElementType 子节点；其次读取 Elements 自身 ' data' 首元素（ANSA/Cradle 风格）。
    """
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


def replace_data_in_node(node, new_array):
    """
    将 Group 的 ' data' 子集或 Dataset 自身替换为 new_array。
    返回实际完成写入的父对象和键名，供调用方确认。
    """
    if isinstance(node, h5py.Group):
        del node[DATA_DSET]
        node.create_dataset(DATA_DSET, data=new_array)
    else:
        parent = node.parent
        key = node.name.split("/")[-1]
        del parent[key]
        parent.create_dataset(key, data=new_array)


# ---------------------------------------------------------------------------
# 步骤 1：设置 CGNSLibraryVersion
# ---------------------------------------------------------------------------

def step_set_version(f, dry_run):
    """将 CGNSLibraryVersion 设置为 3.3。"""
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
# 步骤 2：NGON_n / NFACE_n 偏移格式 -> 内联计数格式
# ---------------------------------------------------------------------------

def _collect_ngon_nface_groups(f):
    """
    收集同时包含 ElementConnectivity 和 ElementStartOffset 的
    NGON_n / NFACE_n 类型的 Elements_t Group。
    """
    results = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Group):
            return
        keys = set(obj.keys())
        if "ElementConnectivity" not in keys or "ElementStartOffset" not in keys:
            return
        etype = get_etype(obj)
        if etype in ("NGON_n", "NFACE_n"):
            results.append(obj)

    f.visititems(visit)
    return results


def _build_inline_conn(conn4x, offsets):
    """
    将 CGNS 4.x 偏移格式转换为 CGNS 3.x 内联计数格式。

    CGNS 4.x：
      ElementConnectivity = [v0, v1, ..., v0, v1, ...]  （纯顶点/面 ID）
      ElementStartOffset  = [0, n0, n0+n1, ...]          （累积偏移，长度=n_elem+1）

    CGNS 3.x：
      ElementConnectivity = [n0, v0, v1, ..., n1, v0, v1, ...]  （嵌入每元素顶点/面数）

    NFACE_n 中面 ID 可为负数（表示反向），绝对值不超过 int32 最大值时可正常转换。
    """
    conn4x = np.asarray(conn4x).ravel()
    offsets = np.asarray(offsets).ravel()
    n_elem = len(offsets) - 1

    parts = []
    for i in range(n_elem):
        s = int(offsets[i])
        e = int(offsets[i + 1])
        nv = e - s
        parts.append(np.array([nv], dtype=np.int32))
        seg = conn4x[s:e]
        # 检查 int32 范围（含负数，用于 NFACE_n 的方向符号）
        seg_min = int(seg.min()) if seg.size > 0 else 0
        seg_max = int(seg.max()) if seg.size > 0 else 0
        i32_min = np.iinfo(np.int32).min
        i32_max = np.iinfo(np.int32).max
        if seg_min < i32_min or seg_max > i32_max:
            raise OverflowError(
                f"元素 {i} 的 ID 值 [{seg_min}, {seg_max}] 超出 int32 范围，"
                "无法降级为 3.3 格式。"
            )
        parts.append(seg.astype(np.int32))

    if not parts:
        return np.array([], dtype=np.int32)
    return np.concatenate(parts)


def step_convert_ngon_nface(f, dry_run):
    """
    将 NGON_n / NFACE_n 的连接性数组从 CGNS 4.x 偏移格式转换为 3.x 内联格式，
    并删除 ElementStartOffset 节点。
    """
    targets = _collect_ngon_nface_groups(f)

    if not targets:
        print("[NGON/NFACE] 未发现需要转换的 NGON_n / NFACE_n 节点（或已是 3.x 格式）。")
        return

    for grp in targets:
        path = grp.name
        etype = get_etype(grp)

        conn_node = grp["ElementConnectivity"]
        off_node = grp["ElementStartOffset"]

        conn_data = read_data(conn_node)
        off_data = read_data(off_node)

        if conn_data is None or off_data is None:
            print(f"[NGON/NFACE] {path}: 无法读取 ElementConnectivity 或 ElementStartOffset，跳过。")
            continue

        offsets = np.asarray(off_data).ravel()
        n_elem = len(offsets) - 1
        old_conn_size = len(np.asarray(conn_data).ravel())

        print(
            f"[NGON/NFACE] {path} ({etype}): "
            f"{n_elem} 个元素，原始 conn 长度 {old_conn_size}"
        )

        if dry_run:
            # 仅估算新数组大小
            estimated_new_size = old_conn_size + n_elem
            print(f"  -> [预览] 新 conn 长度约 {estimated_new_size}，将删除 ElementStartOffset")
            continue

        try:
            new_conn = _build_inline_conn(conn_data, offsets)
        except OverflowError as exc:
            print(f"  -> 转换失败: {exc}")
            continue

        replace_data_in_node(conn_node, new_conn)
        del grp["ElementStartOffset"]
        print(f"  -> 转换完成，新 conn 长度 {len(new_conn)}，已删除 ElementStartOffset")


# ---------------------------------------------------------------------------
# 步骤 3：int64 连接性数据降级为 int32
# ---------------------------------------------------------------------------

_CONN_PARENT_NAMES = frozenset({
    "ElementConnectivity",
    "ElementRange",
    "ElementStartOffset",
    "PointList",
    "PointRange",
})


def step_downgrade_int64(f, dry_run):
    """
    将 ElementConnectivity、ElementRange、PointList 等连接性节点中的 int64
    数据集降级为 int32。仅当值域在 int32 范围内时转换；否则输出警告并跳过。
    """
    i32_min = int(np.iinfo(np.int32).min)
    i32_max = int(np.iinfo(np.int32).max)

    converted = []
    skipped = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Dataset):
            return
        if obj.dtype != np.int64:
            return
        # 只处理 ' data' 子集
        tail = name.rsplit("/", 1)[-1]
        if tail != DATA_DSET:
            return
        # 父节点名称需在目标集合中
        parent_key = name.rsplit("/", 1)[0].rsplit("/", 1)[-1] if "/" in name else ""
        if parent_key not in _CONN_PARENT_NAMES:
            return

        arr = obj[()].ravel()
        vmin, vmax = int(arr.min()), int(arr.max())
        if vmin < i32_min or vmax > i32_max:
            skipped.append((name, vmin, vmax))
            return
        converted.append((obj, name))

    f.visititems(visit)

    if not converted and not skipped:
        print("[int64->int32] 未发现 int64 连接性数据集。")
        return

    for ds, path in converted:
        data = ds[()]
        print(f"[int64->int32] {path}")
        if not dry_run:
            new_data = data.astype(np.int32)
            parent = ds.parent
            key = ds.name.split("/")[-1]
            del parent[key]
            parent.create_dataset(key, data=new_data, dtype=np.int32)

    for path, vmin, vmax in skipped:
        print(
            f"[int64->int32] 跳过 {path}：值域 [{vmin}, {vmax}] 超出 int32 范围，"
            "保留 int64。"
        )

    action = "[预览] 将转换" if dry_run else "已转换"
    print(
        f"[int64->int32] {action} {len(converted)} 个数据集，"
        f"跳过 {len(skipped)} 个（值域超范围）。"
    )


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="将 CGNS 4.2 文件向下转换为 CGNS 3.3 格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
转换内容：
  1. CGNSLibraryVersion 降为 3.3
  2. NGON_n / NFACE_n：ElementStartOffset 偏移格式 -> 内联计数格式
  3. int64 连接性数据 -> int32（可用 --keep-int64 跳过此步骤）

示例：
  python downgrade_cgns_42_to_33.py mesh.cgns              # 原地修改
  python downgrade_cgns_42_to_33.py mesh.cgns -o out.cgns  # 保存到新文件
  python downgrade_cgns_42_to_33.py mesh.cgns -n           # 仅预览，不修改
  python downgrade_cgns_42_to_33.py mesh.cgns --keep-int64 # 跳过 int64 降级
""",
    )
    parser.add_argument("file", help="输入 CGNS/HDF5 文件路径")
    parser.add_argument(
        "-o", "--output", default=None,
        help="输出文件路径（不指定则原地修改输入文件）",
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="仅预览将要执行的操作，不实际修改文件",
    )
    parser.add_argument(
        "--keep-int64", action="store_true",
        help="跳过 int64 -> int32 降级步骤",
    )
    args = parser.parse_args()

    input_path = Path(args.file)
    if not input_path.exists():
        print(f"错误：文件不存在: {input_path}")
        sys.exit(1)

    # 确定目标文件
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

            print("\n── 步骤 2：转换 NGON_n / NFACE_n 连接性格式 ──")
            step_convert_ngon_nface(f, args.dry_run)

            print("\n── 步骤 3：int64 连接性数据降级为 int32 ──")
            if args.keep_int64:
                print("[int64->int32] 已跳过（--keep-int64）。")
            else:
                step_downgrade_int64(f, args.dry_run)

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
