#!/usr/bin/env python3
"""Compare two CGNS files and identify potential memory-error risks."""

import sys
from pathlib import Path

try:
    import h5py
    import numpy as np
except ImportError:
    print("pip install h5py numpy")
    sys.exit(1)

DATA_DSET = " data"


def collect_info(f, prefix=""):
    """Return dict: path -> {shape, dtype, has_negative, sample}."""
    info = {}

    def visit(name, obj):
        path = name
        if isinstance(obj, h5py.Dataset):
            d = {"shape": obj.shape, "dtype": str(obj.dtype)}
            arr = obj[()]
            a = np.asarray(arr)
            if a.dtype.kind in ("i", "u"):
                neg = np.any(a < 0)
                d["has_negative"] = neg
                if a.size <= 32:
                    d["sample"] = a.tolist()
            info[path] = d

    f.visititems(visit)
    return info


def compare(path_a, path_b):
    """Compare two CGNS files and report differences."""
    with h5py.File(path_a, "r") as fa, h5py.File(path_b, "r") as fb:
        ia = collect_info(fa)
        ib = collect_info(fb)

    only_a = set(ia) - set(ib)
    only_b = set(ib) - set(ia)
    common = set(ia) & set(ib)

    print("=" * 70)
    print("1. STRUCTURE DIFFERENCES")
    print("=" * 70)
    if only_a:
        print("\nOnly in", path_a)
        for p in sorted(only_a)[:30]:
            print("  ", p)
        if len(only_a) > 30:
            print("  ... and", len(only_a) - 30, "more")
    if only_b:
        print("\nOnly in", path_b)
        for p in sorted(only_b)[:30]:
            print("  ", p)
        if len(only_b) > 30:
            print("  ... and", len(only_b) - 30, "more")

    print("\n" + "=" * 70)
    print("2. SHAPE/DTYPE DIFFERENCES (common paths)")
    print("=" * 70)
    shape_diff = []
    for p in sorted(common):
        sa, sb = ia[p]["shape"], ib[p]["shape"]
        da, db = ia[p]["dtype"], ib[p]["dtype"]
        if sa != sb or da != db:
            shape_diff.append((p, sa, sb, da, db))
    for p, sa, sb, da, db in shape_diff[:50]:
        print(f"\n  {p}")
        print(f"    ansa:  shape={sa} dtype={da}")
        print(f"    ngons: shape={sb} dtype={db}")
    if len(shape_diff) > 50:
        print("\n  ... and", len(shape_diff) - 50, "more")
    if not shape_diff:
        print("  (none)")

    print("\n" + "=" * 70)
    print("3. POTENTIAL MEMORY-ERROR RISKS IN box_ansa.cgns")
    print("=" * 70)

    risks = []
    for path, d in ia.items():
        p = path.lower()
        # PointList 1D vs 2D
        if "pointlist" in p and "zonebc" in p:
            s = d["shape"]
            if len(s) == 1:
                risks.append(("PointList 1D", path, d, "Readers expect (n,1); stride/overflow"))
        # ElementConnectivity negative
        if "elementconnectivity" in p and d.get("has_negative"):
            risks.append(("Negative connectivity", path, d, "Solvers expect positive IDs; index errors"))
        # ElementStartOffset
        if "elementstartoffset" in p:
            risks.append(("ElementStartOffset", path, d, "Verify vs ElementConnectivity length"))

    # Comparison-based risks (critical)
    for (p, sa, sb, da, db) in shape_diff:
        pl = p.lower()
        # BC/surfs data length mismatch - CRITICAL
        if ("zonebc" in pl or "box_surfs" in pl) and sa != sb:
            risks.append(("BC data LENGTH MISMATCH", p, ia.get(p, {}),
                         f"ansa shape={sa} vs ngons {sb} -> buffer overrun/underrun"))
        # int32 vs int64
        if "int32" in da and "int64" in db:
            risks.append(("int32 vs int64", p, ia.get(p, {}),
                         "Large indices may overflow; reader expecting int64 may mis-stride"))
        # PointList shape
        if "pointlist" in pl and len(sa) != len(sb):
            risks.append(("PointList shape mismatch", p, ia.get(p, {}), f"ansa={sa} ngons={sb}"))

    for kind, path, d, reason in risks:
        print(f"\n  [{kind}]")
        print(f"    Path: {path}")
        print(f"    Shape: {d.get('shape')} dtype: {d.get('dtype')}")
        print(f"    Risk: {reason}")

    print("\n" + "=" * 70)
    print("4. SUMMARY COUNTS")
    print("=" * 70)
    print(f"  Datasets only in ansa: {len(only_a)}")
    print(f"  Datasets only in ngons: {len(only_b)}")
    print(f"  Common datasets: {len(common)}")
    print(f"  Shape/dtype diffs: {len(shape_diff)}")
    print(f"  Identified risks: {len(risks)}")


if __name__ == "__main__":
    a = Path("box_ansa.cgns")
    b = Path("box_ngons.cgns")
    if not a.exists():
        print("Missing:", a)
        sys.exit(1)
    if not b.exists():
        print("Missing:", b)
        sys.exit(1)
    compare(str(a), str(b))
