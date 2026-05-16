#!/usr/bin/env python3
"""
将 CGNS 文件中 ZoneBC 下各边界条件的 PointList group 下名为 " data" 的 dataset
的 shape 从 (n,) 修正为 (n, 1)。
"""

import argparse
import sys

try:
    import h5py
except ImportError:
    print("请先安装 h5py: pip install h5py")
    sys.exit(1)


DATA_DSET = " data"  # PointList group 下的 dataset 名称


def collect_pointlists_to_fix(f):
    """收集 ZoneBC 下 PointList/ data 中 shape 为 (n,) 的 dataset。返回 [(pointlist_group, path), ...]"""
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
    return to_fix


def fix_data_dataset(pointlist_group):
    """将 PointList group 下的 " data" dataset 从 (n,) 修正为 (n, 1)。"""
    ds = pointlist_group[DATA_DSET]
    data = ds[()]
    new_data = data.reshape(-1, 1)
    del pointlist_group[DATA_DSET]
    pointlist_group.create_dataset(DATA_DSET, data=new_data)


def main():
    parser = argparse.ArgumentParser(
        description='将 ZoneBC 下 PointList 内 " data" 的 shape 从 (n,) 修正为 (n, 1)'
    )
    parser.add_argument("file", help="CGNS/HDF5 文件路径")
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="仅列出需要修正的 PointList，不实际修改",
    )
    args = parser.parse_args()

    try:
        with h5py.File(args.file, "r+" if not args.dry_run else "r") as f:
            if args.dry_run:
                to_fix = collect_pointlists_to_fix(f)
                if to_fix:
                    print('以下 PointList/" data" 将被修正为 (n, 1):')
                    for pointlist_group, path in to_fix:
                        shape = pointlist_group[DATA_DSET].shape
                        print(f"  {path}: {shape} -> ({shape[0]}, 1)")
                else:
                    print('未发现需要修正的 PointList/" data"。')
                return

            to_fix = collect_pointlists_to_fix(f)
            if to_fix:
                for pointlist_group, path in to_fix:
                    fix_data_dataset(pointlist_group)
                print("已修正以下 PointList:")
                for _, path in to_fix:
                    print(f"  {path}")
            else:
                print('未发现需要修正的 PointList/" data"。')

    except OSError as e:
        print(f"无法打开文件 '{args.file}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
