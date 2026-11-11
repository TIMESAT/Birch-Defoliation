# Birch forest defoliation from MODIS LAI

How much leaf area does a birch forest lose during a moth outbreak, and how does that loss change from day to day? The study estimates daily defoliation at 500 m resolution by comparing each pixel’s leaf area index (LAI) with its LAI on the same day in reference years.

`run_birch_lai.py` writes growing-season peak LAI (double-logistic fit) and daily LAI (spline fit). `select_birch_reference.py` uses the peaks to select reference years and flag outbreaks. `daily_birch_defoliation.py` combines those selections with daily LAI to calculate signed defoliation ratios.

## From fitted LAI to daily defoliation

If you already have the TIMESAT peak and daily fitted LAI products on the same grid, you can run the following stages directly in the project environment.

1. **Select reference years for each pixel.** Over 2002–2020, select the 14 years with the highest annual growing-season peak LAI. Compute the mean and standard deviation of those 14 peaks.
2. **Identify outbreak years.** For each pixel and year, subtract the reference mean from the annual peak and divide by the reference standard deviation. The study used a z-score threshold of −1.97 to flag unusually low peaks. The reference-year count and threshold were calibrated using field observations in Abisko in 2013.
3. **Estimate daily defoliation.** Construct the normal daily spline (SP) curve for each pixel by averaging its daily spline fits across the 14 reference years, one day at a time. Compare each day in a flagged year with the corresponding value on that curve. Equation 2 in the manuscript gives the signed ratio `(daily LAI − reference LAI) / reference LAI`. For example, a daily LAI of 3 against a reference of 4 gives −0.25, a 25% deficit.

### Run the downstream stages

For the Abisko 50 km run, execute these commands from the repository root in the `birch-lai` environment. Each command creates a new output directory.

```sh
python select_birch_reference.py runs/abisko_50km_2002_2020/double_logistic/VPP runs/abisko_50km_inputs/mask.tif runs/abisko_50km_2002_2020/annual
python daily_birch_defoliation.py runs/abisko_50km_2002_2020/spline/ST runs/abisko_50km_2002_2020/annual runs/abisko_50km_2002_2020/daily
```

| Output | How to read it |
| --- | --- |
| `annual/annual_peak.tif` | One band per year, using the largest valid seasonal MAXV. |
| `annual/reference_years.tif` | Year-labelled bands. For eligible pixels, 1 marks a selected year and 0 an unselected year. |
| `annual/reference_peak_stats.tif` | Mean and standard deviation of the selected annual peaks. |
| `annual/zscore.tif`, `annual/outbreak.tif` | Annual z-scores and flags. Flag 1 means the score is below the threshold, 0 means the score is at or above it. |
| `daily/reference_sp.tif` | The reference LAI curve, with one band for each TIMESAT day of year (1–365). |
| `daily/defoliation_YYYY.tif` | One dated band per day, populated only in flagged pixel-years. Values are signed fractions. Positive values indicate daily LAI above the reference. |

The annual defaults are `--reference-count 14 --threshold -1.97 --ddof 1`. The implementation uses sample standard deviation (N−1), a strict threshold comparison, and earlier years first when peaks tie. A pixel needs at least 14 valid annual peaks. Zero standard deviation gives NoData for the z-score and outbreak flag. The annual directory records the settings used.

The daily stage aligns years by ordinal day on the fitted 365-day calendar. Each day requires valid spline LAI in all selected reference years. The ratio also requires valid outbreak-year LAI and positive reference LAI. NoData is 255 for the two flag products and −9999 for floating-point outputs. Changes to the annual settings require rerunning both downstream stages.

## Install the TIMESAT CLI for LAI fitting

Open a terminal in the directory containing `run_birch_lai.py`. Create a Python 3.12 environment, then use pip to install the released CLI and its TIMESAT core dependency.

```sh
conda create -n birch-lai python=3.12 -y
conda activate birch-lai
python -m pip install timesat-cli==1.9.2 timesat==4.4.1
python -m timesat_cli run --help
```

