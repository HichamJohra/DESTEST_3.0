# API reference

Generated from the docstrings in `src/destest`.

## Checking names

::: destest.filename_check.validate
    options:
      members:
        - check_name
        - check_files
        - check_folder
        - check_location
        - NameCheck
        - Issue

## Building names

::: destest.filename_check.build

## Reports

::: destest.filename_check.report

## The convention

::: destest.filename_check.convention
    options:
      members:
        - SERIES
        - DATA_TYPES
        - EXTENSIONS
        - FIELDS
        - Field
        - template
        - describe

## Spec files

::: destest.specs
    options:
      members:
        - load_naming_convention
        - load_cme_spec
        - list_cme_specs
        - SpecError

::: destest.specs.schema
    options:
      members:
        - NamingConvention
        - CmeSpec

## ResultMetadata files

::: destest.metadata_check.validate
    options:
      members:
        - check_metadata
        - check_metadata_folder
        - MetadataCheck

::: destest.metadata_check.template

## ResultData files

::: destest.data_check.validate
    options:
      members:
        - check_data
        - check_data_folder
        - check_data_text
        - DataCheck

::: destest.data_check.template

## Everything at once

::: destest.check

## Consistency rules

::: destest.specs.expressions
    options:
      members:
        - parse_rule
        - check_rule

## Result types

::: destest.result

## New submission

::: destest.submission
