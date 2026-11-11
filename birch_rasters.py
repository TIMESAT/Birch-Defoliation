"""Shared raster I/O for the downstream birch analysis."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
from rasterio.windows import Window


@contextmanager
def new_output(path):
    path = Path(path).resolve()
    if path.exists():
        raise FileExistsError(f"Choose a new output directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as work:
        pending = Path(work) / "products"
        pending.mkdir()
        yield pending
        pending.rename(path)


def check_grid(dataset, template):
    if (dataset.shape, dataset.crs, dataset.transform) != (
        template.shape, template.crs, template.transform
    ):
        raise ValueError(f"Grid mismatch: {dataset.name}")


def windows(dataset, size=256):
    for y in range(0, dataset.height, size):
        for x in range(0, dataset.width, size):
            yield Window(x, y, min(size, dataset.width-x), min(size, dataset.height-y))


def writer(path, grid, labels, dtype, nodata):
    ds = rasterio.open(path, "w", driver="GTiff", width=grid.width, height=grid.height,
                       crs=grid.crs, transform=grid.transform, count=len(labels),
                       dtype=dtype, nodata=nodata, compress="deflate", interleave="band",
                       tiled=True, blockxsize=128, blockysize=128, BIGTIFF="IF_SAFER")
    ds.descriptions = tuple(map(str, labels))
    return ds


def values(dataset, window):
    data = dataset.read(1, window=window, masked=True).astype("float64").filled(np.nan)
    data[~np.isfinite(data)] = np.nan
    return data


def floats(data):
    return np.where(np.isfinite(data), data, -9999).astype("float32")
