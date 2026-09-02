"""Catalog App Tests Settings"""

# *** imports

# ** core
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet import TiferetError
from tiferet.blueprints.app import build_app
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

# *** fixtures

# ** fixture: catalog_path
@pytest.fixture
def catalog_path(tmp_path: Path) -> str:
    '''
    Return a path (as str) to a not-yet-existing HDF5 file for the example's tests.
    '''
    return str(tmp_path / 'catalog.h5')


# ** fixture: items_repo
@pytest.fixture
def items_repo(catalog_path: str) -> CatalogItemsRepository:
    '''
    Return a CatalogItemsRepository bound to the test's HDF5 file.
    '''
    return CatalogItemsRepository(catalog_path)


# ** fixture: meta_repo
@pytest.fixture
def meta_repo(catalog_path: str) -> CatalogMetaRepository:
    '''
    Return a CatalogMetaRepository bound to the test's HDF5 file.
    '''
    return CatalogMetaRepository(catalog_path)


# *** tests

# ** test: two_repository_composition_persists_meta_and_items
def test_two_repository_composition_persists_meta_and_items(
    items_repo: CatalogItemsRepository,
    meta_repo: CatalogMetaRepository,
) -> None:
    '''
    Test that the two-repository composition pattern (CatalogItemsRepository +
    CatalogMetaRepository sharing one file) persists and reads back correctly
    through the events layer.
    '''
    DomainEvent.handle(
        SaveCatalogMeta,
        dependencies={'catalog_meta_service': meta_repo},
        catalog_name='Hardware Catalog',
        currency='USD',
    )
    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items_repo},
        sku='BOLT-001', name='Bolt', price=1.50,
    )

    meta = DomainEvent.handle(GetCatalogMeta, dependencies={'catalog_meta_service': meta_repo})
    items = DomainEvent.handle(ListCatalogItems, dependencies={'catalog_item_service': items_repo})

    assert meta.catalog_name == 'Hardware Catalog'
    assert len(items) == 1
    assert items[0].sku == 'BOLT-001'


# ** test: repository_level_filters_apply_compression
def test_repository_level_filters_apply_compression(items_repo: CatalogItemsRepository) -> None:
    '''
    Test that CatalogItemsRepository's repository-level `filters` default is
    applied automatically to the created table.
    '''
    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items_repo},
        sku='BOLT-001', name='Bolt', price=1.50,
    )

    with items_repo.client(mode='r') as h5:
        table = h5.get_table('/catalog/items')
        assert table.filters.complib == 'zlib'
        assert table.filters.complevel == 5


# ** test: apply_item_discount_mutates_aggregate_independent_of_original_row
def test_apply_item_discount_mutates_aggregate_independent_of_original_row(
    items_repo: CatalogItemsRepository,
) -> None:
    '''
    Test that ApplyItemDiscount maps the persisted row onto a mutable
    Aggregate, applies the discount, and replaces the stale row -- the
    resolved item afterward reflects the discount.
    '''
    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items_repo},
        sku='BOLT-001', name='Bolt', price=1.50,
    )

    discounted = DomainEvent.handle(
        ApplyItemDiscount,
        dependencies={'catalog_item_service': items_repo},
        sku='BOLT-001', percent=10,
    )

    assert abs(discounted.price - 1.35) < 1e-9
    persisted = DomainEvent.handle(ListCatalogItems, dependencies={'catalog_item_service': items_repo})
    assert abs(persisted[0].price - 1.35) < 1e-9


# ** test: remove_and_verify_and_compact_catalog
def test_remove_and_verify_and_compact_catalog(items_repo: CatalogItemsRepository) -> None:
    '''
    Test the events layer's direct H5Client usage alongside the mixins:
    RemoveCatalogItem, then opt-in schema verification and compact() via
    VerifyAndCompactCatalog.
    '''
    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items_repo},
        sku='BOLT-001', name='Bolt', price=1.50,
    )
    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items_repo},
        sku='WSHR-003', name='Washer', price=0.25,
    )

    removed = DomainEvent.handle(
        RemoveCatalogItem,
        dependencies={'catalog_item_service': items_repo},
        sku='WSHR-003',
    )
    DomainEvent.handle(VerifyAndCompactCatalog, dependencies={'catalog_item_service': items_repo})  # must not raise

    assert removed == 1
    remaining = DomainEvent.handle(ListCatalogItems, dependencies={'catalog_item_service': items_repo})
    assert [obj.sku for obj in remaining] == ['BOLT-001']


