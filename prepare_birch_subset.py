"""Crop prepared LAI, masked QA and land cover to the selected study area."""
import argparse
from contextlib import ExitStack
from datetime import datetime
from math import ceil, floor
from pathlib import Path

import rasterio
import numpy as np
from rasterio.warp import transform, transform_bounds
from rasterio.windows import Window, from_bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new subset directory")
    region = parser.add_mutually_exclusive_group(required=True)
    region.add_argument("--abisko-size-km", type=float,
                        help="side length of a UTM 34N square centred on Abisko Östra")
    region.add_argument("--bounds", nargs=4, type=float,
                        metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    parser.add_argument("--padding-km", type=float, default=0,
                        help="extend each edge in the MODIS metre grid")
    parser.add_argument("--inputs", type=Path, default=Path("data/local_inputs"))
    parser.add_argument("--mask", type=Path, default=Path("data/masks/birch_mask_h18v02.tif"))
    args = parser.parse_args()
    region_crs = "EPSG:4326"
    if args.bounds:
        w, s, e, n = args.bounds
        if not (-180 <= w < e <= 180 and -90 <= s < n <= 90 and args.padding_km >= 0):
            parser.error("invalid WGS84 bounds or padding")
    else:
        if not np.isfinite(args.abisko_size_km) or args.abisko_size_km <= 0 or args.padding_km:
            parser.error("--abisko-size-km needs a positive finite size and zero padding")
        region_crs = "EPSG:32634"
        east, north = transform("EPSG:4326", region_crs, [18.83035], [68.34864])
        half = args.abisko_size_km * 500
        w, s, e, n = east[0]-half, north[0]-half, east[0]+half, north[0]+half
    dates, lai, qa = [(args.inputs / (key + ".txt")).read_text().splitlines()
                      for key in ("dates", "lai", "qa")]
    if not dates or len(dates) != len(lai) or len(dates) != len(qa):
        parser.error("expected matching, nonempty prepared lists")
    if dates != sorted(set(dates)):
        parser.error("dates must be unique and chronological")
    for date in dates:
        datetime.strptime(date, "%Y%m%d")

    with rasterio.open(args.mask) as mask:
        grid = (mask.shape, mask.transform, mask.crs)
        left, bottom, right, top = transform_bounds(region_crs, mask.crs, w, s, e, n)
        pad = args.padding_km * 1000
        box = from_bounds(left-pad, bottom-pad, right+pad, top+pad, mask.transform)
        x, y = floor(box.col_off), floor(box.row_off)
        end_x, end_y = ceil(box.col_off + box.width), ceil(box.row_off + box.height)
        if x < 0 or y < 0 or end_x > mask.width or end_y > mask.height:
            parser.error("requested bounds extend beyond the source tile")
        window = Window(x, y, end_x-x, end_y-y)
        birch = mask.read(1, window=window)
        if args.abisko_size_km:
            rows, cols = np.indices(birch.shape)
            mx, my = mask.window_transform(window) * (cols + 0.5, rows + 0.5)
            east, north = np.asarray(transform(mask.crs, region_crs, mx.ravel(), my.ravel()))
            inside = (east >= w) & (east <= e) & (north >= s) & (north <= n)
            birch[~inside.reshape(birch.shape)] = 0
        profile = dict(driver="GTiff", width=window.width, height=window.height,
                       transform=mask.window_transform(window), crs=mask.crs,
                       dtype="uint8", compress="deflate", interleave="band")
    args.output.mkdir(parents=True, exist_ok=False)
    with rasterio.open(args.output / "mask.tif", "w", count=1, nodata=0, **profile) as dst:
        dst.write(birch, 1)
    with ExitStack() as stack:
        targets = [stack.enter_context(rasterio.open(args.output / name, "w",
                   count=len(dates), **profile)) for name in ("lai.tif", "qa.tif")]
        for band, (date, image, quality) in enumerate(zip(dates, lai, qa), 1):
            for path, dst in zip((image, quality), targets):
                with rasterio.open(path) as src:
                    if (src.shape, src.transform, src.crs) != grid:
                        raise ValueError(f"Mask grid mismatch: {path}")
                    values = src.read(1, window=window)
                    if dst is targets[1]:
                        values[birch != 1] = 0
                    dst.write(values, band)
                dst.set_band_description(band, date)
    print(f"{window.width} x {window.height}, {int((birch == 1).sum())} birch pixels, "
          f"{len(dates)} acquisitions in {args.output}")


if __name__ == "__main__":
    main()
