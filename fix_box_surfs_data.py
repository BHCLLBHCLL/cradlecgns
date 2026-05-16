#!/usr/bin/env python3
"""Copy ZoneBC/box_surfs/ data from box_ngons.cgns into box_ansa.cgns."""

import sys

try:
    import h5py
    import numpy as np
except ImportError:
    print("pip install h5py numpy")
    sys.exit(1)

DATA_DSET = " data"


def main():
    ansa_path = "box_ansa.cgns"
    ngons_path = "box_ngons.cgns"
    if len(sys.argv) >= 2:
        ansa_path = sys.argv[1]
    if len(sys.argv) >= 3:
        ngons_path = sys.argv[2]

    with h5py.File(ngons_path, "r") as f_src:
        path = "Base/box_vol/ZoneBC/box_surfs"
        if path not in f_src:
            print(f"Path {path} not found in {ngons_path}")
            sys.exit(1)
        data = f_src[f"{path}/{DATA_DSET}"][()]
        data = np.asarray(data, dtype=np.int8)

    with h5py.File(ansa_path, "r+") as f_dst:
        grp_path = f"{path}"
        if grp_path not in f_dst:
            print(f"Path {grp_path} not found in {ansa_path}")
            sys.exit(1)
        grp = f_dst[grp_path]
        if DATA_DSET in grp:
            del grp[DATA_DSET]
        grp.create_dataset(DATA_DSET, data=data, dtype=data.dtype)

    print(f"Updated {ansa_path} ZoneBC/box_surfs/ data from {ngons_path}")
    print(f"  New value: {data.tobytes().decode('ascii', errors='replace')!r}")


if __name__ == "__main__":
    main()
