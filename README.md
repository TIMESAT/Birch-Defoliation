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
python -m pip install timesat-cli
python -m timesat_cli run --help
```

Use `python -m pip show timesat-cli timesat` to record the installed versions. The example was tested with Python 3.12, timesat-cli 1.9.2 and timesat 4.4.1.

## Prepare the two inputs

Use the raw MCD15A2H Collection 6 LAI and FparLai_QC layers on the same pixel grid and dates. Apply the study's birch mask beforehand. Keep the stored integer LAI values. The script scales them by 0.1 and retains observations flagged good (MODLAND_QC = 0) and clear (CloudState = 0).

Supply one text file per layer, with one absolute path per line in chronological order. Include the acquisition date in each raster filename, for example `Lai_20120601.tif` and `FparLai_QC_20120601.tif`. You can also supply two multiband GeoTIFFs with acquisition dates in their band descriptions.

## Run the fits

```sh
python run_birch_lai.py lai_files.txt qc_files.txt results
```

Choose a new output directory for each run. To try a different spline smoothing factor, append `--smooth VALUE`. The default of 1000 comes from a TIMESAT 4.1.4 example configuration.

| Output under the run directory | Contents |
| --- | --- |
| `double_logistic/VPP/*_MAXV_*.tif` | Peak fitted LAI by year and season. Missing seasons have nodata values. |
| `spline/ST/` | Daily fitted LAI in physical units and associated QA rasters. Each year has 365 output dates. In leap years this configuration omits December 31. |
| `double_logistic.json`, `spline.json` | The exact settings passed to the CLI for each fit. |

The current core and version 4.1.4 handle season detection and spline bounds differently. Numerical agreement with historical birch outputs still needs validation on the original pixels.
