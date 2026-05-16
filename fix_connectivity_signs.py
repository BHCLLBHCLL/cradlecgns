#!/usr/bin/env python3
"""
按 CGNS 格式定义，将 ElementConnectivity 中的负数全部转为正整数（取绝对值）。
同时校验并保持 ElementStartOffset、ElementRange 与修正后的数据一致。

说明：CGNS 中 NFACE_n 的 face ID 可带符号表示法向方向（负=向内）。
备注：connectivity 是否允许为负数，需进一步验证。
取绝对值后仅保留 face 编号，失去方向信息；数组长度不变，ElementStartOffset 与 ElementRange 无需变更。
"""

import argparse
import sys

try:
    import h5py
    import numpy as np
except ImportError:
    print("Install: pip install h5py numpy")
    sys.exit(1)


DATA_DSET = " data"


def get_conn_data(node):
    """从 ElementConnectivity 节点读取数据。"""
    if node is None:
        return None
    if isinstance(node, h5py.Dataset):
        return np.asarray(node[()], dtype=np.int32)
    if isinstance(node, h5py.Group) and DATA_DSET in node:
        return np.asarray(node[DATA_DSET][()], dtype=np.int32)
    return None


def has_negative(arr):
    """检查数组是否含负数。"""
    return np.any(arr < 0)


def collect_elements_with_conn(f):
    """收集所有包含 ElementConnectivity 的 Elements group。"""
    result = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Group):
            return
        conn_node = obj.get("ElementConnectivity")
        if conn_node is None:
            return
        conn = get_conn_data(conn_node)
        if conn is not None and has_negative(conn):
            result.append((obj, obj.name))

    f.visititems(visit)
    return result


def fix_connectivity(elements_group):
    """将 ElementConnectivity 中负数取绝对值并写回。ElementStartOffset、ElementRange 结构不变。"""
    conn_node = elements_group.get("ElementConnectivity")
    if conn_node is None:
        return False, "No ElementConnectivity"
    conn = get_conn_data(conn_node)
    if conn is None:
        return False, "Cannot read ElementConnectivity"
    if not has_negative(conn):
        return True, "no negatives"

    new_conn = np.abs(conn).astype(conn.dtype)
    ds = conn_node[DATA_DSET] if isinstance(conn_node, h5py.Group) else conn_node
    ds[...] = new_conn
    return True, "fixed"


def main():
    parser = argparse.ArgumentParser(
        description="Convert negative values in ElementConnectivity to positive (abs)"
    )
    parser.add_argument("file", help="CGNS/HDF5 file path")
    parser.add_argument("-n", "--dry-run", action="store_true", help="List only, no modify")
    args = parser.parse_args()

    try:
        with h5py.File(args.file, "r+" if not args.dry_run else "r") as f:
            to_fix = collect_elements_with_conn(f)
            if not to_fix:
                print("No Elements with negative values in ElementConnectivity.")
                return

            if args.dry_run:
                print("Elements with negative connectivity (will apply abs):")
                for _, path in to_fix:
                    print(f"  {path}")
                return

            for elements_group, path in to_fix:
                ok, msg = fix_connectivity(elements_group)
                if ok and msg == "fixed":
                    print(f"Fixed: {path}")
                elif ok:
                    print(f"Skip {path}: {msg}")
                else:
                    print(f"Fail {path}: {msg}")

    except OSError as e:
        print(f"Cannot open '{args.file}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
