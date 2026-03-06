#!/usr/bin/env python3
"""
使用 h5py 查看 HDF5 格式 CGNS 文件中各 dataset 的 shape。
"""

import argparse
import sys

try:
    import h5py
except ImportError:
    print("请先安装 h5py: pip install h5py")
    sys.exit(1)


def print_dataset_shapes(name, obj):
    """遍历 HDF5 对象，打印 dataset 的 name 和 shape。"""
    if isinstance(obj, h5py.Dataset):
        print(f"  {name}: shape={obj.shape}  dtype={obj.dtype}")


def main():
    parser = argparse.ArgumentParser(description="查看 CGNS/HDF5 文件中 dataset 的 shape")
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="CGNS/HDF5 文件路径",
    )
    args = parser.parse_args()

    if args.file is None:
        parser.print_help()
        print("\n示例: python view_cgns_shapes.py your_file.cgns")
        sys.exit(1)

    try:
        with h5py.File(args.file, "r") as f:
            print(f"文件: {args.file}\n")
            print("Dataset 列表 (name: shape, dtype):")
            print("-" * 60)
            f.visititems(lambda name, obj: print_dataset_shapes(name, obj))
    except OSError as e:
        print(f"无法打开文件 '{args.file}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
