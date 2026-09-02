"""
Catalog Client -- a runnable, end-to-end worked example for tiferet-h5.

Demonstrates the full domain -> interface -> mapper -> repo -> event stack
together: the two-repository composition pattern from RFP-005 (a
TableRepository and a NodeRepository sharing one file, never multiply
inherited into a single class -- see docs/guides/repos.md), the
repository-level compression default from RFP-004, and a domain events
layer (app/events/catalog.py) that enforces real business rules (duplicate
SKUs, price/discount/currency bounds) on top of the service interfaces
(app/interfaces/catalog.py) -- rather than the client script calling
repository methods directly. Every operation below is driven through
DomainEvent.handle(EventClass, dependencies={...}, **kwargs), the same
invocation surface core tiferet documents for exercising events outside of
a full config-driven app.

Run from this directory with: python catalog_client.py
"""

from pathlib import Path

from tiferet import TiferetError
from tiferet.events import DomainEvent

from app.events.catalog import (
    AddCatalogItem,
    ApplyItemDiscount,
    GetCatalogMeta,
    ListCatalogItems,
    RemoveCatalogItem,
    SaveCatalogMeta,
    VerifyAndCompactCatalog,
)
from app.repos.catalog import CatalogItemsRepository, CatalogMetaRepository

CATALOG_PATH = Path(__file__).parent / 'catalog.h5'

# Fresh file for each run of the example.
if CATALOG_PATH.exists():
    CATALOG_PATH.unlink()

items_repo = CatalogItemsRepository(str(CATALOG_PATH))
meta_repo = CatalogMetaRepository(str(CATALOG_PATH))

# Save the catalog's own metadata via SaveCatalogMeta, then read it back via
# GetCatalogMeta -- both events depend on CatalogMetaService, not the
# concrete repository, and CatalogMetaService is happy to have that
# dependency satisfied by CatalogMetaRepository.
DomainEvent.handle(
    SaveCatalogMeta,
    dependencies={'catalog_meta_service': meta_repo},
    catalog_name='Hardware Catalog',
    currency='USD',
)
meta = DomainEvent.handle(GetCatalogMeta, dependencies={'catalog_meta_service': meta_repo})
print(f'Catalog: {meta.catalog_name} ({meta.currency})')

# Save a few items via AddCatalogItem -- filters= is applied automatically
# on table creation since CatalogItemsRepository declares a repository-level
# compression default, and AddCatalogItem itself rejects a duplicate sku or
# a negative price before ever reaching the repository.
for sku, name, price in [
    ('BOLT-001', 'Bolt', 1.50),
    ('NUT-002', 'Nut', 0.50),
    ('WSHR-003', 'Washer', 0.25),
]:
    DomainEvent.handle(AddCatalogItem, dependencies={'catalog_item_service': items_repo}, sku=sku, name=name, price=price)

for item in DomainEvent.handle(ListCatalogItems, dependencies={'catalog_item_service': items_repo}):
    print(f'  {item.sku}  {item.name:<8}  ${item.price:.2f}')

# Demonstrate a rejected domain rule: adding a duplicate sku raises.
try:
    DomainEvent.handle(AddCatalogItem, dependencies={'catalog_item_service': items_repo}, sku='BOLT-001', name='Bolt (dup)', price=1.50)
except TiferetError as e:
    print(f'Error: {e.kwargs.get("sku")} rejected as a duplicate sku')

# ApplyItemDiscount: verifies the item exists and the percent is in bounds,
# maps the row to a mutable CatalogItemAggregate, applies the discount, then
# replaces the stale row -- HDF5 table rows have no in-place update.
discounted = DomainEvent.handle(ApplyItemDiscount, dependencies={'catalog_item_service': items_repo}, sku='BOLT-001', percent=10)
print(f'Discounted {discounted.sku}: ${discounted.price:.2f}')

# RemoveCatalogItem, then VerifyAndCompactCatalog -- the latter wraps two
# direct H5Client primitives (verify()/RFP-002 and compact()/RFP-004) behind
# an event boundary, so even these lower-level operations flow through the
# events layer rather than the client script reaching into the repo itself.
removed = DomainEvent.handle(RemoveCatalogItem, dependencies={'catalog_item_service': items_repo}, sku='WSHR-003')
DomainEvent.handle(VerifyAndCompactCatalog, dependencies={'catalog_item_service': items_repo})
print(f'Removed {removed} item(s), verified the schema, and compacted the file.')

print('Remaining items:')
for item in DomainEvent.handle(ListCatalogItems, dependencies={'catalog_item_service': items_repo}):
    print(f'  {item.sku}  {item.name:<8}  ${item.price:.2f}')
