# Comparison metrics

<!-- Written by scripts/make_metrics_doc.py from the code: do not edit by hand. -->

The point-by-point comparison metrics of DESTEST 3.0 (`destest.analysis.point_by_point_comparison`).
They follow the notation, names, units, ranges and optimum values of Technical Report 314
(Johra et al., 2023), the supplementary material of the review by Johra et al. (2023):

* **x** = reference values (here: the point-by-point median of all submissions),
  **y** = simulated values, **n** = number of points, x-bar, y-bar = means,
  sigma = standard deviations;
* errors are **y - x**: a positive bias means that the model over-predicts;
* pairs where y or x is missing are left out.

A CME chooses its metrics in `analysis.point_by_point_comparison.metrics` of its spec file
(CME_DHN_1 and CME_DHN_2: MBE and CVRMSE). In the accuracy grade, each submission is scored
on the distance of its metric value to the **optimum** (the value of a perfect fit).

References:

* H. Johra, M. Mans, K. Filonenko, I. De Jaeger, D. Saelens, T. Tvedebrink (2021).
  Evaluating different metrics for inter-model comparison of urban-scale building energy
  simulation time series. Building Simulation 2021, Bruges.
  <https://doi.org/10.26868/25222708.2021.30410>
* H. Johra, M. Schaffer, G. Chaudhary, H. Syed Kazmi, J. Le Dréau, S. Petersen (2023).
  Coherent description of 48 metrics to compare, validate and assess accuracy of building
  energy models and indoor environment simulations. DCE Technical Report No. 314, Aalborg
  University. <https://doi.org/10.54337/aau533917780>
* H. Johra, M. Schaffer, G. Chaudhary, H.S. Kazmi, J. Le Dréau, S. Petersen (2023). What
  metrics does the building energy performance community use to compare dynamic models?
  Building Simulation 2023, Shanghai, 861-868. <https://doi.org/10.26868/25222708.2023.1309>

Not implemented: the qualitative graphical assessment (see the dashboards) and nCPBES (no
equation in the report).

## Point-by-point metrics (time series and data profiles)

### Absolute error based

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `MaxAE` | Maximum Absolute Error | `MaxAE = max abs(y_i - x_i)` | unit of the data | [0, +inf] | 0 |  |
| `ThresholdError` | Threshold percentage error (e.g. 0.5 C percentage error) | `share of points with abs(y_i - x_i) > threshold = #{abs(y_i - x_i) > threshold} / n` | - | [0, 1] | 0 | Also: 0.5C Percentage Error. Threshold as a parameter (report: 0.5 C or 1 C); result is a share (0-1). Parameters: threshold. |
| `MAE` | Mean Absolute Error | `MAE = sum abs(y_i - x_i) / n` | unit of the data | [0, +inf] | 0 |  |
| `NMAE` | Normalised Mean Absolute Error | `NMAE = sum abs(y_i - x_i) / sum x_i * 100 % = MAE / x-bar * 100 %` | % | [0, +inf] | 0 | Also: MAE%. |
| `MANMAE` | Mean Absolute Normalized MAE | `MANMAE = sum abs(y_i - x_i) / sum x_i * 100 % (as printed in the report)` | % | [0, +inf] | 0 | The report prints the same equation as NMAE; computed as printed. |
| `RNMAE` | Range Normalized Mean Absolute Error | `RNMAE = MAE / (max x - min x) * 100 %` | % | [0, +inf] | 0 | Also: NMAE. |
| `ZMAE` | MAE normalised by the standard deviation of the reference | `ZMAE = MAE / sigma_x * 100 %` | % | [0, +inf] | 0 | sigma_x with n - 1 (as Var in the report); ddof = 0 for n. Parameters: ddof. |
| `rMAE` | Relative Mean Absolute Error | `rMAE = MAE(model) / MAE(baseline)` | - | [0, +inf] | 0 | Also: relative MAE. Needs the series of a baseline model (`baseline`); None without it. Parameters: baseline. |

### Bias based

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `MBE` | Mean Bias Error | `MBE = sum (y_i - x_i) / n` | unit of the data | [-inf, +inf] | 0 |  |
| `NMBE` | Normalised Mean Bias Error | `NMBE = MBE / x-bar * 100 %` | % | [-inf, +inf] | 0 | Also: RPE, RAE. |
| `RNMBE` | Range Normalized Mean Bias Error | `RNMBE = MBE / (max x - min x) * 100 %` | % | [-inf, +inf] | 0 |  |

