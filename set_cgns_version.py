#!/usr/bin/env python3
"""Set CGNSLibraryVersion to 4.2 for Star-CCM+ and ANSA compatibility."""

import argparse
import sys

try:
    import h5py
    import numpy as np
except ImportError:
    print("pip install h5py numpy")
    sys.exit(1)

DATA_DSET = " data"
TARGET_VERSION = 4.2


def main():
    parser = argparse.ArgumentParser(
        description="Set CGNSLibraryVersion to 4.2 (Star-CCM+, ANSA compatible)"
    )
    parser.add_argument("file", help="CGNS/HDF5 file path")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Print current version only")
    args = parser.parse_args()

    with h5py.File(args.file, "r+" if not args.dry_run else "r") as f:
        name = "CGNSLibraryVersion"
        if name not in f:
            if args.dry_run:
                print(f"No {name} in file.")
                return
            grp = f.create_group(name)
            grp.create_dataset(DATA_DSET, data=np.array([TARGET_VERSION], dtype=np.float32))
            print(f"Created {name} = {TARGET_VERSION}")
            return

        grp = f[name]
        if DATA_DSET not in grp:
            if args.dry_run:
                print(f"{name} exists but has no data.")
                return
            grp.create_dataset(DATA_DSET, data=np.array([TARGET_VERSION], dtype=np.float32))
            print(f"Created {name}/ data = {TARGET_VERSION}")
            return

        ds = grp[DATA_DSET]
        current = float(ds[()].flat[0])
        if args.dry_run:
            print(f"Current {name}: {current}")
            return

        if current == TARGET_VERSION:
            print(f"{name} already {TARGET_VERSION}")
            return

        del grp[DATA_DSET]
        grp.create_dataset(DATA_DSET, data=np.array([TARGET_VERSION], dtype=np.float32))
        print(f"Updated {name}: {current} -> {TARGET_VERSION}")


if __name__ == "__main__":
    main()
