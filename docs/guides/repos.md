# tiferet-h5 Repos

**Package:** `tiferet_h5.repos`

## Overview

`H5Repository` owns the file path and a short-lived `H5Client`. `TableRepository` and `NodeRepository` are mixins composed beside it. Each mixin owns one storage primitive: table rows, or node attributes.

---

<a id="noderepository"></a>

## NodeRepository

**Module:** `tiferet_h5.repos.core`

Attribute-backed repositories repeat the same group create and attribute read. `NodeRepository` is that shared sequence. It has no `__init__`. Compose it as `class MyRepo(NodeRepository, H5Repository)` and declare `node_cls` and `node_path` on the subclass.

`node_path` is a fixed path or a `str.format()` template. `resolve_node_path()` formats it only when keyword arguments are given.

- `save(obj, **path_kwargs)` creates the group with `create_group` when the node is missing, then sets each `to_attrs()` item with `set_node_attr`. A missing file is created. A later save updates the existing group.
- `get(**path_kwargs)` returns `node_cls.from_attrs(get_node_attrs(path))`, or `None` when the file or node is missing. A missing file does not open a client and does not create the file.
- `exists(**path_kwargs)` returns `node_exists`, or `False` when the file is missing. A missing file does not open a client.

There is no `delete`. `H5Service` has no generic node-removal method, and this mixin does not add one.

Nullable string fields declared on `node_cls` still round-trip through `to_attrs` / `from_attrs`. The repository does not add a second sentinel.

---

<a id="do-not-compose-both-mixins"></a>

## Do not compose both mixins

Do not compose `TableRepository` and `NodeRepository` on one class. `save`, `get`, and `exists` collide under the MRO. Use two repository instances on one file.

```python
class CatalogItemsRepository(TableRepository, H5Repository):
    table_cls = ItemTableObject
    table_path = '/catalog/items'

class CatalogMetaRepository(NodeRepository, H5Repository):
    node_cls = CatalogMetaNodeObject
    node_path = '/catalog'

items_repo = CatalogItemsRepository('catalog.h5')
meta_repo = CatalogMetaRepository('catalog.h5')
```

Whichever mixin is listed first would silently own the shared method names. Two instances keep table rows and node attributes addressable on the same HDF5 file.

---

## Import Reference

```python
from tiferet_h5 import H5Repository, NodeRepository, TableRepository
# or
from tiferet_h5.repos import H5Repository, NodeRepository, TableRepository
```
