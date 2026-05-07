# tiferet-h5 Domain Objects

**Package:** `tiferet_h5.domain`

## Overview

The domain layer defines three `DomainObject` subclasses that capture HDF5-specific structural concepts as first-class Tiferet models.  These objects are the Tiferet-side representation of the hierarchical and typed nature of HDF5 files — they do not directly interact with PyTables; that is the responsibility of the mapper and utility layers.

All three classes extend `tiferet.domain.DomainObject` (backed by Pydantic v2) and are **read-only at this layer**.  Mutation logic, if needed, belongs in Aggregate subclasses in the mappers layer.

---

## H5Column

**Module:** `tiferet_h5.domain.h5`

Represents a single typed column in an HDF5 table schema.  It is the Tiferet-side descriptor for one `Col` slot in a PyTables `IsDescription` subclass.

### Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `str` | yes | Column name as it appears in the HDF5 table. |
| `dtype` | `str` | yes | PyTables type descriptor string. Common values: `"string256"`, `"float64"`, `"int64"`, `"bool"`. For string columns the format is `"string<N>"` where `N` is the byte width. |
| `default` | `Any \| None` | no | Optional default value used when a field is absent during row writes. |
| `position` | `int \| None` | no | Optional explicit column sort position within the schema. |

### PyTables Correspondence

`H5Column` describes what would otherwise be a class-level `Col` attribute on a hand-written `IsDescription`:

```python
# Hand-written PyTables description
class FeatureDesc(tables.IsDescription):
    id   = tables.StringCol(256)   # dtype="string256"
    name = tables.StringCol(256)

# Tiferet equivalent
H5Column(name='id',   dtype='string256')
H5Column(name='name', dtype='string256')
```

`H5Column` instances are stored on `H5TableSchema` and are used by `TableObject.get_description()` when programmatic schema generation is needed.

---

## H5TableSchema

**Module:** `tiferet_h5.domain.h5`

Represents the full schema of an HDF5 table node.  It is the Tiferet-side equivalent of an entire `IsDescription` subclass combined with the node path it targets.

### Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `node_path` | `str` | yes | Absolute HDF5 path for the table, e.g. `"/features/calc"`. |
| `title` | `str \| None` | no | Optional human-readable title stored as HDF5 table metadata. |
| `columns` | `List[H5Column]` | no | Ordered list of column definitions. |

### Methods

#### `get_column(name: str) -> H5Column | None`

Look up a column definition by name.  Returns `None` if no column with that name exists.

```python
schema = H5TableSchema(
    node_path='/features/calc',
    columns=[
        H5Column(name='id',   dtype='string256'),
        H5Column(name='name', dtype='string256'),
    ],
)
col = schema.get_column('id')
# H5Column(name='id', dtype='string256', ...)
```

#### `column_names() -> List[str]`

Return column names in declaration order.

```python
schema.column_names()
# ['id', 'name']
```

### Role in the Mapper Layer

`H5TableSchema` is an informational/introspective object.  It does **not** drive `TableObject` at runtime — `TableObject` uses `_H5_TYPES` and `_DESCRIPTION` directly.  `H5TableSchema` is useful when you need to describe a table schema in domain configuration (e.g. a repository that validates or creates tables from a declarative spec).

---

## H5Node

**Module:** `tiferet_h5.domain.h5`

A lightweight descriptor for any navigable node in an HDF5 file.  It captures enough information to identify, classify, and inspect a node without holding a live PyTables handle.

### Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `path` | `str` | yes | Absolute HDF5 node path, e.g. `"/features/calc/steps"`. |
| `node_type` | `str` | yes | Classification: `"group"`, `"table"`, `"array"`, or `"leaf"`. |
| `title` | `str \| None` | no | Optional human-readable title stored as node metadata. |
| `attrs` | `Dict[str, Any]` | no | Snapshot of the node attribute set (`_v_attrs`) as a plain Python dict. |

### Usage

`H5Node` is intended for listing and navigating the HDF5 hierarchy programmatically, or for passing node metadata through domain events without carrying a live file handle.  A repository can populate it by reading `node._v_pathname`, `type(node).__name__`, and `node._v_title` from an open `H5Client`.

```python
node = H5Node(
    path='/features/calc',
    node_type='group',
    title='Calculator Features',
    attrs={'schema_ver': '1.0'},
)
```

---

## Import Reference

```python
from tiferet_h5 import H5Column, H5TableSchema, H5Node
# or
from tiferet_h5.domain import H5Column, H5TableSchema, H5Node
```