### Absolute percentage error

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `MaxAPE` | Maximum Absolute Percentage Error | `MaxAPE = max abs(y_i - x_i) / abs(x_i) * 100 %` | % | [0, +inf] | 0 | In % of abs(x_i) (report: unit X, no factor 100); points with x_i = 0 left out. |
| `MedianAPE` | Median Absolute Percentage Error | `MedianAPE = median abs(y_i - x_i) / abs(x_i) * 100 %` | % | [0, +inf] | 0 | Also: med(absRTE), MdAPE. Range [0, +inf] (report: [-inf, +inf]); in %; points with x_i = 0 left out. |
| `MAPE` | Mean Absolute Percentage Error | `MAPE = sum abs(y_i - x_i) / abs(x_i) / n * 100 %` | % | [0, +inf] | 0 | Also: MAPD. Points with x_i = 0 left out. |

### Square error based

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `MSE` | Mean Square Error | `MSE = sum (y_i - x_i)^2 / n` | (unit of the data)² | [0, +inf] | 0 |  |
| `NMSE` | Normalised Mean Square Error | `NMSE = sum (y_i - x_i)^2 / sum (x_i - x-bar)^2 * 100 %` | % | [0, +inf] | 0 |  |
| `IA` | Index of Agreement (Willmott) | `IA = (1 - sum (y_i - x_i)^2 / sum (abs(y_i - x-bar) + abs(x_i - x-bar))^2) * 100 %` | % | [0, 100] | 100 | Willmott's index 1 - ... (the report prints the ratio alone, optimum 0). |
| `EF` | Modelling efficiency (Nash-Sutcliffe) | `EF = (sum (x_i - x-bar)^2 - sum (y_i - x_i)^2) / sum (x_i - x-bar)^2 * 100 %` | % | [-inf, 100] | 100 |  |
| `TheilUm` | Theil's coefficient of inequality: bias proportion Um | `Um = (y-bar - x-bar)^2 / MSE` | - | [0, 1] | 0 | Population standard deviations (n), so that Um + Uv + Uc = 1. Undefined for a perfect match (MSE = 0). |
| `TheilUv` | Theil's coefficient of inequality: variance proportion Uv | `Uv = (sigma_y - sigma_x)^2 / MSE` | - | [0, 1] | 0 | Population standard deviations (n), so that Um + Uv + Uc = 1. |
| `TheilUc` | Theil's coefficient of inequality: covariance proportion Uc | `Uc = 2 (1 - r_xy) sigma_y sigma_x / MSE` | - | [0, 1] | 1 | Population standard deviations (n), so that Um + Uv + Uc = 1. Optimum 1: all remaining error unsystematic (report: garbled). |
| `RMSE` | Root Mean Square Error | `RMSE = sqrt(sum (y_i - x_i)^2 / n) = sqrt(MSE)` | unit of the data | [0, +inf] | 0 | Also: RMSD, DRMS. |
| `RMSEP` | Root Mean Square Error Percentage | `RMSEP = sqrt(sum ((y_i - x_i) / x_i)^2 / n) * 100 %` | % | [0, +inf] | 0 | Points with x_i = 0 left out. |
| `RNRMSE` | Range Normalized Root Mean Square Error | `RNRMSE = RMSE / (max x - min x) * 100 %` | % | [0, +inf] | 0 | The report labels this equation 'RMSEP'. |
| `CVRMSE` | Coefficient of Variation of Root Mean Square Error | `CVRMSE = RMSE / x-bar * 100 %` | % | [0, +inf] | 0 | Also: (CV)RMSE, NRMSE, RMSE%, RRMSE. |
| `RMSEIQR` | Root Mean Square Error normalised by the interquartile range | `RMSEIQR = RMSE / IQR(x) * 100 %` | % | [0, +inf] | 0 |  |
| `RMSLE` | Root Mean Square Logarithmic Error | `RMSLE = sqrt(sum (log(y_i + 1) - log(x_i + 1))^2 / n)` | - | [0, +inf] | 0 | Natural logarithm; only for values above -1. Dimensionless (report: unit X). |
| `ZRMSE` | RMSE normalised by the standard deviation of the reference | `ZRMSE = RMSE / sigma_x * 100 %` | % | [0, +inf] | 0 | sigma_x with n - 1 (as Var in the report); ddof = 0 for n. Parameters: ddof. |
| `NRMSE` | Normalized Root Mean Squared Error | `NRMSE = sqrt(sum (y_i - x_i)^2) / sqrt(sum (x_i - x-bar)^2) * 100 %` | % | [0, +inf] | 0 |  |

