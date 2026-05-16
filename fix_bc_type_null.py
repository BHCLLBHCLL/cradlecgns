#!/usr/bin/env python3
"""Fix ZoneBC BCType: replace Null/NULL with BCTypeNull per CGNS BCType_t."""

import argparse
import sys

try:
    import h5py
    import numpy as np
except ImportError:
    print("pip install h5py numpy")
    sys.exit(1)

DATA_DSET = " data"
BC_TYPE_NULL = "BCTypeNull"


def is_null_type(arr):
    """Check if BCType data represents Null/NULL."""
    s = arr.tobytes().decode("ascii", errors="replace").strip().rstrip("\x00")
    return s.lower() in ("null",)


def collect_bc_with_null(f):
    """Collect ZoneBC/*/ data that equals Null/NULL."""
    result = []

    def visit(name, obj):
        if not isinstance(obj, h5py.Dataset):
            return
        if "ZoneBC" not in name:
            return
        if not name.endswith("/" + DATA_DSET):
            return
        # BC group's data = BCType; parent of data is the BC group
        arr = np.asarray(obj[()])
        if arr.dtype.kind not in ("S", "U", "i", "u") or arr.dtype.itemsize != 1:
            return
        s = arr.tobytes().decode("ascii", errors="replace").strip().rstrip("\x00")
        if s.lower() == "null":
            result.append((obj, name))

    f.visititems(visit)
    return result


def fix_one(ds, path):
    """Replace Null with BCTypeNull."""
    # Use at least 32 chars (CGNS convention), pad with null bytes
    new_val = BC_TYPE_NULL.encode("ascii").ljust(32, b"\x00")[:32]
    arr = np.frombuffer(new_val, dtype=np.int8)
    parent = ds.parent
    name = ds.name.split("/")[-1]
    del parent[name]
    parent.create_dataset(name, data=arr, dtype=np.int8)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Replace BCType Null/NULL with BCTypeNull (CGNS BCType_t)"
    )
    parser.add_argument("file", help="CGNS/HDF5 file path")
    parser.add_argument("-n", "--dry-run", action="store_true", help="List only")
    args = parser.parse_args()

    with h5py.File(args.file, "r+" if not args.dry_run else "r") as f:
        to_fix = collect_bc_with_null(f)
        if not to_fix:
            print("No ZoneBC BCType with Null/NULL found.")
            return

        if args.dry_run:
            print("Will replace Null -> BCTypeNull:")
            for _, path in to_fix:
                print(" ", path)
            return

        for ds, path in to_fix:
            fix_one(ds, path)
            print(f"Fixed: {path} -> {BC_TYPE_NULL}")


if __name__ == "__main__":
    main()
