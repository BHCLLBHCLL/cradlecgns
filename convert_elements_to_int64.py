#!/usr/bin/env python3
"""Convert ElementConnectivity, ElementRange, ElementStartOffset, Zone data to int64.
PointList 不强制转为 int64。
备注：数据类型是否必须为 64 位，需进一步验证。"""

import argparse
import sys

try:
    import h5py
    import numpy as np
except ImportError:
    print("pip install h5py numpy")
    sys.exit(1)

DATA_DSET = " data"
NAMES = ("ElementConnectivity", "ElementRange", "ElementStartOffset")


def collect_datasets(f):
    """Collect paths of target datasets that are int32."""
    result = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Dataset):
            return
        path = name
        parent_name = path.rsplit("/", 1)[0] if "/" in path else ""
        tail = path.rsplit("/", 1)[-1]
        if tail != DATA_DSET and tail != " data":
            return
        # ElementConnectivity, ElementRange, ElementStartOffset
        for n in NAMES:
            if f"{n}/{DATA_DSET}" in path or (tail == DATA_DSET and n in parent_name):
                if obj.dtype in (np.int32, np.dtype("int32")):
                    result.append((obj, path))
                return
        # Base/box_vol/ data（不含 PointList）
        if path.endswith("/ data") and obj.dtype in (np.int32, np.dtype("int32")):
            if "box_vol" in path and path.count("/") == 2 and "PointList" not in path:
                result.append((obj, path))

    f.visititems(visit)
    return result


def convert_one(ds, path):
    """Convert dataset to int64. Returns True on success."""
    data = np.asarray(ds[()], dtype=np.int64)
    parent = ds.parent
    name = ds.name.split("/")[-1]
    del parent[name]
    parent.create_dataset(name, data=data, dtype=np.int64)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Convert ElementConnectivity/ElementRange/ElementStartOffset/Zone data to int64 (excludes PointList)"
    )
    parser.add_argument("file", nargs="?", default="box_ansa.cgns", help="CGNS file")
    parser.add_argument("-n", "--dry-run", action="store_true", help="List only")
    args = parser.parse_args()

    with h5py.File(args.file, "r+" if not args.dry_run else "r") as f:
        to_convert = collect_datasets(f)
        if not to_convert:
            print("No int32 ElementConnectivity/ElementRange/ElementStartOffset found.")
            return

        if args.dry_run:
            print("Will convert to int64:")
            for _, path in to_convert:
                print(" ", path)
            return

        for ds, path in to_convert:
            convert_one(ds, path)
            print("Converted:", path)

    print(f"Done. {len(to_convert)} datasets converted to int64.")


if __name__ == "__main__":
    main()
