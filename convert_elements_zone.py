#!/usr/bin/env python3
"""
将 CGNS 文件中包含 ElementConnectivity、ElementRange、ElementStartOffset 的 Elements_t
转换成只包含 ElementConnectivity、ElementRange 的形式。

按 CGNS 标准正确处理三者关联：
- 固定单元类型（HEXA_8, TETRA_4 等）：ElementConnectivity 已是固定格式，删除 ElementStartOffset
- MIXED：按单元类型拆分为多个同质 Elements_t 段
- NGON_n, NFACE_n：需保留 ElementStartOffset，不予转换
"""

import argparse
import sys

try:
    import h5py
    import numpy as np
except ImportError as e:
    print("请先安装依赖: pip install h5py numpy")
    sys.exit(1)


DATA_DSET = " data"

# CGNS 固定单元类型 -> 每单元节点数 (NPE)
NPE_MAP = {
    "NODE": 1, "BAR_2": 2, "BAR_3": 3, "BAR_4": 4,
    "TRI_3": 3, "TRI_6": 6, "TRI_9": 9, "TRI_10": 10,
    "QUAD_4": 4, "QUAD_8": 8, "QUAD_9": 9, "QUAD_12": 12, "QUAD_16": 16,
    "TETRA_4": 4, "TETRA_10": 10, "TETRA_16": 16, "TETRA_20": 20,
    "PYRA_5": 5, "PYRA_13": 13, "PYRA_14": 14, "PYRA_21": 21, "PYRA_29": 29, "PYRA_30": 30,
    "PENTA_6": 6, "PENTA_15": 15, "PENTA_18": 18, "PENTA_24": 24, "PENTA_38": 38, "PENTA_40": 40,
    "HEXA_8": 8, "HEXA_20": 20, "HEXA_27": 27, "HEXA_32": 32, "HEXA_56": 56, "HEXA_64": 64,
}

# CGNS ElementType 整型到名称的映射 (cgnslib 常用值及扩展)
ETYPE_INT_TO_NAME = {
    2: "NODE", 3: "BAR_2", 4: "BAR_3", 5: "TRI_3", 6: "TRI_6", 7: "QUAD_4", 8: "QUAD_8", 9: "QUAD_9",
    10: "TETRA_4", 11: "TETRA_10", 12: "PYRA_5", 13: "PYRA_14", 14: "PENTA_6", 15: "PENTA_15",
    16: "PENTA_18", 17: "HEXA_8", 18: "HEXA_20", 19: "HEXA_27", 20: "MIXED",
    21: "NGON_n", 22: "NGON_n", 23: "NFACE_n",  # 22/23 为不同实现中的 NGON_n/NFACE_n 编码
}


def get_dataset_value(group, name):
    """获取 group 下名为 name 的节点的 data。支持 group/ data 或直接 dataset。"""
    node = group.get(name)
    if node is None:
        return None
    if isinstance(node, h5py.Dataset):
        return node[()]
    if isinstance(node, h5py.Group) and DATA_DSET in node:
        return node[DATA_DSET][()]
    return None


def _decode_etype_value(arr):
    """从 ElementType 的 data 数组解码为类型名称。"""
    arr = np.asarray(arr)
    if arr.dtype.kind in ("U", "S") or arr.dtype == object:
        s = "".join(c.decode() if hasattr(c, "decode") else str(c) for c in np.ravel(arr))
        return s.strip().rstrip("\x00")
    if arr.size >= 1:
        v = int(arr.flat[0])
        return ETYPE_INT_TO_NAME.get(v, str(v))
    return None


