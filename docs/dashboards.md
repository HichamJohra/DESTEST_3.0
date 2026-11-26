# Dashboards: what is compared, and the visuals

The analysis code is written once and shared by every CME. Each CME only chooses, in the
`analysis` section of its spec file (`src/destest/specs/cme/CME_<Series>_<Number>.yaml`),
what to compare and which tables and figures to show on its three dashboards.

```bash
uv run destest dashboard CME_DHN_1                                    # overview, all submissions
uv run destest dashboard CME_DHN_1 --kind detail --submission Laluce  # one submission
uv run destest dashboard CME_DHN_1 --kind comparison --submission TRNSYS_2022 --submission "SIM VICUS"
uv run destest dashboard CME_DHN_1 -o output/overview.json            # JSON for a web front end
```

`--submission` takes any part of a file name or label that matches exactly one submission.
Pages are written to `output/` (ignored by git) unless `-o` says otherwise. The HTML page
draws its figures with plotly.js, loaded from the internet.

## The three dashboards

| Kind | Shows | Reference |
|---|---|---|
| `overview` | all submissions of the CME | median (or mean) of all submissions |
| `detail` | one submission | same |
| `comparison` | a selection of submissions | same |

## Building blocks

Every number on the dashboards is a **compared item**: one value per submission, scored
in the accuracy grade. There are three kinds:

**General comparison** (`src/destest/analysis/general_comparison/`): one value per
submission, from one or more columns.

| Function | Module | Result | Inputs | Parameters |
|---|---|---|---|---|
| `steady_state` | data_aggregates | mean of the last values | `values` | `last_n` (default: all) |
| `mean`, `minimum`, `maximum`, `final_value` | data_aggregates | as named | `values` | – |
| `total` | data_aggregates | sum × factor | `values` | `factor` |
| `integral` | data_aggregates | ∫ value dt (trapezoidal); W over s gives J | `values` | `to_unit` (J, kJ, MJ, Wh, kWh, MWh), `factor` |
| `heat_balance_error` | physics_check | (ΣQ − Σ ṁ·cp·ΔT) / Σ ṁ·cp·ΔT × 100, in % | `power`, `m_flow`, `T_hot`, `T_cold` | `cp`, `m_flow_unit`, `min_flow` |
| `temperature_difference` | physics_check | mean of T_hot − T_cold (optionally only with flow) | `T_hot`, `T_cold`, optional `m_flow` | `min_flow` |
| `relative_difference` | physics_check | (mean a − mean b) / mean of both × 100, in % | `a`, `b` | – |
| `time_steps_below` | physics_check | number of time steps below `threshold − tolerance` | `values`, optional `m_flow` | `threshold`, `tolerance`, `min_flow` |

A data aggregate is compared with the **median of all submissions**; a physics check with
its **`target`** (e.g. 0 %, 30 K), given in the spec file.

**Point-by-point comparison** (`src/destest/analysis/point_by_point_comparison/`): a series
against the reference series (point-by-point median of all submissions), with the metrics
of Technical Report 314 (MBE, CVRMSE, RMSE, R², ... see [Comparison metrics](comparison-metrics.md)):

* `time_series`: the columns of the result file as time series (all, or a list);
* `data_profiles`: several columns read as one profile, e.g. the supply temperature at the
  nodes i, h, g, f, e and SimpleDistrict_1 (one value per column: its mean).

Each metric value is scored on its distance to the metric's **ideal value** (0 for MBE and
CVRMSE, 1 for r, ...).

**Differences from the reference** (tables and heatmaps): `relative_deviation` (in %) and
`absolute_deviation` (in the unit of the value) of a value from its median.

**Visuals** (`src/destest/analysis/visuals.py`):

| Name | What | Main options |
|---|---|---|
| `data_check_table` | per submission: creation date, `destest check` status, closeness grade, errors and warnings (short) | `closeness`, `first_column`, `ranked` (default: best grade on top) |
| `results_table` | all compared items, one column per submission: target (median of all, target or ideal), acceptable and critical deviation (yellow / red), weights and the accuracy grade | `items` (`all`, `general`, `aggregates` or keys), `deviation`, `closeness`, `weights`, `limits`, `zero_weight_last` (default: items with weight 0 last, below a separator), `ranked` (default: submissions ordered by grade, best on the left) |
| `metadata_table` | metadata side by side (`sections: all` for the whole file) | `sections` |
| `closeness_bar` | closeness grade, best first; the shown ones in colour, others grey | `colors` (`submission`, `rank`), `submissions` (`all`, `selected`: only the shown ones, rank among all) |
| `contributions_map` | map at the institutions' cities; a "Colour by" switch picks the metadata field (one map each) | `color_by` |
| `contributions_pie` | share of the submissions per tool, institution or country (donut); several `color_by` give a switch | `color_by` (list of `tool`, `institution`, `country`, `cme`), `height` |
| `contributions_timeline` | submissions per month, one square each, up to the current month (scrolls, opens at today); several `color_by` give a switch | `color_by` (list of `tool`, `institution`, `country`, `cme`), `min_months` |
| `deviation_heatmap` | submissions × compared items, coloured by a difference (`relative_deviation`) or a metric on the item's column (`NMBE`, `CVRMSE`, ...) | `items` (`general` by default, `aggregates`, `all` or keys), `metric`, `limit` |
| `value_bar` | one bar chart per compared item | `items`, `show_reference` |
| `profile` | several compared items along an axis, e.g. temperatures along the network | `items`, `x_labels`, `y_title` |
| `time_series` | time series of some columns | `columns`, `show_reference` |
| `carpet` | carpet plot (e.g. hour of day × day) | `column`, `period` |

