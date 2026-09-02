"""Catalog App Tests Settings"""

# *** imports

# ** core
from pathlib import Path

# ** infra
import pytest

# ** app
from app.mappers import CatalogItemTableObject, CatalogMetaNodeObject
from app.models import CatalogItemAggregate
from app.repos import CatalogItemsRepository, CatalogMetaRepository

# *** fixtures

# ** fixture: catalog_path
@pytest.fixture
def catalog_path(tmp_path: Path) -> str:
    '''
    Return a path (as str) to a not-yet-existing HDF5 file for the example's tests.
    '''
    return str(tmp_path / 'catalog.h5')


# *** tests

# ** test: two_repository_composition_persists_meta_and_items
def test_two_repository_composition_persists_meta_and_items(catalog_path: str) -> None:
    '''
    Test that the two-repository composition pattern (CatalogItemsRepository +
    CatalogMetaRepository sharing one file) persists and reads back correctly.
    '''
    items_repo = CatalogItemsRepository(catalog_path)
    meta_repo = CatalogMetaRepository(catalog_path)

    meta_repo.save(CatalogMetaNodeObject(catalog_name='Hardware Catalog', currency='USD'))
    items_repo.save(CatalogItemTableObject(sku='BOLT-001', name='Bolt', price=1.50))

    meta = meta_repo.get()
    items = items_repo.list()

    assert meta.catalog_name == 'Hardware Catalog'
    assert len(items) == 1
    assert items[0].sku == 'BOLT-001'


# ** test: repository_level_filters_apply_compression
def test_repository_level_filters_apply_compression(catalog_path: str) -> None:
    '''
    Test that CatalogItemsRepository's repository-level `filters` default is
    applied automatically to the created table.
    '''
    items_repo = CatalogItemsRepository(catalog_path)
    items_repo.save(CatalogItemTableObject(sku='BOLT-001', name='Bolt', price=1.50))

    with items_repo.client(mode='r') as h5:
        table = h5.get_table('/catalog/items')
        assert table.filters.complib == 'zlib'
        assert table.filters.complevel == 5


# ** test: mapper_to_aggregate_mutation_is_independent_of_persisted_row
def test_mapper_to_aggregate_mutation_is_independent_of_persisted_row(catalog_path: str) -> None:
    '''
    Test that mapping a persisted row onto a mutable Aggregate and mutating it
    (apply_discount()) does not affect the persisted row until saved again.
    '''
    items_repo = CatalogItemsRepository(catalog_path)
    items_repo.save(CatalogItemTableObject(sku='BOLT-001', name='Bolt', price=1.50))

    bolt = items_repo.get('sku == b"BOLT-001"')
    aggregate = bolt.map(CatalogItemAggregate)
    aggregate.apply_discount(10)

    assert abs(aggregate.price - 1.35) < 1e-9
    assert abs(items_repo.get('sku == b"BOLT-001"').price - 1.50) < 1e-9


# ** test: verify_and_compact_after_delete
def test_verify_and_compact_after_delete(catalog_path: str) -> None:
    '''
    Test the example's direct H5Client usage alongside the mixins: opt-in
    schema verification via verify(), and compact() via a raw client
    obtained from the repository, after a deletion.
    '''
    items_repo = CatalogItemsRepository(catalog_path)
    items_repo.save(CatalogItemTableObject(sku='BOLT-001', name='Bolt', price=1.50))
    items_repo.save(CatalogItemTableObject(sku='WSHR-003', name='Washer', price=0.25))

    items_repo.verify()  # must not raise

    removed = items_repo.delete('sku == b"WSHR-003"')
    with items_repo.client() as h5:
        h5.compact()

    assert removed == 1
    assert [obj.sku for obj in items_repo.list()] == ['BOLT-001']
