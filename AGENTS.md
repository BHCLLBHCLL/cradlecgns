# AGENTS.md

## Cursor Cloud specific instructions

This is a Python CLI toolbox (no web server, no database, no Docker). All scripts are standalone CLI tools in the repo root that operate on `.cgns` (HDF5) files.

### Dependencies

- `pip install -r requirements.txt` installs `h5py` and `numpy` (core deps).
- `fpdf2` is an optional dependency for `md2pdf_simple.py` (Markdown-to-PDF). Install with `pip install fpdf2` if needed.

### Running scripts

Each script uses `argparse` and can be run with `python3 <script>.py --help`. They require `.cgns` data files as input — none are included in the repo. To create a minimal test file for local development, use `h5py` + `numpy` to write a small HDF5/CGNS structure (see README or inline script docs for structure details).

### Linting

- `flake8 --max-line-length=120 *.py` — pre-existing minor warnings in `convert_elements_zone.py`.
- `pyright *.py` — 35 pre-existing errors, all related to `h5py` type-stub limitations (not real bugs).

### Key gotcha

- `compare_cgns.py` hardcodes input filenames (`box_ansa.cgns`, `box_ngons.cgns`) and does not use argparse — it expects those files in the working directory.
