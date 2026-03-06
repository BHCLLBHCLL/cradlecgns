#!/usr/bin/env python3
"""
将 CGNS 文件中包含 ElementConnectivity、ElementRange、ElementStartOffset 三个子 group 的
Elements_t Zone 转换成只包含 ElementConnectivity、ElementRange 的形式（删除 ElementStartOffset）。
"""

import argparse
import sys

try:
    import h5py
except ImportError:
    print("请先安装 h5py: pip install h5py")
    sys.exit(1)


TO_REMOVE = "ElementStartOffset"


def has_elements_structure(group):
    """检查 group 是否包含 ElementConnectivity、ElementRange、ElementStartOffset。"""
    keys = set(group.keys())
    return (
        "ElementConnectivity" in keys
        and "ElementRange" in keys
        and "ElementStartOffset" in keys
    )


def collect_elements_to_convert(f):
    """收集需转换的 Elements group。返回 [(parent_group, path), ...]"""
    to_convert = []

    def visit(name, obj):
        if isinstance(obj, h5py.Group) and has_elements_structure(obj):
            to_convert.append((obj, obj.name))

    f.visititems(visit)
    return to_convert


def remove_element_start_offset(elements_group):
    """从 Elements group 中删除 ElementStartOffset。"""
    del elements_group[TO_REMOVE]


def main():
    parser = argparse.ArgumentParser(
        description="删除 Elements_t Zone 中的 ElementStartOffset 子 group"
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

            if args.dry_run:
                print("以下 Elements group 将被转换（删除 ElementStartOffset）:")
                for _, path in to_convert:
                    print(f"  {path}")
                return

            for elements_group, path in to_convert:
                remove_element_start_offset(elements_group)
                print(f"已删除: {path}/{TO_REMOVE}")

    except OSError as e:
        print(f"无法打开文件 '{args.file}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