Use `python -m pip show timesat-cli timesat` to record the installed versions. The command pins the versions used in the birch test run. CLI 1.9.2 accepts core versions `>=4.4.1,<4.5`.

## Prepare the LAI and QA inputs

For tile `h18v02`, use the [aligned birch mask](data/masks/birch_mask_h18v02.tif). It identifies 564,352 birch pixels (value 1) on the 2400 × 2400 LAI grid. The [original mask](data/masks/pft08_corine_orig_D2_country4_Poly2Rst_MODISgrid.tif) covers a larger area.

From the project directory, run this once with the folder containing the study's unscaled MCD15A2H Collection 6 LAI and binary QA TIFFs. Replace the example path with your data folder.

```sh
python prepare_birch_inputs.py "path/to/raw_tif"
```

The preparation script pairs each `_lai.tif` with the matching `_qa.tif`, checks their grids against the mask, and reads the acquisition date from the MODIS `AYYYYDDD` field. It writes `lai.txt`, `qa.txt`, and `dates.txt` under `data/local_inputs/`. For the study data, these lists contain 851 paired dates from 2002-07-04 through 2020-12-26.

Each dated QA virtual raster (VRT) computes **birch mask × observation QA**. An observation receives weight 1 only where both values are 1. All observations outside the birch area receive weight 0. The fitting script scales stored LAI by 0.1. If you move the source TIFFs or mask, rerun preparation to update the references.

## Run the fits

With the input lists in place, activate the environment and run both fits from the project directory. The `--mask` option also supplies the aligned raster to TIMESAT as land cover. The prepared QA list enforces the birch boundary for both fits.

```sh
conda activate birch-lai
python run_birch_lai.py data/local_inputs/lai.txt data/local_inputs/qa.txt runs/full_2002_2020 --dates data/local_inputs/dates.txt --mask data/masks/birch_mask_h18v02.tif
```

For already prepared inputs, the runner also accepts multiband GeoTIFFs with acquisition dates in the band descriptions. The QA bands must include the spatial mask to reproduce the study-area restriction.

Choose a new output directory for each run. To try a different spline smoothing factor, append `--smooth VALUE`. The default of 1000 comes from a TIMESAT 4.1.4 example configuration.

### Fit only the Abisko field area

Crop the prepared inputs to a 50 × 50 km square centred on Abisko Östra (68.34864° N, 18.83035° E). The square extends 25 km in each direction in UTM zone 34N. Both fits use the original MODIS grid and all 851 acquisition dates. Only birch pixels whose centres fall inside the square receive observation weights. [Centre coordinates](https://www.lanstrafik.se/en/stop/abisko-ostra/)

```sh
python prepare_birch_subset.py runs/abisko_50km_inputs --abisko-size-km 50
python run_birch_lai.py runs/abisko_50km_inputs/lai.tif runs/abisko_50km_inputs/qa.tif runs/abisko_50km_2002_2020 --mask runs/abisko_50km_inputs/mask.tif
```

The first command creates dated LAI and masked QA stacks once. If these already exist, start with the second command.

### Fit outputs

| Output under the run directory | Contents |
| --- | --- |
| `double_logistic/VPP/*_MAXV_*.tif` | Peak fitted LAI by year and season. Missing seasons have nodata values. |
| `spline/ST/` | Daily fitted LAI in physical units and associated QA rasters. Each year has 365 output dates. In leap years this configuration omits December 31. |
| `double_logistic.json`, `spline.json` | The exact settings passed to the CLI for each fit. |

Both products retain the input grid. In a 4 × 4 window spanning the birch boundary (138 acquisitions, 2010–2012), all 1,095 daily LAI rasters and all six seasonal peak rasters contained NoData outside the mask.

The current core and version 4.1.4 handle season detection and spline bounds differently. Numerical agreement with historical birch outputs still needs validation on the original pixels.
