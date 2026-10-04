from dataclasses import dataclass, field
from .data_types import make_type

@dataclass
class Column:
    name: str
    kind: str
    lower: str | None = None
    upper: str | None = None

    @property
    def column_type(self):
        return make_type(self.kind, self.lower, self.upper)

    @property
    def label(self):
        suffix = f' [{self.lower};{self.upper}]' if self.kind == 'string(charInvl)' else ''
        return f'{self.name}: {self.kind}{suffix}'

@dataclass
class Row:
    values: list[str]

@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)

@dataclass
class Database:
    name: str
    tables: list[Table] = field(default_factory=list)