# ** test: add_catalog_item_rejects_duplicate_sku
def test_add_catalog_item_rejects_duplicate_sku(items_repo: CatalogItemsRepository) -> None:
    '''
    Test that AddCatalogItem rejects a sku that already exists.
    '''
    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items_repo},
        sku='BOLT-001', name='Bolt', price=1.50,
    )

    with pytest.raises(TiferetError) as exc_info:
        DomainEvent.handle(
            AddCatalogItem,
            dependencies={'catalog_item_service': items_repo},
            sku='BOLT-001', name='Bolt (dup)', price=1.50,
        )

    assert exc_info.value.error_code == 'CATALOG_ITEM_ALREADY_EXISTS'


# ** test: apply_item_discount_rejects_out_of_range_percent
def test_apply_item_discount_rejects_out_of_range_percent(items_repo: CatalogItemsRepository) -> None:
    '''
    Test that ApplyItemDiscount rejects a percent outside [0, 100].
    '''
    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items_repo},
        sku='BOLT-001', name='Bolt', price=1.50,
    )

    with pytest.raises(TiferetError) as exc_info:
        DomainEvent.handle(
            ApplyItemDiscount,
            dependencies={'catalog_item_service': items_repo},
            sku='BOLT-001', percent=150,
        )

    assert exc_info.value.error_code == 'INVALID_DISCOUNT_PERCENT'


# ** fixture: config_driven_catalog_path
@pytest.fixture
def config_driven_catalog_path() -> Path:
    '''
    Return the fixed catalog.h5 path config.yml's h5_file params resolve to
    (relative to the process cwd, which must be examples/catalog_app for
    these tests -- see the package README), removing it before and after
    each test so config-driven runs never leak state between tests or into
    a manual `python catalog_client.py` run.
    '''
    path = Path('catalog.h5')
    if path.exists():
        path.unlink()
    yield path
    if path.exists():
        path.unlink()


# ** test: config_driven_app_runs_add_item_and_list_items_features
def test_config_driven_app_runs_add_item_and_list_items_features(config_driven_catalog_path: Path) -> None:
    '''
    Test that config.yml's sessions/services/features wiring resolves
    correctly through tiferet.blueprints.app.build_app -- catches config.yml
    typos (module_path/class_name/service_id mismatches) that the
    DomainEvent.handle()-based tests above cannot, since those construct
    events directly rather than resolving them through the DI container.
    '''
    app = build_app('catalog_client')

    app.run('catalog.add_item', data={'sku': 'BOLT-001', 'name': 'Bolt', 'price': 1.50})
    items = app.run('catalog.list_items', data={})

    assert len(items) == 1
    assert items[0].sku == 'BOLT-001'


# ** test: config_driven_app_formats_registered_error_message
def test_config_driven_app_formats_registered_error_message(config_driven_catalog_path: Path) -> None:
    '''
    Test that a domain rule violation raised by an event resolves against
    config.yml's error catalog and is re-raised as a formatted TiferetAPIError
    -- catches a registered error code/message drifting out of sync with the
    inline error codes actually raised in app/events/catalog.py.
    '''
    app = build_app('catalog_client')
    app.run('catalog.add_item', data={'sku': 'BOLT-001', 'name': 'Bolt', 'price': 1.50})

    with pytest.raises(TiferetError) as exc_info:
        app.run('catalog.add_item', data={'sku': 'BOLT-001', 'name': 'Bolt (dup)', 'price': 1.50})

    assert exc_info.value.error_code == 'CATALOG_ITEM_ALREADY_EXISTS'
    assert exc_info.value.message == 'A catalog item with sku BOLT-001 already exists.'
