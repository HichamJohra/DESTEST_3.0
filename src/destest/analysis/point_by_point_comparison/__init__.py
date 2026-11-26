"""Point-by-point comparison of series with a reference series.

* `point_by_point_difference.py`: the comparison metrics of Technical Report 314 (MBE,
  CVRMSE, RMSE, R2, ...), on two aligned series, y (simulated) against x (reference);
* `time_series.py`: what depends on time (hourly / daily aggregation, elastic distances);
* `data_profiles.py`: all other data series, e.g. values at the nodes along a network;
* `reference_time_series.py`, `reference_data_profiles.py`: the reference, point by point,
  from all submissions (median by default; method from the CME spec file);
* `time_series_to_reference.py`, `data_profiles_to_reference.py`: the metrics of each
  submission against that reference.

References: Johra et al. (2021), https://doi.org/10.26868/25222708.2021.30410;
Johra et al. (2023), DCE Technical Report No. 314, https://doi.org/10.54337/aau533917780;
Johra et al. (2023), Building Simulation 2023, https://doi.org/10.26868/25222708.2023.1309.
"""

from .data_profiles import profile_metric, profile_values
from .data_profiles_to_reference import compare_data_profiles
from .point_by_point_difference import POINT_METRICS, Metric, central_value, point_metric
from .reference_data_profiles import reference_data_profile
from .reference_time_series import reference_time_series
from .time_series import TIME_SERIES_METRICS, all_time_series_metrics, series_metric
from .time_series_to_reference import MetricRequest, SeriesComparison, compare_time_series

__all__ = [
    "POINT_METRICS",
    "TIME_SERIES_METRICS",
    "Metric",
    "MetricRequest",
    "SeriesComparison",
    "all_time_series_metrics",
    "central_value",
    "compare_data_profiles",
    "compare_time_series",
    "point_metric",
    "profile_metric",
    "profile_values",
    "reference_data_profile",
    "reference_time_series",
    "series_metric",
]
