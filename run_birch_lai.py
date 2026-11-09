"""Fit seasonal MAXV and daily LAI via the current TIMESAT CLI.

Supply aligned, unscaled MCD15A2H Lai_500m and raw FparLai_QC rasters.
Each input is a CLI image list (absolute raster paths with dates in their
names) or a GeoTIFF stack with dated band descriptions. Limit inputs to the
study pixels beforehand. Output is in physical LAI units on a 365-day grid.
"""

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lai", type=Path)
    parser.add_argument("qc", type=Path)
    parser.add_argument("output", type=Path, help="new directory for both CLI runs")
    parser.add_argument("--smooth", type=float, default=1000,
                        help="spline smoothing factor (4.1.4 sample setting: 1000)")
    args = parser.parse_args()
    if not math.isfinite(args.smooth) or args.smooth <= 0:
        parser.error("--smooth must be positive and finite")
    for path in (args.lai, args.qc):
        if not path.is_file():
            parser.error(f"input file not found: {path}")

    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    # Unlisted QA byte values receive zero weight in the CLI.
    good_qc = [[q, 1] for q in range(256) if q & 1 == 0 and (q >> 3) & 3 == 0]
    for fit_name, method in (("double_logistic", 1), ("spline", 2)):
        peak_run = method == 1
        config = {
            "input": {"image_file_list": str(args.lai.resolve()),
                      "quality_file_list": str(args.qc.resolve())},
            "general": {
                "scale": 0.1, "offset": 0, "p_ylu": [0, 10], "p_a": good_qc,
                "p_ignoreday": 366, "p_outlier": 0, "p_davailwin": 45,
                # Envelope, thresholds and percentile are from sample.set;
                # the CLI's season detector uses its own parameterization.
                "classes": [{"landuse": 1, "p_fitmethod": method,
                             "p_fillbase": 1, "p_nenvi": 1, "p_wfactnum": 2,
                             "p_low_percentile": 0.05, "p_startmethod": 1,
                             "p_startcutoff": [0.5, 0.5], "p_smooth": args.smooth,
                             "p_seasonmethod": 1, "p_seapar": 1}],
            },
            "output": {
                "outputfolder": str(root / fit_name), "p_hrvppformat": 0,
                "outputvariables": 1 if peak_run else 0,
                "vpp_variables": ["MAXV"], "time_sampling": "regular",
                # VPP uses the full fit independently of the exported ST dates.
                "time_step_days": 365 if peak_run else 1,
                "drop_first_year": False, "drop_last_year": False,
            },
        }
        settings = root / f"{fit_name}.json"
        settings.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, "-m", "timesat_cli", "run", str(settings)],
                       check=True)


if __name__ == "__main__":
    main()
