# Birch forest LAI with TIMESAT

Fit MODIS birch forest leaf area index (LAI) with the [TIMESAT CLI](https://github.com/TIMESAT/TIMESAT-CLI). The double-logistic fit gives the peak LAI for each detected season. A separate spline fit gives daily LAI, including within-season declines during defoliation.

## Install the CLI

Open a terminal in the directory containing `run_birch_lai.py`. Create a Python 3.12 environment, then use pip to install the released CLI and its TIMESAT core dependency.

```sh
conda create -n birch-lai python=3.12 -y
conda activate birch-lai
python -m pip install timesat-cli
python -m timesat_cli run --help
```

To install the development version directly from the official GitHub repository, use the following pip command in the same environment. Git must be installed.

```sh
python -m pip install --upgrade "git+https://github.com/TIMESAT/TIMESAT-CLI.git"
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

The workflow ends at the fitted LAI products. Outbreak classification and daily defoliation ratios are downstream analyses. The current core and version 4.1.4 handle season detection and spline bounds differently. Numerical agreement with historical birch outputs still needs validation on the original pixels.