def get_element_type(elements_group):
    """读取 ElementType_t，返回类型名称。支持 ElementType 子节点或 Elements 自身的  data。"""
    # 1. 优先从 ElementType 子节点读取
    et = elements_group.get("ElementType")
    if et is not None:
        data = None
        if isinstance(et, h5py.Group):
            for key in list(et.keys()):
                if key.strip() == "data" or key == DATA_DSET or "data" in key.lower():
                    data = et[key][()]
                    break
        elif isinstance(et, h5py.Dataset):
            data = et[()]
        if data is not None:
            result = _decode_etype_value(data)
            if result:
                return result
    # 2. 部分实现将 ElementType 存于 Elements 自身的  data 首元素（如 ANSA/Cradle 导出）
    data_node = elements_group.get(DATA_DSET)
    if data_node is not None and isinstance(data_node, h5py.Dataset):
        arr = np.asarray(data_node[()])
        if arr.size >= 1 and arr.dtype.kind in ("i", "u"):
            return ETYPE_INT_TO_NAME.get(int(arr.flat[0]))
    return None


def get_element_range(elements_group):
    """返回 (start, end) 或 None。"""
    er = elements_group.get("ElementRange")
    if er is None:
        return None
    data = get_dataset_value(er, DATA_DSET) if isinstance(er, h5py.Group) and DATA_DSET in er.keys() else None
    if data is None:
        if isinstance(er, h5py.Dataset):
            data = er[()]
        elif isinstance(er, h5py.Group):
            for k in er.keys():
                if "data" in k.lower():
                    data = er[k][()]
                    break
    if data is not None and hasattr(data, "__len__") and len(data) >= 2:
        return (int(data[0]), int(data[1]))
    return None


def copy_node(src_parent, dst_parent, name):
    """复制节点（group 或 dataset）到目标 parent。"""
    src = src_parent[name]
    if isinstance(src, h5py.Dataset):
        dst_parent.create_dataset(name, data=src[()], dtype=src.dtype)
    else:
        grp = dst_parent.create_group(name)
        for k, v in src.items():
            if isinstance(v, h5py.Dataset):
                grp.create_dataset(k, data=v[()], dtype=v.dtype)
            else:
                copy_node(src, grp, k)


def convert_fixed_type(elements_group):
    """固定单元类型：校验后删除 ElementStartOffset。"""
    conn_node = elements_group.get("ElementConnectivity")
    if conn_node is None:
        return False, "缺少 ElementConnectivity"
    conn_data = get_dataset_value(conn_node, DATA_DSET) if isinstance(conn_node, h5py.Group) else None
    if conn_data is None and isinstance(conn_node, h5py.Dataset):
        conn_data = conn_node[()]
    if conn_data is None:
        return False, "无法读取 ElementConnectivity"
    conn = np.asarray(conn_data).ravel()

    er = get_element_range(elements_group)
    if er is None:
        return False, "无法读取 ElementRange"
    start, end = er
    n_elem = end - start + 1

    etype = get_element_type(elements_group)
    if etype not in NPE_MAP:
        return False, f"不支持的固定单元类型: {etype}"
    npe = NPE_MAP[etype]
    expected_size = n_elem * npe
    if conn.size != expected_size:
        return False, f"ElementConnectivity 长度 {conn.size} 与 ElementRange/类型不符 (期望 {expected_size})"

    # 删除 ElementStartOffset
    if "ElementStartOffset" in elements_group:
        del elements_group["ElementStartOffset"]
    return True, None


