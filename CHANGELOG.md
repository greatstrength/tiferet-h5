# Changelog

All notable changes to `tiferet-h5` are documented here. The format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] - 2026-09-25

First stable release. Reconstructed from the `v1.0.0b2` prototype catalog
under freeze id `TH51-FREEZE-001`.

### Added
- `H5Client.ensure_parent_groups()` creates missing parent groups before
  `create_group`, `create_table`, `get_or_create_table`, and `create_array`
  (#55).
- `H5Repository.file_exists()` checks the filesystem without opening or
  creating the file (#44).
- Streaming reads: `read_rows` and `query` accept a `chunk_size` and return
  an iterator instead of materializing every row (#58).
- Column indexing: `create_index`, `is_indexed`, and `reindex` on `H5Service`
  and `H5Client` (#52).
- `H5Client.compact()` rewrites a file to reclaim space, preserving column
  indexes and optionally applying compression filters (#54).
- `TableRepository` mixin with `save`, `get`, `list`, `iter_list`, `delete`,
  `exists`, and opt-in `verify` (#47).
- `NodeRepository` mixin for attribute-oriented node storage (#45).
- `TableObject.schema_fingerprint()` — an order-independent digest of a
  table's declared schema (#41).
- `H5Client.assert_schema()` raises `H5_SCHEMA_MISMATCH` when a live table
  does not match its declared schema (#56).
- `TableRepository.stamp_schema_version()` records the schema version as a
  node attribute on first create (#46).
- `TableRepository.filters` forwards a default `tables.Filters` to
  `get_or_create_table` (#43).
- `MapperAssertions`, `TableObjectTestBase`, and `NodeObjectTestBase` test
  harness in `tiferet_h5/mappers/tests/core.py` (#39).
- `_NULLABLE_FIELDS` on `TableObject` and `NodeObject` so declared optional
  strings round-trip `None` through the HDF5 empty-string sentinel (#40).
- `examples/catalog_app/` — a worked example application (#38).
- `tiferet_h5/tests_int/` — cross-feature integration tests (#50).
- Domain tests locking numeric-to-string coercion for `H5Column.name` and
  `H5Node.node_type` (#51).

### Changed
- Error handling migrated from `TiferetError` / `RaiseError` to
  `ServiceError` raised via `ServiceError.raise_for`, with the original
  driver exception chained as `cause`. Error code constants moved out of
  `tiferet_h5/assets` to sit beside their raise sites in
  `tiferet_h5/utils/h5.py`, and the `assets` package was removed (#57).
- `TableObject` and `NodeObject` moved from `tiferet_h5/mappers/settings.py`
  to `tiferet_h5/mappers/core.py` (#42).
- `tiferet` dependency pinned to `>=2.1.0,<2.2`.

## [0.1.0] - 2026-09-03

Initial trunk release.
