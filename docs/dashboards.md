# Dashboards: KPIs and visuals

The analysis code is written once and shared by every CME. Each CME only chooses, in the
`analysis` section of its spec file (`src/destest/specs/cme/CME_<Series>_<Number>.yaml`),
which KPIs to compute and which tables and figures to show on its three dashboards.

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

**KPI functions** (`src/destest/analysis/kpis.py`), one number from one time series:

| Name | Result | Parameters |
|---|---|---|
| `steady_state` | mean of the last values | `last_n` (default: all) |
| `mean`, `minimum`, `maximum`, `final_value` | as named | – |
| `total` | sum × factor | `factor` |
| `integral` | ∫ value dt (trapezoidal) × factor, e.g. W over s → kWh with `factor: 2.7778e-7` | `factor` |

**Accuracy metrics** (`src/destest/analysis/accuracy_metric.py`), against the reference:

| Name | On | Unit |
|---|---|---|
| `relative_deviation` | KPI value | % |
| `absolute_deviation` | KPI value | unit of the KPI |
| `nmbe`, `cvrmse` | time series, point by point | % |
| `rmse`, `mae`, `max_abs_error` | time series, point by point | unit of the series |

**Visuals** (`src/destest/analysis/visuals.py`):

| Name | What | Main options |
|---|---|---|
| `data_check_table` | per submission: creation date, `destest check` status, closeness grade, errors and warnings (short) | `closeness` |
| `kpi_table` | KPI values, one column per submission, with deviation and the closeness grade | `kpis`, `deviation`, `closeness`, `warn_pct`, `bad_pct` |
| `metadata_table` | metadata side by side (`sections: all` for the whole file) | `sections` |
| `closeness_bar` | closeness grade, best first; the shown ones in colour, others grey | `colors` (`submission`, `rank`), `submissions` (`all`, `selected`: only the shown ones, rank among all) |
| `contributions_map` | map at the institutions' cities; a "Colour by" switch picks the metadata field (one map each) | `color_by` |
| `contributions_pie` | share of the submissions per tool, institution or country (donut); several `color_by` give a switch | `color_by` (list of `tool`, `institution`, `country`, `cme`), `height` |
| `contributions_timeline` | submissions per month, one square each, up to the current month (scrolls, opens at today); several `color_by` give a switch | `color_by` (list of `tool`, `institution`, `country`, `cme`), `min_months` |
| `deviation_heatmap` | submissions × KPIs, coloured by a metric | `kpis`, `metric`, `limit` |
| `kpi_bar` | one bar chart per KPI | `kpis`, `show_reference` |
| `profile` | several KPIs along an axis, e.g. temperatures along the network | `kpis`, `x_labels`, `y_title` |
| `time_series` | time series of some columns | `columns`, `show_reference` |
| `carpet` | carpet plot (e.g. hour of day × day) | `column`, `period` |

## Closeness to the reference

One grade (0–100) per submission summarises all KPIs:

1. for each KPI, every submission's distance to the reference |value − reference| is computed;
2. the closest submission scores **100**, the furthest **0**, the others linearly in between:
   100 × (worst − distance) / (worst − best); if all are equally close, all score 100;
3. the grade is the **mean of the KPI scores** (a missing KPI is left out).

It is shown in the KPI table (first row, with the rank), in the submissions table and in
`closeness_bar`. The scores are relative: on a KPI where all submissions agree almost
perfectly, a tiny difference still spreads the scores from 0 to 100.

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
  comments_and_observations:         # optional: bullets, last card of the overview
    - Comment 1
    - Observation 1
  kpis:
    - key: Q_loss_supply_i_h          # used by the visuals
      label: Heat loss supply i-h
      column: Q_loss_supply_i_h       # column key in result_data.columns
      function: steady_state          # a KPI function
      unit: W
  dashboards:
    overview:
      - visual: kpi_bar
        title: Heat loss and heat supplied
        options:
          kpis:
            - Q_loss_supply_i_h
            - Q_supplied
    detail: [...]
    comparison: [...]
```

`description`, `characteristics` and the reference (method, number of submissions and
`reference_note`) are shown in a card at the top of every dashboard, below the exercise
selection, and in the header of the HTML pages.

Everything is checked when the spec file is loaded (`uv run destest specs`): an unknown
KPI function, visual, parameter or option, or a KPI or column key that does not exist,
stops with a message naming the place in the file.

## Adding a building block

A new KPI function or visual is a Python function with a decorator; it is then available to
every CME:

```python
@kpi_function("degree_hours")
def degree_hours(values, time, *, base: float = 20.0) -> float | None: ...


@visual("scatter_kpis", kpi_options=("x", "y"))
def scatter_kpis(ctx, *, x: str, y: str) -> Figure: ...
```

Figures are Plotly figure specifications (`{"data": [...], "layout": {...}}`), plain JSON
that a web front end draws with plotly.js; no plotting library is needed in the package.
