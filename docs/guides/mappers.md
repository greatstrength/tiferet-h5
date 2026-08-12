# tiferet-h5 Mappers

**Package:** `tiferet_h5.mappers`

## Overview

The mappers layer bridges Tiferet domain objects with HDF5 storage.  It introduces two base classes that mirror Tiferet's `TransferObject` but are adapted to HDF5's two fundamental storage primitives:

| Class | Storage primitive | PyTables API |
|---|---|---|
| `TableObject` | Columnar table rows | `tables.Table`, `tables.IsDescription` |
| `NodeObject` | Group/leaf attributes | `node._v_attrs` |

Both classes extend Tiferet base classes and follow the same `_ROLES` / alias conventions used throughout the framework, so the serialization contract is consistent whether you are writing YAML, JSON, or HDF5.

---

## TableObject

**Module:** `tiferet_h5.mappers.settings`

The HDF5-native analogue of Tiferet's `TransferObject`.  Where `TransferObject` serializes via `model_dump()` → dict → YAML/JSON, `TableObject` serializes to and from typed PyTables table rows (NumPy structured records).

### Class Variables

#### `_H5_TYPES: ClassVar[Dict[str, Any]]`

Maps HDF5 **column names** to PyTables `Col` instances.  The dict keys are the names that will appear in the HDF5 file; they should match the `serialization_alias` of the corresponding Pydantic field when aliasing is used.

```python
class ItemTableObject(TableObject):
    name: str = Field(default='')
    price: float = Field(default=0.0)
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name':  tables.StringCol(256),
        'price': tables.Float64Col(),
    }
```

#### `_DESCRIPTION: ClassVar[Optional[type]]`

An explicit `tables.IsDescription` subclass.  When set it is returned directly by `get_description()` and `_H5_TYPES` is ignored for schema generation.  Use this when you need fine-grained PyTables control (e.g. chunking, expected rows, column ordering).

If `_DESCRIPTION` is `None` (the default), `get_description()` auto-generates it from `_H5_TYPES` and caches the result on the class.

### Aliasing Contract

`_H5_TYPES` keys are **HDF5 column names**.  When a domain field has a different Python name, declare `serialization_alias` (the HDF5 column name) and `validation_alias` (accepting both names on read):

```python
class StepTableObject(TableObject):
    service_id: str = Field(
        default='',
        serialization_alias='svc',
        validation_alias=AliasChoices('svc', 'service_id'),
    )
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'svc': tables.StringCol(256),  # matches serialization_alias
    }
```

`to_row()` calls `model_dump(by_alias=True)` internally, so the alias is automatically applied when writing.  `from_row()` passes the column dict through `model_validate()`, which resolves the `validation_alias` back to the canonical Python field name.

### Methods

#### `get_description() -> type` _(classmethod)_

Return the `IsDescription` subclass for this mapper.  Auto-generates from `_H5_TYPES` on first call and caches the result.

```python
desc = StepTableObject.get_description()
table = h5file.create_table('/steps', desc, title='Steps')
```

Raises a plain `ValueError` if neither `_H5_TYPES` nor `_DESCRIPTION` is set. This is deliberately **not** a `ServiceError`: it is a class-authoring-time mistake caught the first time a mapper subclass is used, not a runtime infrastructure failure, so it does not belong to `H5Client`'s `ServiceError` contract (see [docs/guides/utils/h5.md](utils/h5.md#error-handling)).

#### `to_row(table: tables.Table) -> None`

Append this object as a new row to an open PyTables `Table`.  Encodes string values to bytes for `StringCol` columns; replaces `None` with type-appropriate defaults.  Does **not** flush — call `table.flush()` when the write sequence is complete.

```python
with H5Client('data.h5', mode='a') as h5:
    t = h5.get_or_create_table('/steps', StepTableObject.get_description())
    obj = StepTableObject(service_id='add_event')
    obj.to_row(t)
    t.flush()
```

#### `from_row(row: Any) -> TableObject` _(classmethod)_

Construct a `TableObject` from a PyTables `Row` object, a NumPy record, or a plain dict (as returned by `H5Client.read_rows()`).  Decodes bytes to `str` and converts NumPy scalars to Python natives before calling `model_validate`.

```python
rows = h5.read_rows('/steps')
objs = [StepTableObject.from_row(r) for r in rows]
```

#### `to_primitive(**overrides) -> Dict[str, Any]`

Serialize to a plain Python dict using canonical field names (no aliases).  Useful for debugging or when dict-based serialization is needed alongside row-based storage.

#### `map(target: Type[Aggregate], **overrides) -> Aggregate`

Map this object to a domain `Aggregate` instance.  Calls `to_primitive()` and constructs `target(**data)`.

```python
step_agg = step_obj.map(FeatureStepAggregate)
```

#### `from_model(model: DomainObject, **overrides) -> TableObject` _(classmethod)_

Create a `TableObject` from an existing domain model or aggregate.  Uses `model_dump(by_alias=False)` to extract canonical field values.

```python
table_obj = StepTableObject.from_model(step_aggregate)
```

#### `normalize_value(value: Any) -> Any` _(static)_

Decode `bytes` → `str` and convert NumPy scalars → Python natives.  Called internally by `from_row()` but also available for custom subclass logic.

#### `encode_value(value: Any, col: Any) -> Any` _(static)_

Encode a Python value for a specific PyTables column type.  Encodes `str` → `bytes` for `StringCol`; substitutes type-appropriate defaults for `None`.  Called internally by `to_row()`.

#### `verify_schema(table: tables.Table) -> List[str]` _(classmethod)_

Compare `_H5_TYPES` against an open table's column names.  Returns a list of mismatch descriptions; an empty list means the schemas are consistent.  Useful for guarding against schema drift.

