"""Calculate the daily reference spline and signed defoliation in outbreak years."""
import argparse
from contextlib import ExitStack
from datetime import date, timedelta
import json
from pathlib import Path

import numpy as np
import rasterio

from birch_rasters import check_grid, floats, new_output, values, windows, writer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("st", type=Path, help="TIMESAT daily spline ST directory")
    parser.add_argument("annual", type=Path, help="select_birch_reference.py output")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    settings = json.loads((args.annual / "settings.json").read_text())
    years, n = settings["years"], settings["reference_count"]
    calendar = [[(date(y, 1, 1) + timedelta(days=i)).strftime("%Y%m%d")
                 for i in range(365)] for y in years]
    with new_output(args.output) as out, ExitStack() as stack:
        selected = stack.enter_context(rasterio.open(args.annual / "reference_years.tif"))
        outbreak = stack.enter_context(rasterio.open(args.annual / "outbreak.tif"))
        check_grid(outbreak, selected)
        for ds in (outbreak, selected):
            if ds.descriptions != tuple(map(str, years)):
                raise ValueError(f"Year labels differ from settings: {ds.name}")
        ref = stack.enter_context(writer(out / "reference_sp.tif", selected,
                    [f"DOY_{i:03}" for i in range(1, 366)], "float32", -9999))
        ratios = [stack.enter_context(writer(out / f"defoliation_{year}.tif", selected,
                  dates, "float32", -9999)) for year, dates in zip(years, calendar)]
        for day in range(365):
            with ExitStack() as daily:
                sources = [daily.enter_context(rasterio.open(args.st / f"TIMESAT_{dates[day]}.tif"))
                           for dates in calendar]
                for ds in sources:
                    check_grid(ds, selected)
                for win in windows(selected):
                    keep = selected.read(window=win) == 1
                    flagged = outbreak.read(window=win) == 1
                    lai = np.stack([values(ds, win) for ds in sources])
                    valid = (keep & np.isfinite(lai)).sum(axis=0) == n
                    baseline = np.where(valid, np.where(keep, lai, 0).sum(axis=0)/n, np.nan)
                    ref.write(floats(baseline), day+1, window=win)
                    result = np.full_like(lai, np.nan)
                    np.divide(lai-baseline, baseline, out=result,
                              where=flagged & (baseline > 0))
                    for dst, layer in zip(ratios, result):
                        dst.write(floats(layer), day+1, window=win)
            if (day+1) % 50 == 0:
                print(f"Completed {day+1}/365 days", flush=True)


if __name__ == "__main__":
    main()