## Highlight limits

In every table, the first column stays in place when scrolling sideways.

In the results table, the column **Target** gives each item's reference: the median of all
submissions ("reference: median of 7"), the target of a physics check ("target") or the
ideal value of a metric ("ideal"). The columns **Acceptable deviation** and **Critical
deviation** come from `limits` in the CME spec file; a value beyond them is highlighted
yellow, respectively red.

* values compared with the median: deviation in **%** of the median (`default_limits` of
  the analysis section, or `limits` of the item);
* physics checks and metrics: **difference** from the target or ideal value, in the unit of
  the item (`limits` of the item or metric);
* `mode: relative | absolute` in `limits` overrides this choice. Without limits, nothing is
  highlighted.

## Closeness to target (accuracy grade)

One grade (0–100) per submission summarises all compared items, as the summary Accuracy
Grade of the DESTEST comparison tool (Johra et al., 2021):

1. for each item, every submission's distance to the item's reference is computed: the
   median of all submissions (data aggregates), the target (physics checks) or the ideal
   value of the metric (point-by-point metrics);
2. the closest submission scores **100**, the furthest **0**, the others linearly in between:
   100 × (worst − distance) / (worst − best); if all are equally close, all score 100;
3. the grade is the **weighted mean of the item scores**, with each item's `weight` from the
   CME spec file (default 1; 0 = shown but not counted; a missing value is left out).

It is shown in the results table (first row, with the rank; weights in the column "Weight",
their sum in the first row), in the contributions table and in `closeness_bar`. The scores
are relative: on an item where all submissions agree almost perfectly, a tiny difference
still spreads the scores from 0 to 100.

## Map of contributions

`contributions_map` places each submission at `modeller.institution_city` and
`modeller.institution_country` from its metadata file, using the coordinates in
`src/destest/specs/locations.yaml`. An unknown city falls back to the centre of its country;
add the city to that file when a new institution joins.

## In a CME spec file

```yaml
cme:
  # ... series, exercise_number, full_title, description_reference, status
  description: >-                    # what the exercise tests, a few sentences
    Checks that the fundamental equations for pressure drop and heat loss ...
  characteristics:                   # label: value, shown in this order
    Simulation: Steady state (constant boundary conditions)
    Heat source: Ideal source at node i, constant supply temperature 70 °C

analysis:
  reference: median                  # median | mean of all valid submissions
  reference_note: >-                 # optional: why this reference
    There is no measured or analytical truth for this exercise ...
  default_limits:                    # highlight limits of values compared with the median
    acceptable: 5                    # yellow beyond 5 % from the median
    critical: 20                     # red beyond 20 %
  comments_and_observations:         # optional: bullets, last card of the overview
    - Comment 1
    - Observation 1
  general_comparison:                # one value per submission
    - key: Q_loss_supply_i_h          # used by the visuals
      label: Heat loss supply i-h
      column: Q_loss_supply_i_h       # column key in result_data.columns
      function: steady_state          # a data aggregate
      unit: W
      weight: 1                       # share in the accuracy grade (default 1)
    - key: heat_balance_source
      label: Heat balance at the source (Q vs m cp dT)
      function: heat_balance_error    # a physics check
      inputs: {power: Q_supplied, m_flow: m_flow_supply_i, T_hot: T_supply_i, T_cold: T_return_i}
      params: {cp: 4180, m_flow_unit: kg/h}
      unit: "%"
      target: 0                       # compared with the target, not the median
      limits: {acceptable: 0.5, critical: 2}   # difference from the target, in its unit
  point_by_point_comparison:          # series against the reference series
    metrics:                          # names, or {name, weight, params, limits}
      - MBE
      - {name: CVRMSE, limits: {acceptable: 15, critical: 30}}
    time_series:                      # optional: columns compared as time series
      columns: all
    data_profiles:                    # optional: columns read as one profile
      - key: supply_temperature_profile
        label: Supply temperature along the network
        points: [T_supply_i, T_supply_h, T_supply_g, T_supply_f, T_supply_e, T_supply_district]
        positions: [i, h, g, f, e, SimpleDistrict_1]
        unit: degC
  dashboards:
    overview:
      - visual: value_bar
        title: Heat loss and heat supplied
        options:
          items:
            - Q_loss_supply_i_h
            - Q_supplied
    detail: [...]
    comparison: [...]
```

`description`, `characteristics` and the reference (method, number of submissions and
`reference_note`) are shown in a card at the top of every dashboard, below the exercise
selection, and in the header of the HTML pages.

Everything is checked when the spec file is loaded (`uv run destest specs`): an unknown
function, input, metric, visual, parameter or option, or an item or column key that does
not exist, stops with a message naming the place in the file.

## Adding a building block

A new general-comparison function, comparison metric or visual is a Python function with a
decorator; it is then available to every CME:

```python
@general_function("degree_hours", "data_aggregate")  # general_comparison/
def degree_hours(values, time, *, base: float = 20.0) -> float | None: ...


@point_metric(
    "MyMetric",
    full_name="...",
    group="...",
    equation="...",
    unit="%",
    value_range="[0, +inf]",
    optimum=0.0,
)  # point_by_point_comparison/
def my_metric(y, x) -> float | None: ...


@visual("scatter_items", item_options=("x", "y"))
def scatter_items(ctx, *, x: str, y: str) -> Figure: ...
```

After adding a metric, run `uv run python scripts/make_metrics_doc.py` to update the
[Comparison metrics](comparison-metrics.md) page (a test checks it is current).

Figures are Plotly figure specifications (`{"data": [...], "layout": {...}}`), plain JSON
that a web front end draws with plotly.js; no plotting library is needed in the package.
