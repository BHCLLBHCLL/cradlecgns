#!/usr/bin/env python3
"""Dump HDF5 group/dataset structure and attributes for two ZoneBC groups."""

import sys
from pathlib import Path

import h5py
import numpy as np

DATA_DSET = " data"


def dump_node(name, obj, indent=0):
    pref = "  " * indent
    if isinstance(obj, h5py.Group):
        print(f"{pref}Group: {name}")
        for k, v in obj.attrs.items():
            print(f"{pref}  @attr {k}: {v}")
        for key in obj.keys():
            dump_node(key, obj[key], indent + 1)
    elif isinstance(obj, h5py.Dataset):
        arr = obj[()]
        print(f"{pref}Dataset: {name} shape={obj.shape} dtype={obj.dtype}")
        for k, v in obj.attrs.items():
            print(f"{pref}  @attr {k}: {v}")
        if arr.size <= 32:
            print(f"{pref}  raw: {arr.tobytes().hex()}")
            if obj.dtype.kind in ("S", "U", "i", "u") and obj.dtype.itemsize == 1:
                print(f"{pref}  ascii: {repr(arr.tobytes().decode('ascii', errors='replace'))}")
        else:
            print(f"{pref}  raw (first 64 bytes hex): {arr.reshape(-1)[:64].tobytes().hex()}")


def main():
    if len(sys.argv) < 4:
        print("Usage: python inspect_bc_hdf5_headers.py file.cgns /path/BC1 /path/BC2")
        sys.exit(1)
    fn = Path(sys.argv[1])
    path1, path2 = sys.argv[2], sys.argv[3]
    if not fn.exists():
        print("File not found:", fn)
        sys.exit(1)

    with h5py.File(fn, "r") as f:
        for label, path in [("Rotate_Cylinder", path1), ("Rotate_Cylinder_Moving", path2)]:
            print("\n" + "=" * 60)
            print(f"BC: {label}  path={path}")
            print("=" * 60)
            if path not in f:
                print("  [NOT FOUND]")
                continue
            g = f[path]
            dump_node(path.split("/")[-1], g)


if __name__ == "__main__":
    main()
