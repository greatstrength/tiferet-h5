# tiferet-h5

HDF5 infrastructure extension for the [Tiferet](https://github.com/greatstrength/tiferet) framework via PyTables.

`tiferet-h5` mirrors the layered architecture of the Tiferet core — `domain`, `interfaces`, `mappers`, `utils`, `repos` — adapted to the hierarchical, columnar, and typed nature of HDF5 files.  It introduces two mapper base classes that are the HDF5-native analogue of Tiferet's `TransferObject`: `TableObject` for row-oriented table storage and `NodeObject` for attribute-oriented node storage.

## Requirements

- Python ≥ 3.10
- `tiferet >= 2.0.3, < 2.1`
- `tables >= 3.10.0` (PyTables)

## Installation

```bash
pip install tiferet-h5
```

Or in development mode from the repository root:

```bash
pip install -e .
```

## Quick Start

This tutorial stores a simple feature catalog — groups with scalar metadata and child step tables — to demonstrate the full stack: domain objects, mapper classes, `H5Client`, and `H5Repository`.

### 1. Define Your Mappers

```python
import tables
from typing import ClassVar, Dict, Any, List
from pydantic import Field, AliasChoices
from tiferet_h5 import TableObject, NodeObject

# ── Group-level metadata → node attributes ────────────────────────────────
# One instance per feature group, stored on the HDF5 group node.
class FeatureGroupObject(NodeObject):
    name: str = Field(default='', description='Feature name.')
    description: str = Field(
        default='',
        serialization_alias='desc',
        validation_alias=AliasChoices('desc', 'description'),
        description='Stored as "desc" in HDF5 to keep attribute keys short.',
    )
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }

# ── Child collection → table rows ─────────────────────────────────────────
# One row per step, stored in a table nested inside the feature group.
class FeatureStepObject(TableObject):
    name: str = Field(default='', description='Step name.')
    service_id: str = Field(
        default='',
        serialization_alias='svc',
        validation_alias=AliasChoices('svc', 'service_id'),
        description='Service ID; stored as "svc" column in HDF5.',
    )
    pass_on_error: bool = Field(
        default=False,
        serialization_alias='pass_err',
        validation_alias=AliasChoices('pass_err', 'pass_on_error'),
    )
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name':     tables.StringCol(256),
        'svc':      tables.StringCol(256),
        'pass_err': tables.BoolCol(),
    }
```

### 2. Write to HDF5

```python
from tiferet_h5 import H5Client

# HDF5 layout:
#   /features/                ← group, attr: schema_ver
#       calc/                 ← group, attrs: name, desc
#           steps             ← table, cols: name, svc, pass_err

with H5Client('catalog.h5', mode='w') as h5:
    # Catalog root
    h5.create_group('/features')
    h5.set_node_attr('/features', 'schema_ver', '1.0')

    # Feature group
    h5.create_group('/features/calc')
    group = FeatureGroupObject(
        name='Calculator Features',
        description='Basic arithmetic operations',
    )
    for k, v in group.to_attrs().items():
        h5.set_node_attr('/features/calc', k, v)

    # Child steps table
    t = h5.create_table(
        '/features/calc/steps',
        FeatureStepObject.get_description(),
        title='Feature Steps',
    )
    FeatureStepObject(name='Add numbers', service_id='add_event').to_row(t)
    FeatureStepObject(name='Validate',    service_id='validate_event', pass_on_error=True).to_row(t)
    t.flush()
```

### 3. Read Back

```python
with H5Client('catalog.h5', mode='r') as h5:
    schema_ver = h5.get_node_attr('/features', 'schema_ver')
    print('Schema version:', schema_ver)

    group = FeatureGroupObject.from_attrs(h5.get_node_attrs('/features/calc'))
    print('Feature:', group.name, '—', group.description)

    steps: List[FeatureStepObject] = [
        FeatureStepObject.from_row(r)
        for r in h5.read_rows('/features/calc/steps')
    ]
    for s in steps:
        print(f'  step  {s.name!r}  service_id={s.service_id!r}  pass_on_error={s.pass_on_error}')
```

Output:
```
Schema version: 1.0
Feature: Calculator Features — Basic arithmetic operations
  step  'Add numbers'  service_id='add_event'  pass_on_error=False
  step  'Validate'     service_id='validate_event'  pass_on_error=True
```

### 4. Use a Repository

`TableRepository` and `NodeRepository` (`tiferet_h5.repos.core`) remove the hand-rolled `get_or_create_table()`/`to_attrs()` orchestration a repository would otherwise write itself -- compose one of each with `H5Repository` for the group's own metadata and its child table respectively:

```python
from tiferet_h5 import H5Repository, NodeRepository, TableRepository

class FeatureMetaRepository(NodeRepository, H5Repository):
    node_cls = FeatureGroupObject
    node_path = '/features/{key}'

class FeatureStepsRepository(TableRepository, H5Repository):
    table_cls = FeatureStepObject
    table_path = '/features/{key}/steps'

meta_repo  = FeatureMetaRepository('catalog.h5')
steps_repo = FeatureStepsRepository('catalog.h5')

# Write
meta_repo.save(FeatureGroupObject(name='Calculator', description='Arithmetic ops'), key='calc')
steps_repo.save(FeatureStepObject(name='Add numbers', service_id='add_event'), key='calc')

# Read
group = meta_repo.get(key='calc')
steps = steps_repo.list(key='calc')
```

`table_path`/`node_path` are `str.format()` templates -- any `**kwargs` passed to a method (here, `key='calc'`) interpolate into the path, so one repository instance serves every feature group in the file. See [docs/guides/repos.md](docs/guides/repos.md) for the full method reference, the repository-level compression default, and why `TableRepository`/`NodeRepository` should never be multiply inherited into a single class.

See [examples/catalog_app](examples/catalog_app) for a complete, runnable application built on this pattern, including opt-in schema verification and file compaction alongside the repository mixins.

## Package Layout

```
tiferet_h5/
├── __init__.py          Public exports and aliases
├── domain/
│   └── h5.py            H5Column, H5TableSchema, H5Node
├── interfaces/
│   └── h5.py            H5Service abstract interface
├── mappers/
│   └── settings.py      TableObject, NodeObject base classes
├── utils/
│   └── h5.py            H5Client (alias: H5); also hosts H5 error code string constants
└── repos/
    ├── core.py          TableRepository, NodeRepository CRUD mixins
    └── h5.py            H5Repository base
```

## Documentation

- [Domain Objects](docs/guides/domain.md) — `H5Column`, `H5TableSchema`, `H5Node`
- [Mappers](docs/guides/mappers.md) — `TableObject`, `NodeObject`, aliasing, nested modeling
- [H5Client](docs/guides/utils/h5.md) — full method reference, error codes, and concurrency guidance
- [Repos](docs/guides/repos.md) — `H5Repository`, `TableRepository`, `NodeRepository` CRUD mixins
- [examples/catalog_app](examples/catalog_app) — a complete, runnable application exercising the full stack end-to-end

## License

MIT
