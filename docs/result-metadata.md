# ResultMetadata files

Every ResultData file (`.csv`) comes with one ResultMetadata file (`.yaml`) in the same
folder, with the same name apart from the data type and the extension. It describes that
one submission: who made it, with which tool, how the simulation was set up and which
modelling choices were made.

## Get a template

The template is written from the spec files, so it always matches what the checker expects.
Given the ResultData file, everything that follows from its name is filled in already:

```bash
uv run destest metadata-template "Result data/CME_DHN_1/ResultData_DESTEST_CME_DHN_1_TRNSYS_2022_TUD_Clemens_Felsmann_2022_01_01_12_00_00.csv" -o "Result data/CME_DHN_1"
uv run destest metadata-template CME_DHN_1          # blank template, printed
```

## Sections

| Section | Content | Fields defined in |
|---|---|---|
| `submission_info` | CME, name of the ResultData file, creation date and time | `specs/result_metadata.yaml` |
| `modeller` | Name, institution (short and full), city and country, ORCID | `specs/result_metadata.yaml` |
| `modelling_tool` | Name, version, licence, website, libraries | `specs/result_metadata.yaml` |
| `simulation_config` | Solver, time step, tolerance, computation time, computer | the CME's file, `specs/cme/CME_<Series>_<Number>.yaml` |
| `model_details` | Modelling choices the CME description leaves open | the CME's file |
| `deviations` | Free text: every departure from the CME description | `specs/result_metadata.yaml` |
| `other_comments` | Free text | `specs/result_metadata.yaml` |

## What the checker reports

```bash
uv run destest check-metadata "Result data"
```

All of these are errors:

- a section or key is **missing**, or there is a section or key that is **not in the spec**;
- a **required** value is empty;
- a value is a list or a sub-section instead of a single value;
- a value marked `must_match` in the spec does not agree with the file name, the CME or
  the name of the ResultData file (e.g. `modeller.last_name`, `modelling_tool.version`);
- `metadata_format_version` is not the current one;
- the file is not valid YAML, or its name is not a valid ResultMetadata name.

All values are free text. Text that looks like a number (a version such as `18.40`) must be
written in quotes, otherwise YAML reads it as a number (`18.4`) and it no longer matches the
file name; the checker says so.

!!! note "Public repository"
    ResultMetadata files are published together with the results. Do not put information in
    them that should not be public.

## Changing the fields

- Fields used in every CME: edit `src/destest/specs/result_metadata.yaml`.
- `simulation_config` and `model_details` of one CME: edit its file in `src/destest/specs/cme/`.

Each field has a `key`, `required` (true/false) and a `description` that becomes the comment
in the template. Run `uv run destest specs` to check the spec files after a change.
