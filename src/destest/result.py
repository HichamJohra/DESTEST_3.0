"""The shared result types of every check: `Issue` and `CheckResult`.

Every checker returns a subclass of `CheckResult`:

- `filename_check.NameCheck`: one file name
- `data_check.DataCheck`: the content of one ResultData file
- `metadata_check.MetadataCheck`: the content of one ResultMetadata file
- `check.FileReport`: everything about one file (`destest check`)

They all offer the same interface: `issues`, `errors`, `warnings`, `ok`, `status`
and `add()`. Each subclass only adds what is specific to it (e.g. the values read
from a name, the number of data rows).

    >>> r = CheckResult()
    >>> r.add("warning", "rows", "9 data rows; 10 expected.")
    >>> r.ok, r.status, str(r.warnings[0])
    (True, 'warning', 'warning: 9 data rows; 10 expected.')
"""

from dataclasses import dataclass, field

#: Levels an issue can have. `ignore` (allowed in the spec files) is never recorded.
LEVELS: tuple[str, ...] = ("error", "warning")


@dataclass
class Issue:
    """One problem found.

    `field` says where: a name part (e.g. `series`), a place in a file
    (e.g. `header`, `modeller.first_name`) or a check (e.g. `pairing`).
    `stage` says which check found it (`name` or `content`), when several are combined.
    """

    level: str  # "error" or "warning"
    field: str
    message: str
    stage: str = ""

    def __str__(self) -> str:
        return f"{self.level}: {self.message}"


@dataclass
class CheckResult:
    """Base of every check result: a list of issues and what follows from it."""

    issues: list[Issue] = field(default_factory=list, kw_only=True)

    @property
    def errors(self) -> list[Issue]:
        """Problems that make the checked item invalid."""
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        """Things that are allowed but probably unintended."""
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        """True when there is no error (warnings are allowed)."""
        return not self.errors

    @property
    def status(self) -> str:
        """`ok`, `warning` or `error`."""
        return "error" if self.errors else ("warning" if self.warnings else "ok")

    def add(self, level: str, where: str, message: str, stage: str = "") -> None:
        """Record an issue. Level `ignore` (from a spec setting) records nothing."""
        if level in LEVELS:
            self.issues.append(Issue(level, where, message, stage))
