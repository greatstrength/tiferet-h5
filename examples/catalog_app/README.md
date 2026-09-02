# Catalog App Example

A small, runnable application built with `tiferet-h5`, demonstrating the full domain -> mapper -> repo -> `H5Client` stack working together end-to-end -- mirroring the shape of core `tiferet`'s `examples/basic_calculator`.

## Prerequisites

- Python 3.10+
- `tiferet-h5` (`pip install -e ../..` from this directory, or `pip install tiferet-h5`)

## Project Structure

```
catalog_app/
├── catalog_client.py       # Runnable entry point
└── app/
    ├── models.py            # CatalogItem (domain), CatalogItemAggregate (mutable)
    ├── mappers.py            # CatalogItemTableObject, CatalogMetaNodeObject
    └── repos.py              # CatalogItemsRepository, CatalogMetaRepository
```

## What It Demonstrates

- **Two-repository composition** (RFP-005): `CatalogItemsRepository` (`TableRepository` + `H5Repository`) and `CatalogMetaRepository` (`NodeRepository` + `H5Repository`) are two separate repository instances sharing one HDF5 file -- **not** a single class multiply-inheriting both mixins, which would silently collide on `save()`/`get()`/`exists()` under Python's MRO. See [docs/guides/repos.md](../../docs/guides/repos.md) for why.
- **Repository-level compression default** (RFP-004/RFP-005): `CatalogItemsRepository.filters` is set once; every item written through it is compressed automatically, with no `save()` call site needing to pass `filters=` itself.
- **Domain -> mapper -> aggregate round trip**: a `CatalogItemTableObject` row is mapped onto a mutable `CatalogItemAggregate` via `.map()`, mutated (`apply_discount()`), independent of the persisted row.
- **Direct `H5Client` primitives used alongside the mixins** (not instead of them): `items_repo.verify()` (opt-in schema enforcement, RFP-002) and a raw `h5.compact()` call via `items_repo.client()` (RFP-004) after a deletion -- so the example teaches both the high-level repository layer and the lower-level client primitives it sits on.

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
Discounted BOLT-001: $1.35
Schema verified: OK
Removed 1 item(s) and compacted the file.
Remaining items:
  BOLT-001  Bolt      $1.50
  NUT-002  Nut       $0.50
```

Running the script creates (and overwrites) `catalog.h5` in this directory.

## Tests

```bash
cd examples/catalog_app
python -m pytest tests/
```
