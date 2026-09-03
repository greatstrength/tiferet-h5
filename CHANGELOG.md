# Changelog

All notable changes to `tiferet-h5` are documented here. The format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/); the
version sequence follows this project's own alpha/beta pre-release roadmap
rather than plain SemVer feature/patch categories.

## [1.0.0b1] - 2026-09-03 - Release Candidate

### Added
- `TableObjectTestBase`/`NodeObjectTestBase` mapper test harness
  (`tiferet_h5/mappers/tests/settings.py`), mirroring core Tiferet's
  `AggregateTestBase`/`TransferObjectTestBase` pattern, so downstream
  packages can inherit standardized tests for `TableObject`/`NodeObject`
  subclasses with minimal configuration (closes #17).

### Changed
- **API freeze declared.** The public surface as of `1.0.0a8` (RFP-001
  through RFP-007) is locked; only bug fixes land between now and `1.0.0`.

## [1.0.0a8] - 2026-09-03 - RFP-007: Async Strategy Decision

### Decided
- **Sync-only stance (Option B).** `tiferet-h5` does not ship an async
  wrapper around core Tiferet's `AsyncFeatureContext`. A naive
  `asyncio.to_thread` wrapper would reintroduce the exact concurrent-access
  hazard the Concurrency guide documents as unsafe, and the package isn't
  yet confident enough in core's own async design to couple its API to it.
  Documented in `README.md` and `docs/guides/utils/h5.md`'s new Async Usage
  subsection.

## [1.0.0a7] - 2026-09-02 - RFP-006: Validation & Hardening

### Added
- `tiferet_h5/tests_int/` — cross-feature integration tests exercising
  schema integrity, streaming/indexing, storage efficiency, and the CRUD
  mixins together.
- `examples/catalog_app/` — a full worked example application mirroring
  core `tiferet`'s `examples/basic_calculator`.
- CI now runs against an explicit `tiferet-version: ["2.0.3"]` matrix entry.
- PyTables' single-writer concurrency constraints documented explicitly in
  `docs/guides/utils/h5.md` (no lock helper shipped this alpha).

### Fixed
- `H5Client.compact()` was silently dropping column indexes during its
  copy-and-rewrite (PyTables' `copy_children()` defaults `propindexes` to
  `False`); fixed by passing `propindexes=True` explicitly.

## [1.0.0a6] - 2026-09-02 - RFP-005: Developer Ergonomics

### Added
- `TableRepository`/`NodeRepository` CRUD mixins (`tiferet_h5/repos/core.py`),
  composed alongside `H5Repository` rather than subclassing it.
- Repository-level compression default (`TableRepository.filters`, applied
  automatically in `save()`) and automatic `schema_version` stamping at
  table-creation time via `TableObject.schema_fingerprint()`.
- First test coverage for the repos layer (`tiferet_h5/repos/tests/`).

### Known limitation
- Composing both mixins via multiple inheritance on one class collides on
  `save()`/`get()`/`exists()` under Python's MRO (one mixin's implementation
  silently shadows the other). Use two separate repository instances
  sharing one file instead — documented in `docs/guides/repos.md`.

## [1.0.0a5] - 2026-09-02 - RFP-004: Storage Efficiency

### Added
- Per-call compression (`filters`, a native `tables.Filters` instance) on
  `create_table`/`get_or_create_table`/`create_array`.
- `H5Client.compact()` for reclaiming disk space after row deletions, with
  an optional `filters` override to change compression on rewrite.

## [1.0.0a4] - 2026-09-02 - RFP-003: Scale & Query Performance

### Added
- Streaming reads (`iter_rows`/`iter_query`) and column indexing
  (`create_index`/`is_indexed`/`reindex`) on `H5Client`, plus the
  corresponding `H5Service` interface additions.

## [1.0.0a3] - 2026-09-01 - RFP-002: Schema Integrity

### Added
- `H5Client.assert_schema()` — opt-in schema mismatch enforcement, detecting
  drift in both directions (missing columns and type/extra-column drift).
- `TableObject.schema_fingerprint()` — content-fingerprint schema
  versioning, stamped as a node attribute on the table's own node.
- Documented copy-rewrite migration pattern (no migration helper shipped).

### Fixed
- Folded in backlog #18's missing regression test
  (`test_create_table_auto_creates_parents`) for the auto-parent-group
  creation fix that had already shipped functionally in `1.0.0a1`.

## [1.0.0a2] - 2026-09-01 - Dependency correction

### Changed
- `tiferet` dependency widened from the exact `==2.0.0b16` pin to
  `>=2.0.3,<2.1`, tracking core Tiferet's move out of its beta series.

## [1.0.0a1] - 2026-08-12 - RFP-001: Error-Handling & b16 Alignment

### Changed
- `H5Client` migrated fully off `TiferetError` onto `ServiceError`
  (`tiferet.interfaces`), with `cause` chaining preserving the original
  driver exception.
- Error code constants relocated from the deleted `assets/` module into
  `tiferet_h5/utils/h5.py`, hosted beside their raise sites.
- Broad `except Exception` catches narrowed to specific PyTables/stdlib
  exception types.

### Removed
- Dead `H5_SCHEMA_MISMATCH_ID` constant (no raiser at the time; real
  enforcement shipped later in `1.0.0a3`).

## [0.1.0] - 2026-05-07

### Added
- Initial implementation: `domain`, `interfaces`, `mappers`
  (`TableObject`/`NodeObject`), `utils` (`H5Client`), and `repos`
  (`H5Repository`) layers.
- CI/CD pipeline and PyPI release workflow.