def convert_mixed(elements_group, parent, base_name):
    """MIXED 类型：按单元类型拆分为多个同质 Elements_t。"""
    conn_node = elements_group.get("ElementConnectivity")
    off_node = elements_group.get("ElementStartOffset")
    if conn_node is None or off_node is None:
        return False, "MIXED 缺少 ElementConnectivity 或 ElementStartOffset"
    conn_data = get_dataset_value(conn_node, DATA_DSET)
    if conn_data is None and isinstance(conn_node, h5py.Dataset):
        conn_data = conn_node[()]
    off_data = get_dataset_value(off_node, DATA_DSET)
    if off_data is None and isinstance(off_node, h5py.Dataset):
        off_data = off_node[()]
    if conn_data is None or off_data is None:
        return False, "无法读取 ElementConnectivity 或 ElementStartOffset"
    conn = np.asarray(conn_data).ravel()
    offset = np.asarray(off_data).ravel()

    er = get_element_range(elements_group)
    if er is None:
        return False, "无法读取 ElementRange"
    start, end = er
    n_elem = end - start + 1
    if offset.size != n_elem + 1:
        return False, f"ElementStartOffset 长度与 ElementRange 不符"

    # 按类型分组
    by_type = {}
    for i in range(n_elem):
        pos = int(offset[i])
        etype_int = int(conn[pos])
        etype = ETYPE_INT_TO_NAME.get(etype_int) or str(etype_int)
        if etype not in NPE_MAP:
            return False, f"未知单元类型: {etype_int}"
        npe = NPE_MAP[etype]
        block = conn[pos + 1 : pos + 1 + npe]
        if etype not in by_type:
            by_type[etype] = []
        by_type[etype].append((start + i, block))

    if not by_type:
        return False, "无有效单元数据"

    # 创建新的 Elements_t 段
    next_elem = start
    for etype, items in sorted(by_type.items()):
        items.sort(key=lambda x: x[0])
        elem_range = (items[0][0], items[-1][0])
        conn_flat = np.concatenate([b for _, b in items]).astype(conn.dtype)
        name = f"{base_name}_{etype}"
        idx = 0
        while name in parent:
            idx += 1
            name = f"{base_name}_{etype}_{idx}"
        new_grp = parent.create_group(name)
        new_grp.attrs.update(elements_group.attrs)
        # ElementRange
        er_grp = new_grp.create_group("ElementRange")
        er_grp.create_dataset(DATA_DSET, data=np.array([elem_range[0], elem_range[1]], dtype=np.int32))
        # ElementType
        et_grp = new_grp.create_group("ElementType")
        et_grp.create_dataset(DATA_DSET, data=np.array(etype, dtype="S"))
        # ElementConnectivity
        conn_grp = new_grp.create_group("ElementConnectivity")
        conn_grp.create_dataset(DATA_DSET, data=conn_flat)
        next_elem = elem_range[1] + 1

    # 删除原 MIXED 段
    del parent[elements_group.name.split("/")[-1]]
    return True, None


def has_elements_structure(group):
    """检查是否包含三字段。"""
    keys = set(group.keys())
    return (
        "ElementConnectivity" in keys
        and "ElementRange" in keys
        and "ElementStartOffset" in keys
    )


def collect_elements_to_convert(f):
    """收集需转换的 Elements group。"""
    result = []

    def visit(name, obj):
        if isinstance(obj, h5py.Group) and has_elements_structure(obj):
            parent_path = "/".join(obj.name.split("/")[:-1])
            parent = f[parent_path] if parent_path else f
            result.append((obj, parent))

    f.visititems(visit)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="按 CGNS 标准将 Elements_t 从带 ElementStartOffset 转为仅 ElementConnectivity+ElementRange"
    )
    parser.add_argument("file", help="CGNS/HDF5 文件路径")
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="仅列出将处理的 group，不实际修改",
    )
    args = parser.parse_args()

    try:
        with h5py.File(args.file, "r+" if not args.dry_run else "r") as f:
            to_convert = collect_elements_to_convert(f)
            if not to_convert:
                print("未发现包含 ElementConnectivity、ElementRange、ElementStartOffset 的 Elements group。")
                return

            for elements_group, parent in to_convert:
                path = elements_group.name
                etype = get_element_type(elements_group)
                base_name = path.split("/")[-1]

                if args.dry_run:
                    print(f"  {path}  ElementType={etype}")
                    continue

                if etype in ("NGON_n", "NFACE_n"):
                    print(f"Skip {path}: {etype} requires ElementStartOffset per CGNS standard, cannot convert.")
                    continue

                if etype == "MIXED":
                    ok, err = convert_mixed(elements_group, parent, base_name)
                else:
                    ok, err = convert_fixed_type(elements_group)

                if ok:
                    print(f"已转换: {path}")
                else:
                    print(f"转换失败 {path}: {err}")

    except OSError as e:
        print(f"无法打开文件 '{args.file}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
