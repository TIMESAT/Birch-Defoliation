"""Prepare dated TIMESAT lists and virtual QA rasters for the h18v02 study."""
import argparse
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import rasterio
from rasterio.shutil import copy as raster_copy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/local_inputs"))
    parser.add_argument("--mask", type=Path, default=Path("data/masks/birch_mask_h18v02.tif"))
    args = parser.parse_args()
    root = args.output.resolve()
    alias_dir = root / "qa_dates"
    alias_dir.mkdir(parents=True, exist_ok=True)
    images = sorted(args.raw_dir.resolve().glob("MCD15A2H.A*.h18v02.006.*_lai.tif"))
    if not images:
        parser.error("no Collection 6 h18v02 LAI images found")
    dates = []
    quality = []
    with rasterio.open(args.mask) as mask:
        grid = (mask.shape, mask.transform, mask.crs)
    for image in images:
        date = datetime.strptime(image.name.split(".")[1], "A%Y%j").strftime("%Y%m%d")
        if dates and date <= dates[-1]:
            raise ValueError(f"Duplicate or out-of-order acquisition: {image}")
        qa = image.with_name(image.name.replace("_lai.tif", "_qa.tif"))
        with rasterio.open(image) as lai, rasterio.open(qa) as obs:
            for dataset in (lai, obs):
                if (dataset.shape, dataset.transform, dataset.crs) != grid:
                    raise ValueError(f"Mask grid mismatch: {dataset.name}")
        alias = alias_dir / f"QA_{date}.vrt"
        # Build a dated GDAL view of QA * mask. Both inputs are binary.
        raster_copy(qa, alias, driver="VRT")
        tree = ET.parse(alias)
        band = tree.find("VRTRasterBand")
        band.set("subClass", "VRTDerivedRasterBand")
        band.set("dataType", "Byte")
        ET.SubElement(band, "PixelFunctionType").text = "mul"
        source = ET.SubElement(band, "SimpleSource")
        ET.SubElement(source, "SourceFilename", relativeToVRT="0").text = str(args.mask.resolve())
        ET.SubElement(source, "SourceBand").text = "1"
        tree.write(alias, encoding="utf-8")
        quality.append(str(alias))
        dates.append(date)
    for name, rows in (("lai", map(str, images)), ("qa", quality), ("dates", dates)):
        (root / f"{name}.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Prepared {len(images)} paired acquisitions in {root}")


if __name__ == "__main__":
    main()