### Based on statistical dispersion

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `Var` | Variance of the simulated values | `Var(y) = sum (y_i - y-bar)^2 / (n - 1)` | (unit of the data)² | [0, +inf] | see note | Optimum: Var(x), the variance of the reference. |
| `sd_ratio` | Standard deviation ratio | `sd_ratio = sigma_y / sigma_x` | - | ]0, +inf] | 1 |  |
| `sd_error` | Standard deviation of an error metric over periods | `sd_error = sd(metric on period 1, ..., metric on period k)` | unit of the data | [0, +inf] | 0 | `metric` computed on consecutive blocks of `period` points; unit of that metric. Parameters: metric, period. |
| `Cov` | Covariance | `cov(x, y) = sum (x_i - x-bar)(y_i - y-bar) / (n - 1)` | (unit of the data)² | [-inf, +inf] | see note | Optimum: Var(x) (report: 1). |

### Correlation based

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `r` | Pearson correlation coefficient | `r_xy = sum (x_i - x-bar)(y_i - y-bar) / sqrt(sum (x_i - x-bar)^2 sum (y_i - y-bar)^2)` | - | [-1, +1] | 1 |  |
| `rs` | Spearman's rank correlation coefficient | `r_s = r(rank(x), rank(y))` | - | [-1, +1] | 1 | Also: rho. Ties get their average rank. |
| `tau` | Kendall rank correlation coefficient | `tau = 1 - 2 * (number of discordant pairs) / (n (n - 1) / 2)` | - | [-1, +1] | 1 | As in the report (tau-a); tied pairs are not counted as discordant. |

### Relative difference based

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `CRM` | Coefficient of residual mass | `CRM = (sum y_i - sum x_i) / sum x_i` | - | [-inf, +inf] | 0 | Dimensionless (report: unit X). |

### Miscellaneous

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `SSE` | Sum of Squared Errors | `SSE = sum (y_i - x_i)^2` | (unit of the data)² | [0, +inf] | 0 | Also: SSR, RSS. |
| `R2` | Coefficient of determination (R squared) | `R2 = 1 - RSS / TSS = 1 - sum (y_i - x_i)^2 / sum (x_i - x-bar)^2` | - | [-inf, 1] | 1 | 1 - RSS/TSS (ESS/TSS equals it only for least-squares fits); can be negative. |
| `GOF` | Goodness of Fit | `GOF = sqrt((w_cv^2 CVRMSE^2 + w_b^2 NMBE^2) / (w_cv^2 + w_b^2))` | % | [0, +inf] | 0 | Bias term NMBE (default) or MBE (`bias='MBE'`); weights as parameters. Parameters: bias, w_bias, w_cvrmse. |
| `ACF` | Auto-correlation of the residuals | `ACF(k) = sum (e_i - e-bar)(e_(i+k) - e-bar) / sum (e_i - e-bar)^2, e = y - x` | - | [-1, 1] | 0 | At lag `lag` (default 1); should be close to 0 for non-zero lags. Parameters: lag. |

## Time-series metrics (need the time axis)

### Time-aggregated (DESTEST)

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `HourlyCVRMSE` | CVRMSE of hourly-averaged data | `CVRMSE of the hourly means of y and x` | % | [0, +inf] | 0 | Johra et al. (2021): smooths small time shifts. `period` in s (default 3600). Parameters: period. |
| `CVRMSE_24hAmp` | CVRMSE of the daily amplitude | `CVRMSE of (max - min) per day of y and x` | % | [0, +inf] | 0 | Johra et al. (2021): days from t = 0 (midnight); `period` in s (default 86400). Parameters: period. |
| `RMSE_24hAmp` | RMSE of the daily amplitude | `RMSE of (max - min) per day of y and x` | unit of the data | [0, +inf] | 0 | Johra et al. (2021): days from t = 0 (midnight); `period` in s (default 86400). Parameters: period. |

### Elastic distance

| Name | Full name | Equation | Unit | Range | Optimum | Notes |
|---|---|---|---|---|---|---|
| `DTW` | Dynamic Time Warping distance | `DTW = min over warping paths of sum abs(y_i - x_j) (absolute cost)` | unit of the data | [0, +inf] | 0 | Optional Sakoe-Chiba `window` (points); O(n * window) memory-light computation. Parameters: window. |
| `Frechet` | Discrete Frechet distance | `Frechet = min over couplings of max abs(y_i - x_j)` | unit of the data | [0, +inf] | 0 | Discrete version (Eiter and Mannila, 1994), on the values only. |
| `COR` | Dissimilarity based on Pearson's correlation | `COR = sqrt(2 (1 - r_xy))` | - | [0, 2] | 0 | As CorDistance of TSdist (Mori et al., 2016). |
| `CORT` | Dissimilarity combining temporal correlation and raw values | `CORT = 2 / (1 + exp(k * cort)) * sqrt(sum (y_i - x_i)^2), cort = sum dy_t dx_t / sqrt(sum dy_t^2 sum dx_t^2)` | unit of the data | [0, +inf] | 0 | Douzal-Chouakria & Nagabhushan (2007); k = 2 by default (k = 0: Euclidean). Parameters: k. |
