"""
Catalog Client -- a runnable, end-to-end worked example for tiferet-h5.

Demonstrates the full domain -> mapper -> repo -> H5Client stack together:
the two-repository composition pattern from RFP-005 (a TableRepository and
a NodeRepository sharing one file, never multiply inherited into a single
class -- see docs/guides/repos.md), the repository-level compression
default from RFP-004, mapping a persisted row onto a mutable Aggregate, and
two direct H5Client calls -- assert_schema() (RFP-002, opt-in schema
enforcement) and compact() (RFP-004, reclaiming space after a delete) --
used alongside the mixins rather than only through them, so the example
teaches both abstraction levels.

Run from this directory with: python catalog_client.py
"""

from pathlib import Path

from app.mappers import CatalogItemTableObject, CatalogMetaNodeObject
from app.models import CatalogItemAggregate
from app.repos import CatalogItemsRepository, CatalogMetaRepository

CATALOG_PATH = Path(__file__).parent / 'catalog.h5'

# Fresh file for each run of the example.
if CATALOG_PATH.exists():
    CATALOG_PATH.unlink()

items_repo = CatalogItemsRepository(str(CATALOG_PATH))
meta_repo = CatalogMetaRepository(str(CATALOG_PATH))

# Save the catalog's own metadata via the NodeRepository half.
meta_repo.save(CatalogMetaNodeObject(catalog_name='Hardware Catalog', currency='USD'))
meta = meta_repo.get()
print(f'Catalog: {meta.catalog_name} ({meta.currency})')

# Save a few items via the TableRepository half -- filters= is applied
# automatically on table creation since CatalogItemsRepository declares a
# repository-level compression default.
items_repo.save(CatalogItemTableObject(sku='BOLT-001', name='Bolt', price=1.50))
items_repo.save(CatalogItemTableObject(sku='NUT-002', name='Nut', price=0.50))
items_repo.save(CatalogItemTableObject(sku='WSHR-003', name='Washer', price=0.25))

for item in items_repo.list():
    print(f'  {item.sku}  {item.name:<8}  ${item.price:.2f}')

# Mapper -> domain: read one item back and mutate it as an Aggregate.
bolt = items_repo.get('sku == b"BOLT-001"')
bolt_aggregate = bolt.map(CatalogItemAggregate)
bolt_aggregate.apply_discount(10)
print(f'Discounted {bolt_aggregate.sku}: ${bolt_aggregate.price:.2f}')

# H5Client, directly: opt-in schema verification (RFP-002). Never called
# automatically by save()/get()/list() -- this is the mixin's verify(),
# which itself delegates to H5Client.assert_schema().
items_repo.verify()
print('Schema verified: OK')

# Remove an item, then reclaim the freed space directly via H5Client.
# compact() is not wrapped by the repository mixins -- it operates at the
# whole-file level, so it is reached via the lower-level client directly.
removed = items_repo.delete('sku == b"WSHR-003"')
with items_repo.client() as h5:
    h5.compact()
print(f'Removed {removed} item(s) and compacted the file.')

print('Remaining items:')
for item in items_repo.list():
    print(f'  {item.sku}  {item.name:<8}  ${item.price:.2f}')