```python
with H5Client('data.h5') as h5:
    t = h5.get_table('/steps')
    issues = StepTableObject.verify_schema(t)
    if issues:
        raise ValueError('\n'.join(issues))
```

---

## NodeObject

**Module:** `tiferet_h5.mappers.settings`

Extends Tiferet's `TransferObject` with two additional methods for mapping domain objects to and from HDF5 node attribute sets (`_v_attrs`).  Used when lightweight metadata — config values, version markers, scalar settings — is stored on a group or leaf node rather than as table rows.

### Default Role

`NodeObject` ships with a built-in `_ROLES` entry:

```python
_ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
    'to_h5.attrs': {'by_alias': True},
}
```

This ensures `to_attrs()` applies `serialization_alias` values as HDF5 attribute key names by default.  Subclasses may extend `_ROLES` to add `exclude` rules or additional roles while keeping the `'to_h5.attrs'` entry.

### Aliasing Contract

Declare `serialization_alias` (the HDF5 attribute key name) and `validation_alias` on fields whose Python names differ from the desired attribute keys:

```python
class FeatureGroupObject(NodeObject):
    name: str = Field(default='')
    description: str = Field(
        default='',
        serialization_alias='desc',
        validation_alias=AliasChoices('desc', 'description'),
    )
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }
```

`to_attrs()` defaults to the `'to_h5.attrs'` role, so `description` serializes as `'desc'` in HDF5 without any extra steps.  `from_attrs()` uses `model_validate()`, which resolves `validation_alias` back to the Python field name transparently.

### Methods

#### `to_attrs(role: str = 'to_h5.attrs', **overrides) -> Dict[str, Any]`

Serialize this object to a flat dict suitable for writing to `node._v_attrs`.  Delegates to `to_primitive(role=role)`.

```python
group_obj = FeatureGroupObject(name='Calculator', description='Arithmetic ops')
attrs = group_obj.to_attrs()
# {'name': 'Calculator', 'desc': 'Arithmetic ops'}

for k, v in attrs.items():
    h5.set_node_attr('/features/calc', k, v)
```

#### `from_attrs(attrs: Dict[str, Any], **overrides) -> NodeObject` _(classmethod)_

Construct a `NodeObject` from a node attribute dict.  Decodes bytes to `str` and converts NumPy scalars to Python natives before calling `model_validate`.  Pass the result of `H5Client.get_node_attrs()` directly.

```python
raw = h5.get_node_attrs('/features/calc')
group_obj = FeatureGroupObject.from_attrs(raw)
print(group_obj.description)  # 'Arithmetic ops'
```

---

## Nested Object Modeling

HDF5's group hierarchy maps naturally to nested domain concepts.  The canonical pattern in tiferet-h5 is:

```
/features/                        group  ← one attr per catalog-level scalar
    calc/                         group  ← FeatureGroupObject attrs (name, desc)
        steps                     table  ← FeatureStepObject rows (one row per step)
    utils/
        steps
```

**One `NodeObject` subclass per group level** holds the scalar metadata for that group as `_v_attrs`.  **One `TableObject` subclass** holds the collection of child records as table rows nested inside the group.

### Full Example

```python
import tables
from typing import ClassVar, Dict, Any, List
from pydantic import Field, AliasChoices
from tiferet_h5 import H5Client, TableObject, NodeObject

# ── Group mapper (scalar metadata → node attributes) ────────────────────────
class FeatureGroupObject(NodeObject):
    name: str = Field(default='')
    description: str = Field(
        default='',
        serialization_alias='desc',
        validation_alias=AliasChoices('desc', 'description'),
    )
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }

# ── Child table mapper (collection items → table rows) ───────────────────────
class FeatureStepObject(TableObject):
    name: str = Field(default='')
    service_id: str = Field(
        default='',
        serialization_alias='svc',
        validation_alias=AliasChoices('svc', 'service_id'),
    )
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name': tables.StringCol(256),
        'svc':  tables.StringCol(256),
    }

# ── Write ────────────────────────────────────────────────────────────────────
with H5Client('catalog.h5', mode='w') as h5:
    h5.create_group('/features/calc')

    group = FeatureGroupObject(name='Calculator', description='Arithmetic ops')
    for k, v in group.to_attrs().items():
        h5.set_node_attr('/features/calc', k, v)

    t = h5.create_table('/features/calc/steps', FeatureStepObject.get_description())
    FeatureStepObject(name='Add', service_id='add_event').to_row(t)
    t.flush()

# ── Read ─────────────────────────────────────────────────────────────────────
with H5Client('catalog.h5', mode='r') as h5:
    group = FeatureGroupObject.from_attrs(h5.get_node_attrs('/features/calc'))
    steps: List[FeatureStepObject] = [
        FeatureStepObject.from_row(r)
        for r in h5.read_rows('/features/calc/steps')
    ]
```

### Design Rules

- `NodeObject` subclass fields should only include scalar values (strings, numbers, booleans) — HDF5 attributes do not support nested structures.
- `TableObject` subclass fields should correspond 1-to-1 with HDF5 column types declared in `_H5_TYPES`.
- When a parent group holds both attributes and a child table, keep the `NodeObject` and `TableObject` as separate classes.  A concrete repository is responsible for orchestrating reads and writes to both.
- Use `H5Client.get_or_create_table()` in repository `save()` methods to avoid repeated `node_exists()` checks.

---

## Import Reference

```python
from tiferet_h5 import TableObject, NodeObject
# or
from tiferet_h5.mappers import TableObject, NodeObject
from tiferet_h5.mappers.settings import TableObject, NodeObject
```
