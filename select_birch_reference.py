"""Select per-pixel reference years and classify annual birch outbreaks."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import re

import numpy as np
import rasterio

from birch_rasters import check_grid, floats, new_output, values, windows, writer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vpp", type=Path)
    parser.add_argument("mask", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reference-count", type=int, default=14)
    parser.add_argument("--threshold", type=float, default=-1.97)
    parser.add_argument("--ddof", choices=(0, 1), type=int, default=1,
                        help="standard deviation divisor: N-ddof (default: sample SD)")
    args = parser.parse_args()
    groups = {}
    for p in sorted(args.vpp.glob("*_MAXV_*.tif")):
        match = re.fullmatch(r".+_MAXV_(\d{4})_season_(\d+)\.tif", p.name)
        if match:
            year, season = map(int, match.groups())
            if season in groups.setdefault(year, {}):
                parser.error(f"Duplicate season in {p}")
            groups[year][season] = p
    years = sorted(groups)
    n = args.reference_count
    if not 2 <= n <= len(years) or not np.isfinite(args.threshold):
        parser.error("need a finite threshold and at least reference-count years (N >= 2)")
    if any(set(groups[y]) != {1, 2} for y in years):
        parser.error("expected both TIMESAT season rasters for every year")

    with new_output(args.output) as out, ExitStack() as stack:
        grid = stack.enter_context(rasterio.open(args.mask))
        sources = []
        for y in years:
            seasons = [stack.enter_context(rasterio.open(p)) for p in groups[y].values()]
            for ds in seasons:
                check_grid(ds, grid)
            sources.append(seasons)
        def product(name, labels, dtype="float32", nodata=-9999):
            return stack.enter_context(writer(out / name, grid, labels, dtype, nodata))
        peaks = product("annual_peak.tif", years)
        selected = product("reference_years.tif", years, "uint8", 255)
        stats = product("reference_peak_stats.tif", ["mean", "sd"])
        scores = product("zscore.tif", years)
        outbreak = product("outbreak.tif", years, "uint8", 255)
        for win in windows(grid):
            birch = grid.read(1, window=win) == 1
            peak = np.stack([np.fmax(values(a, win), values(b, win)) for a, b in sources])
            peak[:, ~birch] = np.nan
            eligible = np.isfinite(peak).sum(axis=0) >= n
            # Stable descending sort resolves equal peaks in favour of earlier years.
            order = np.argsort(-np.nan_to_num(peak, nan=-np.inf), axis=0, kind="stable")[:n]
            keep = np.zeros(peak.shape, dtype=bool)
            np.put_along_axis(keep, order, True, axis=0)
            top = np.take_along_axis(peak, order, axis=0)
            mean, sd = top.mean(axis=0), top.std(axis=0, ddof=args.ddof)
            z = np.full_like(peak, np.nan)
            np.divide(peak-mean, sd, out=z, where=eligible & (sd > 0))
            peaks.write(floats(peak), window=win)
            selected.write(np.where(eligible, keep, 255).astype("uint8"), window=win)
            stats.write(floats(np.stack([mean, sd])), window=win)
            scores.write(floats(z), window=win)
            outbreak.write(np.where(np.isfinite(z), z < args.threshold, 255).astype("uint8"),
                           window=win)
        (out / "settings.json").write_text(json.dumps(dict(years=years, reference_count=n,
            ddof=args.ddof, threshold=args.threshold, comparison="<", tie_break="earliest year"),
            indent=2) + "\n")


if __name__ == "__main__":
    main()
