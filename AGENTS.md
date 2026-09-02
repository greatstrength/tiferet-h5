# AGENTS.md — tiferet-h5

## Project Overview

**tiferet-h5** is an HDF5 infrastructure extension package for the [Tiferet](https://github.com/greatstrength/tiferet) framework.  It provides a full Domain-Driven Design (DDD) layer over PyTables, enabling structured, aliased, and repository-backed access to HDF5 files within Tiferet applications.

- **Repository:** https://github.com/greatstrength/tiferet-h5
- **Branch:** `v1.x-proto`
- **Python:** ≥ 3.10
- **Version:** `1.0.0a6`
- **Dependencies:** `tiferet >= 2.0.3, < 2.1`, `tables >= 3.10.0`

## Architecture

### Layer Overview

```
tiferet_h5/
├── domain/         DomainObject subclasses (H5Column, H5TableSchema, H5Node)
├── interfaces/     H5Service abstract contract (extends FileService)
├── mappers/        TableObject + NodeObject base classes
├── utils/          H5Client concrete utility (alias: H5); also hosts its own error code constants
└── repos/          H5Repository generic base
```

### Key Concepts

**HDF5 Storage Primitives**

HDF5 has two fundamentally different storage primitives, each served by its own mapper base class:

- **Tables** (`tables.Table`) — schema-defined columnar records, analogous to a database table.  Represented by `TableObject`.
- **Node Attributes** (`node._v_attrs`) — lightweight key-value metadata on any group or leaf node.  Represented by `NodeObject`.

**`TableObject`** (`mappers/settings.py`)
- The HDF5-native analogue of Tiferet's `TransferObject`.
- Declares `_H5_TYPES: ClassVar[Dict[str, Any]]` — maps HDF5 column names to PyTables `Col` instances.
- Declares `_DESCRIPTION: ClassVar[Optional[type]]` — optional explicit `IsDescription`; auto-generated from `_H5_TYPES` if absent.
- `to_row(table)` serializes via `model_dump(by_alias=True)` so `serialization_alias` values map to column names.
- `from_row(row)` accepts `tables.Row`, NumPy records, or plain dicts; normalizes bytes/scalars via `normalize_value`.
- `get_description()` auto-generates and caches the `IsDescription` subclass.
- `verify_schema(table)` checks `_H5_TYPES` against a live table's column names.

**`NodeObject`** (`mappers/settings.py`)
- Extends Tiferet's `TransferObject` for attribute-oriented HDF5 storage.
- Ships with `_ROLES = {'to_h5.attrs': {'by_alias': True}}` so `to_attrs()` applies `serialization_alias` values as HDF5 attribute keys by default.
- `to_attrs(role='to_h5.attrs')` serializes via `to_primitive(role=role)`.
- `from_attrs(attrs)` normalizes bytes/numpy scalars then calls `model_validate`.

**`H5Client`** (`utils/h5.py`, alias `H5`)
- Extends `FileLoader` and implements `H5Service`.
- Overrides `open_file()` / `close_file()` to use `tables.open_file()` instead of Python's `open()`.
- Valid modes: `'r'`, `'r+'`, `'w'` (truncates!), `'w-'`, `'a'` (default — never truncates).
- All operations guard against `h5file is None` and raise `ServiceError` (`tiferet.interfaces`) via `ServiceError.raise_for()` — never `TiferetError`. Error code constants live beside the raise sites in `utils/h5.py`, not in a separate assets module.
- `get_node_attrs()` uses `_v_attrnamesuser` to exclude PyTables system attributes.

**`H5Repository`** (`repos/h5.py`)
- Extends `Service`; stores `h5_file` path and default `mode`.
- `client(mode=None)` returns a new `H5Client` instance (not yet open) for use as a context manager per operation.

### Aliasing Contract

`_H5_TYPES` keys are HDF5 **column names** (not Python field names).  When they differ, use Pydantic aliases:

```python
service_id: str = Field(
    serialization_alias='svc',          # HDF5 column name
    validation_alias=AliasChoices('svc', 'service_id'),
)
_H5_TYPES = {'svc': tables.StringCol(256)}
```

`to_row()` uses `model_dump(by_alias=True)` → alias becomes the column key.
`from_row()` calls `model_validate()` → `validation_alias` resolves alias back to Python field.

The same pattern applies to `NodeObject` with `to_attrs()` / `from_attrs()`.

### Nested Object Pattern

Use a `NodeObject` subclass for group-level scalar metadata and a `TableObject` subclass for the child collection:

```
/catalog/
    items/
        widget/           ← group node, attrs via WidgetGroupObject
            tags          ← table node, rows via TagTableObject
```

See [docs/guides/mappers.md](docs/guides/mappers.md) for the full example.

## Structured Code Style

All code follows the Tiferet artifact comment hierarchy.  **This is mandatory.**

### Comment Levels

- `# *** <section>` — Top-level: `imports`, `constants`, `classes`, `utils`, `repos`, `interfaces`, `models`, `mappers`
- `# ** <category>: <name>` — Mid-level: `core`, `infra`, `app` (imports); `util: <name>`, `repo: <name>`, `interface: <name>`, `model: <name>`, `mapper: <name>`, `class: <name>`
- `# * <component>` — Low-level: `attribute: <name>`, `init`, `method: <name>`, `method: <name> (static)`

### Spacing Rules

- One empty line between `# ***` and first `# **`.
- One empty line between each `# *` section.
- One empty line after docstrings and between code snippets within methods.

### Docstrings

RST format with `:param`, `:type`, `:return:`, `:rtype:` for all public methods.

### No Private Methods

All helper methods must be public.  Use the `(static)` suffix in the artifact comment for static methods:

```python
# * method: normalize_value (static)
@staticmethod
def normalize_value(value: Any) -> Any:
    ...
```

## Domain Objects

Defined in `tiferet_h5/domain/h5.py`.  All extend `tiferet.domain.DomainObject` (Pydantic v2).

- **`H5Column`** — Single typed column descriptor (`name`, `dtype`, `default`, `position`).
- **`H5TableSchema`** — Full table schema (`node_path`, `title`, `columns`).  Methods: `get_column`, `column_names`.
- **`H5Node`** — Navigable node descriptor (`path`, `node_type`, `title`, `attrs`).

These are **read-only** structural objects.  Mutation logic goes in Aggregate subclasses.

See [docs/guides/domain.md](docs/guides/domain.md).

## Interface

`H5Service` is defined in `tiferet_h5/interfaces/h5.py`.  It extends `tiferet.interfaces.FileService` and declares abstract methods for:

- File lifecycle: `open_file`, `close_file`, `flush`, `__enter__`, `__exit__`
- Node existence: `node_exists`
- Groups: `create_group`, `get_group`
- Tables: `create_table`, `get_table`, `get_or_create_table`, `append_rows`, `read_rows`, `query`, `remove_rows`
- Arrays: `create_array`, `get_array`
- Attributes: `set_node_attr`, `get_node_attr`, `get_node_attrs`

## Mappers

Defined in `tiferet_h5/mappers/settings.py`.

**`TableObject`** — Use for columnar table data.  Key class variables: `_H5_TYPES`, `_DESCRIPTION`.  Key methods: `get_description`, `to_row`, `from_row`, `map`, `from_model`, `normalize_value`, `encode_value`, `verify_schema`, `to_primitive`.

**`NodeObject`** — Use for node attribute data.  Inherits `_ROLES`, `to_primitive`, `map`, `from_model` from `TransferObject`.  Adds: `to_attrs`, `from_attrs`.

See [docs/guides/mappers.md](docs/guides/mappers.md).

## Utils

`H5Client` (`tiferet_h5/utils/h5.py`, alias `H5`) — Concrete implementation of `H5Service`.  Default mode is `'a'`.  Always use as a context manager.  See [docs/guides/utils/h5.md](docs/guides/utils/h5.md).

## Repos

`H5Repository` (`tiferet_h5/repos/h5.py`) — Generic base.  Extend it and call `self.client()` inside each method to get a context-managed `H5Client`.

```python
class MyRepository(H5Repository):
    def save(self, obj):
        with self.client() as h5:
            t = h5.get_or_create_table('/path/to/table', MyTableObject.get_description())
            MyTableObject.from_model(obj).to_row(t)
            t.flush()
```

## Error Handling

All errors are raised as `ServiceError` (`tiferet.interfaces`) via `ServiceError.raise_for()` — never `TiferetError`. Error code constants are hosted beside their raise sites in `tiferet_h5/utils/h5.py` (there is no `assets/` layer).

| Constant | When raised |
|---|---|
| `H5_FILE_NOT_FOUND_ID` | File absent on read, parent dir absent on write/append, or a low-level open failure. |
| `H5_INVALID_FILE_ID` | Missing `.h5` / `.hdf5` extension in read mode. |
| `H5_INVALID_MODE_ID` | Mode not in `{'r', 'r+', 'w', 'w-', 'a'}`. |
| `H5_FILE_ALREADY_OPEN_ID` | `open_file()` called on an already-open client. |
| `H5_CONN_NOT_INITIALIZED_ID` | Operation attempted without an open file handle. |
| `H5_NODE_NOT_FOUND_ID` | Requested HDF5 path does not exist. |
| `H5_GROUP_CREATE_FAILED_ID` | `create_group()` (or an intermediate parent group) raised a PyTables exception. |
| `H5_TABLE_CREATE_FAILED_ID` | `create_table()` raised a PyTables exception. |
| `H5_QUERY_FAILED_ID` | `read_rows()` / `query()` raised a PyTables exception. |
| `H5_WRITE_FAILED_ID` | `append_rows()`, `remove_rows()`, or `create_array()` failed. |

Import pattern inside the package:

```python
from tiferet.interfaces import ServiceError
from .h5 import H5_NODE_NOT_FOUND_ID

ServiceError.raise_for(self, H5_NODE_NOT_FOUND_ID, f'Node not found at path: {path}.', path=path)
```

## Package Exports

`tiferet_h5/__init__.py` exports:

```python
# Domain
H5Column, H5TableSchema, H5Node

# Interface
H5Service

# Mappers
TableObject, NodeObject

# Utils
H5Client, H5   # H5 is an alias for H5Client

# Repos
H5Repository
```

## Key Files for Orientation

- `tiferet_h5/__init__.py` — Version and public exports
- `tiferet_h5/domain/h5.py` — Domain objects
- `tiferet_h5/interfaces/h5.py` — `H5Service` abstract contract
- `tiferet_h5/mappers/settings.py` — `TableObject` and `NodeObject` base classes
- `tiferet_h5/utils/h5.py` — `H5Client` concrete utility and its H5 error code constants
- `tiferet_h5/repos/h5.py` — `H5Repository` generic base

## Contributing

1. Work from the `v1.x-proto` branch.  Feature branches should be named `<issue-number>-<lowercase-hyphenated-title>`.
2. Follow the structured code style documented above.  No private methods.
3. All errors must use `ServiceError.raise_for()` with a constant hosted beside its raise site (e.g. `utils/h5.py`).
4. Separate functional changes from documentation in distinct commits.
5. Include `Co-Authored-By: Oz <oz-agent@warp.dev>` in every commit made with AI assistance.
6. Publish a Collaboration Report on the issue upon completion.
