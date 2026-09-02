# Catalog App Example

A small, runnable application built with `tiferet-h5`, demonstrating the full domain -> interface -> mapper -> repo -> event stack working together end-to-end -- mirroring the layered shape of core `tiferet`'s `examples/basic_calculator`.

## Prerequisites

- Python 3.10+
- `tiferet-h5` (`pip install -e ../..` from this directory, or `pip install tiferet-h5`)

## Project Structure

```
catalog_app/
├── catalog_client.py        # Runnable entry point
└── app/
    ├── domain/catalog.py     # CatalogItem, CatalogMeta -- read-only domain objects
    ├── interfaces/catalog.py # CatalogItemService, CatalogMetaService -- Service ABCs
    ├── mappers/catalog.py    # CatalogItemTableObject, CatalogMetaNodeObject, CatalogItemAggregate
    ├── repos/catalog.py      # CatalogItemsRepository, CatalogMetaRepository
    └── events/catalog.py     # AddCatalogItem, ListCatalogItems, ApplyItemDiscount, RemoveCatalogItem,
                               # SaveCatalogMeta, GetCatalogMeta, VerifyAndCompactCatalog
```

## Layers

- **Domain** (`app/domain/`): `CatalogItem` and `CatalogMeta` hold only field declarations -- no persistence or serialization concerns.
- **Interfaces** (`app/interfaces/`): `CatalogItemService`/`CatalogMetaService` are abstract `Service` contracts. Events depend on these interfaces, not on the concrete repository classes.
- **Mappers** (`app/mappers/`): `CatalogItemTableObject`/`CatalogMetaNodeObject` (row/attribute-oriented HDF5 mappers) and `CatalogItemAggregate` (the mutable counterpart to `CatalogItem`) all inherit their fields from the domain layer rather than redeclaring them -- mirroring core tiferet's `FormulaConfigObject(Formula, TransferObject)` / `FormulaAggregate(Formula, Aggregate)`.
- **Repos** (`app/repos/`): `CatalogItemsRepository` (`TableRepository` + `H5Repository`) and `CatalogMetaRepository` (`NodeRepository` + `H5Repository`) implement the service interfaces above. See the note in `app/repos/catalog.py` on why the mixin is listed *before* the service interface in each class's bases -- the reverse order would leave the interface's abstract stubs shadowing the mixin's real implementation.
- **Events** (`app/events/`): each event is constructor-injected with a service interface and enforces at least one real domain rule via `self.verify(...)` (duplicate SKUs, price/discount/currency bounds, not-found checks) -- not just pass-through field storage.

## What It Demonstrates

- **A full layered architecture**, not just persistence: domain objects, an explicit service-interface layer, and domain events that enforce real business rules on top of those interfaces.
- **Two-repository composition** (RFP-005): `CatalogItemsRepository` and `CatalogMetaRepository` are two separate repository instances sharing one HDF5 file -- **not** a single class multiply-inheriting both mixins, which would silently collide on `save()`/`get()`/`exists()` under Python's MRO. See [docs/guides/repos.md](../../docs/guides/repos.md) for why.
- **Repository-level compression default** (RFP-004/RFP-005): `CatalogItemsRepository.filters` is set once; every item written through it is compressed automatically.
- **Events invoked via `DomainEvent.handle(...)`**: `catalog_client.py` and the test suite drive every operation through `DomainEvent.handle(EventClass, dependencies={...}, **kwargs)` -- the same invocation surface core tiferet documents for exercising events outside of a full config-driven app -- rather than calling repository methods directly.
- **The append-only-row pattern**: `ApplyItemDiscount` maps a persisted row onto a mutable `CatalogItemAggregate`, mutates it, then deletes the stale row and saves a fresh one, since HDF5 table rows have no in-place update.
- **Direct `H5Client` primitives used alongside the events layer** (not instead of it): `VerifyAndCompactCatalog` wraps opt-in schema verification (RFP-002) and a raw `h5.compact()` call (RFP-004) behind an event boundary, so even these lower-level, whole-file operations are reached through `DomainEvent.handle(...)`.

## Running It

```bash
cd examples/catalog_app
python catalog_client.py
```

### Output

```
Catalog: Hardware Catalog (USD)
  BOLT-001  Bolt      $1.50
  NUT-002  Nut       $0.50
  WSHR-003  Washer    $0.25
Error: BOLT-001 rejected as a duplicate sku
Discounted BOLT-001: $1.35
Removed 1 item(s), verified the schema, and compacted the file.
Remaining items:
  NUT-002  Nut       $0.50
  BOLT-001  Bolt      $1.35
```

Running the script creates (and overwrites) `catalog.h5` in this directory. Note that BOLT-001 moves to the end of the listing after the discount -- `ApplyItemDiscount` deletes and re-saves its row, so it becomes the most recently appended row in the table.

## Tests

```bash
cd examples/catalog_app
python -m pytest tests/
```
