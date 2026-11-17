# DESTEST 3.0

Tools and, in time, a web app for the **District Energy Simulation Test Procedure
(DESTEST)**: common modelling exercises (CMEs) in which several simulation tools model
the same district energy system so their results can be compared.

The first building block is the `destest.filename_check` package, which checks that submitted
result files follow the [naming convention](naming-convention.md):

```console
$ uv run destest check-names "Result data" --recursive
Checking 6 file names in "Result data"

...
[WARN] CME_DHN_1/ResultData_DESTEST_CME_DHN_1_SIM VICUS_-_TUD_Hauke_Hirsch_2022_01_01_12_00_00.csv
         warning Modelling tool 'SIM VICUS' contains spaces; prefer '-' or CamelCase.
         warning Tool version '-' contains no digit - is a part missing, or does the tool name contain '_'?
[OK  ] CME_DHN_1/ResultData_DESTEST_CME_DHN_1_TRNSYS_2021_TUD_Clemens_Felsmann_2021_01_01_12_00_00.csv
[OK  ] CME_DHN_1/ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv

Summary: 6 valid (4 with warnings), 0 with errors - 6 files checked.
```

## Where to go next

| I want to… | Read |
|---|---|
| Install the tools and check result files | [Getting started](getting-started.md) |
| Know how result files must be named | [Naming convention](naming-convention.md) |
| Find where code belongs in the repository | [Project structure](project-structure.md) |
| Change the code, run the checks, update these docs | [Development](development.md) |
| Use the functions from Python | [API reference](reference.md) |
