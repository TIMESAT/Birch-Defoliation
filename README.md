# Birch forest defoliation from MODIS LAI

How much leaf area does a birch forest lose during a moth outbreak, and how does that loss change from day to day? The study estimates daily defoliation at 500 m resolution by comparing each pixel’s leaf area index (LAI) with its LAI on the same day in reference years.

**Available in this repository.** `run_birch_lai.py` fits the two inputs to that analysis. A double-logistic fit yields the growing-season peak LAI used to detect outbreaks. A separate spline fit yields daily LAI and can follow a decline within the growing season. The script writes both products as GeoTIFFs.

## From fitted LAI to daily defoliation

The following steps describe the study method. They still require a separate analysis script. If you already have seasonal peak and daily fitted LAI on the same grid and calendar, you can start here and skip the TIMESAT installation and fitting steps below.

1. **Select reference years for each pixel.** Over 2002–2020, select the 14 years with the highest annual growing-season peak LAI. Compute the mean and standard deviation of those 14 peaks.
2. **Identify outbreak years.** For each pixel and year, subtract the reference mean from the annual peak and divide by the reference standard deviation. The study used a z-score threshold of −1.97 to flag unusually low peaks. The reference-year count and threshold were calibrated using field observations in Abisko in 2013.
3. **Estimate daily defoliation.** For each day in a flagged year, average the fitted LAI for the corresponding day across that pixel’s 14 reference years. Equation 2 in the manuscript gives the signed ratio `(daily LAI − reference LAI) / reference LAI`. For example, a daily LAI of 3 against a reference of 4 gives −0.25, a 25% deficit.

## Install the TIMESAT CLI for LAI fitting

Open a terminal in the directory containing `run_birch_lai.py`. Create a Python 3.12 environment, then use pip to install the released CLI and its TIMESAT core dependency.

```sh
conda create -n birch-lai python=3.12 -y
conda activate birch-lai
python -m pip install timesat-cli==1.9.2 timesat==4.4.1
python -m timesat_cli run --help
```

Use `python -m pip show timesat-cli timesat` to record the installed versions. The example was tested with Python 3.12, timesat-cli 1.9.2 and timesat 4.4.1.

## Prepare the two inputs

The local birch mask is stored at
[`data/masks/pft08_corine_orig_D2_country4_Poly2Rst_MODISgrid.tif`](data/masks/pft08_corine_orig_D2_country4_Poly2Rst_MODISgrid.tif).
It was moved from the local `Jing` directory; the historical `cut_birch.txt`
script identifies it as the birch forest mask and excludes pixels with value 0.
The mask contains values 0 and 1 (retain 1), with 0 also declared as nodata.
Its 9600 × 14400 grid covers a larger area than the raw 2400 × 2400 LAI tile.
Align and crop it to the input raster grid before masking; use nearest-neighbor
resampling if resampling is needed. The runner does not apply the mask itself.

The cropped mask for the current raw LAI tile is
[`data/masks/birch_mask_h18v02.tif`](data/masks/birch_mask_h18v02.tif).
It matches the raw h18v02 LAI grid exactly (2400 × 2400 pixels), was generated
using nearest-neighbor resampling, and retains 564,352 birch pixels with value 1.
Value 0 is excluded/nodata. The original mask is preserved above.

Use the unscaled MCD15A2H Collection 6 LAI and the study's binary QA layers on the same pixel grid and dates. QA value 1 means good data and 0 means bad data, as confirmed by the data owner. These QA rasters are already processed; do not interpret them as raw FparLai_QC bit fields. The preparation command below combines the aligned birch mask with each QA layer. Keep the stored integer LAI values. The script scales them by 0.1 and assigns weight 1 only to QA value 1; all other QA values receive weight 0.

Supply one text file per layer, with one absolute path per line in chronological order. Include the acquisition date in each raster filename, for example `Lai_20120601.tif` and `QA_20120601.tif`. You can also supply two multiband GeoTIFFs with acquisition dates in their band descriptions.

## Run the fits

```sh
python prepare_birch_inputs.py "path/to/raw_tif"
python run_birch_lai.py data/local_inputs/lai.txt data/local_inputs/qa.txt results --dates data/local_inputs/dates.txt --mask data/masks/birch_mask_h18v02.tif
```

Preparation pairs each Collection 6 LAI image with the QA file of the same granule. Each dated QA VRT reads the product of observation QA and the aligned birch mask. This gives every observation outside the birch area zero weight. Keep the source TIFFs and mask at their current locations, or regenerate the lists after moving them. The dates file uses acquisition dates from the MODIS AYYYYDDD field.

Choose a new output directory for each run. To try a different spline smoothing factor, append `--smooth VALUE`. The default of 1000 comes from a TIMESAT 4.1.4 example configuration.

| Output under the run directory | Contents |
| --- | --- |
| `double_logistic/VPP/*_MAXV_*.tif` | Peak fitted LAI by year and season. Missing seasons have nodata values. |
| `spline/ST/` | Daily fitted LAI in physical units and associated QA rasters. Each year has 365 output dates. In leap years this configuration omits December 31. |
| `double_logistic.json`, `spline.json` | The exact settings passed to the CLI for each fit. |

The current core and version 4.1.4 handle season detection and spline bounds differently. Numerical agreement with historical birch outputs still needs validation on the original pixels.
