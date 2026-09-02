"""
Catalog Client -- a runnable, end-to-end worked example for tiferet-h5.

Demonstrates the full domain -> interface -> mapper -> repo -> event stack
wired through tiferet's own config-driven application engine, mirroring
core tiferet's calc_client.py: config.yml declares the catalog_client
session, the two repository services (RFP-005's two-repository composition
sharing one file, plus RFP-004's repository-level compression default), the
seven catalog.* event services, the catalog.* feature workflows, and the
error catalog those events raise into. tiferet.blueprints.app.build_app
resolves all of it into a single AppSessionContext; every operation below
is then just app.run(feature_id, data={...}) -- no direct repository or
event construction here at all.

Run from this directory with: python catalog_client.py
"""

from pathlib import Path

from tiferet import TiferetError
from tiferet.blueprints.app import build_app

CATALOG_PATH = Path(__file__).parent / 'catalog.h5'

# Fresh file for each run of the example.
if CATALOG_PATH.exists():
    CATALOG_PATH.unlink()

app = build_app('catalog_client')

# Save the catalog's own metadata, then read it back.
app.run('catalog.save_meta', data={'catalog_name': 'Hardware Catalog', 'currency': 'USD'})
meta = app.run('catalog.get_meta', data={})
print(f'Catalog: {meta.catalog_name} ({meta.currency})')

# Save a few items -- filters= is applied automatically on table creation
# since CatalogItemsRepository declares a repository-level compression
# default, and catalog.add_item itself rejects a duplicate sku or a
# negative price before ever reaching the repository.
for sku, name, price in [
    ('BOLT-001', 'Bolt', 1.50),
    ('NUT-002', 'Nut', 0.50),
    ('WSHR-003', 'Washer', 0.25),
]:
    app.run('catalog.add_item', data={'sku': sku, 'name': name, 'price': price})

for item in app.run('catalog.list_items', data={}):
    print(f'  {item.sku}  {item.name:<8}  ${item.price:.2f}')

# Demonstrate a rejected domain rule: adding a duplicate sku raises a
# TiferetAPIError, formatted from the error catalog declared in config.yml.
try:
    app.run('catalog.add_item', data={'sku': 'BOLT-001', 'name': 'Bolt (dup)', 'price': 1.50})
except TiferetError as e:
    print(f'Error: {e.message}')

# catalog.apply_discount: verifies the item exists and the percent is in
# bounds, maps the row to a mutable CatalogItemAggregate, applies the
# discount, then replaces the stale row -- HDF5 table rows have no
# in-place update.
discounted = app.run('catalog.apply_discount', data={'sku': 'BOLT-001', 'percent': 10})
print(f'Discounted {discounted.sku}: ${discounted.price:.2f}')

# catalog.remove_item, then catalog.verify_and_compact -- the latter wraps
# two direct H5Client primitives (verify()/RFP-002 and compact()/RFP-004)
# behind an event boundary, so even these lower-level operations are
# reached the same way as every other feature: through app.run(...).
removed = app.run('catalog.remove_item', data={'sku': 'WSHR-003'})
app.run('catalog.verify_and_compact', data={})
print(f'Removed {removed} item(s), verified the schema, and compacted the file.')

print('Remaining items:')
for item in app.run('catalog.list_items', data={}):
    print(f'  {item.sku}  {item.name:<8}  ${item.price:.2f}')
