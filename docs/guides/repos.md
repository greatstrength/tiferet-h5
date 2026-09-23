# tiferet-h5 Repos

**Package:** `tiferet_h5.repos`

## Overview

The repos layer persists `TableObject`/`NodeObject` pairs to HDF5 files. `H5Repository` is the generic base every concrete repository extends for file/mode management. `TableRepository` and `NodeRepository` (`tiferet_h5.repos.core`) are reusable CRUD mixins that remove the hand-rolled `get_or_create_table()` -> `to_row()`/`from_row()` -> `flush()` dance (and the analogous `to_attrs()`/`from_attrs()` dance for nodes) that every concrete repository used to write from scratch.

Mixin reads against a file that does not exist yet return their normal empty result without creating that file. Raw `H5Client` read modes stay strict: `'r'` / `'r+'` on a missing path still raise `H5_FILE_NOT_FOUND`.

---

## H5Repository

**Module:** `tiferet_h5.repos.h5`

Generic base providing `__init__(h5_file, mode='a')`, `file_exists() -> bool`, and `client(mode=None) -> H5Client`. Concrete repositories extend it (directly, or via `TableRepository`/`NodeRepository`) and use `client()` as a per-operation context manager.

`file_exists()` returns whether the configured `h5_file` path exists on disk. It does not open the file and does not create it. Downstream repositories that are not mixin-based should call it before opening a client in `'r'` or `'r+'`:

```python
repo = WidgetRepository('widgets.h5')

if repo.file_exists():
    with repo.client(mode='r') as h5:
        ...
```

`client(mode='r')` and a raw `H5Client` opened in `'r'` or `'r+'` against a missing path still raise `H5_FILE_NOT_FOUND`. That strictness is intentional. A missing file is a normal empty repository read; it is still an error for a raw client that expected the file to exist. Do not read in append mode to survive a missing file -- append mode creates the file. Write paths (`save`, and table `delete` / `verify`) still open the client and may create the file.

---

## TableRepository

**Module:** `tiferet_h5.repos.core`

A mixin for a declared `TableObject` class bound to a fixed (or templated) HDF5 table path.

### Declarations

```python
class WidgetRepository(TableRepository, H5Repository):
    table_cls = WidgetTableObject
    table_path = '/widgets/{catalog}'          # str.format() template
    filters = tables.Filters(complib='zlib', complevel=5)  # optional
    stamp_schema_version = True                 # default
```

- `table_cls` -- the `TableObject` subclass this repository persists.
- `table_path` -- a fixed path, or a `str.format()` template. Methods accept `**path_kwargs` forwarded to `resolve_table_path()`; a fixed path needs no kwargs at all.
- `filters` -- an optional `tables.Filters` instance applied automatically on table creation. This is the repository-level compression default RFP-004 (Storage Efficiency) deliberately left for this layer to add, rather than requiring every `save()` call site to pass `filters=` itself.
- `stamp_schema_version` -- when `True` (the default), `save()` stamps a `schema_version` node attribute (`table_cls.schema_fingerprint()`) the first time the table is created. This makes `H5Client.assert_schema(check_version=True)` meaningful for any table created through this mixin without extra caller effort.

### Methods

- `save(obj, **path_kwargs)` -- creates the table on first write (applying `filters` and stamping `schema_version`), then appends `obj` as a row.
- `get(condition, **path_kwargs) -> Optional[TableObject]` -- first row matching `condition`, or `None` if no row matches or the table or backing file has not been created yet.
- `list(condition=None, **path_kwargs) -> List[TableObject]` -- every matching row (or every row), or `[]` if the table or backing file does not exist yet.
- `iter_list(condition=None, **path_kwargs) -> Iterator[TableObject]` -- lazy counterpart to `list()`, wrapping `H5Client.iter_rows()`. Path/table validation is deferred to first iteration (unlike `H5Client.iter_rows()`'s eager validation), since this method must keep the file open across the caller's full iteration. Use `list()` when failures need to surface immediately. Yields nothing, without creating the file, when the backing file is absent.
- `delete(condition, **path_kwargs) -> int` -- removes matching rows, returns the count removed. Not part of the missing-file read short-circuit; it still opens the client.
- `exists(condition, **path_kwargs) -> bool` -- whether any row matches; `False` if the table or backing file does not exist yet.
- `verify(**path_kwargs)` -- explicitly asserts the live table matches `table_cls`'s declared schema (via `H5Client.assert_schema()`), raising a structured `ServiceError` on drift. **Never called automatically** by `save()`/`get()`/`list()` -- schema enforcement is opt-in, matching `H5Client.assert_schema()`'s own design.

`get()` / `list()` / `iter_list()` / `exists()` call `file_exists()` before opening a client. When the backing file is absent they return `None` / `[]` / no rows / `False` and do not create the file. When the file already exists they keep the repository's current `client()` mode. "Nothing here yet" is a normal empty read for these methods. It is still an error for a raw `H5Client` opened in `'r'` or `'r+'`.

---

## NodeRepository

**Module:** `tiferet_h5.repos.core`

A mixin for a declared `NodeObject` class bound to a fixed (or templated) HDF5 node path.

```python
class WidgetMetaRepository(NodeRepository, H5Repository):
    node_cls = WidgetMetaNodeObject
    node_path = '/widgets_meta'
```

### Methods

- `save(obj, **path_kwargs)` -- creates the group node on first write if absent, then sets each `to_attrs()` entry via `set_node_attr()`. Still creates the file when it does not exist.
- `get(**path_kwargs) -> Optional[NodeObject]` -- the node's attrs as a `NodeObject`, or `None` if the node or the backing file does not exist yet. A missing file returns `None` without creating the file.
- `exists(**path_kwargs) -> bool` -- whether the node currently exists. A missing file returns `False` without creating the file.

`get()` / `exists()` short-circuit on `file_exists()` the same way `TableRepository` reads do.

**No `delete()`.** `H5Service` has no generic node-removal primitive -- only `remove_rows()`, which is table-row-specific -- and adding one is out of scope for this mixin layer. This is a documented gap, not an oversight; a `delete()` is a natural candidate for a future RFP once a node-removal primitive exists on `H5Client`.

---

## Combining Both Mixins

**Do not** multiply inherit both `TableRepository` and `NodeRepository` into one class. Both declare `save()`/`get()`/`exists()`, and Python's MRO would silently resolve those names to whichever mixin is listed first -- shadowing the other's implementation entirely rather than raising an error.

When one domain concept needs both a table and a node persisted (e.g. a catalog's own metadata plus its child items), instantiate one repository of each kind against the same `h5_file`:

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

See the README's worked example, and [examples/catalog_app](../../examples/catalog_app) for a complete, runnable application built on this exact pattern.

---

## Import Reference

```python
from tiferet_h5 import H5Repository, TableRepository, NodeRepository
# or
from tiferet_h5.repos import H5Repository, TableRepository, NodeRepository
from tiferet_h5.repos.core import TableRepository, NodeRepository
```
