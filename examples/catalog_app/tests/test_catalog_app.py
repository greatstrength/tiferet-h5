"""Catalog example tests."""

# *** imports

# ** core
import inspect
import sys
from pathlib import Path

# ** infra
import pytest

# ** app
EXAMPLE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLE_ROOT))

from tiferet import App, DomainEvent, TiferetError
from tiferet_h5 import NodeRepository, TableRepository

from app.events.catalog import (
    CATALOG_DISCOUNT_INVALID_ID,
    CATALOG_ITEM_EXISTS_ID,
    CATALOG_ITEM_NOT_FOUND_ID,
    CATALOG_ITEM_PRICE_INVALID_ID,
    CATALOG_META_CURRENCY_EMPTY_ID,
    CATALOG_META_NOT_FOUND_ID,
    AddCatalogItem,
    ApplyItemDiscount,
    GetCatalogMeta,
    ListCatalogItems,
    RemoveCatalogItem,
    SaveCatalogMeta,
    VerifyAndCompactCatalog,
)
from app.mappers.catalog import CatalogItemTableObject
from app.repos.catalog import CatalogItemsRepository, CatalogMetaRepository

# *** fixtures

# ** fixture: h5_file
@pytest.fixture
def h5_file(tmp_path: Path) -> str:
    '''
    Return a temporary HDF5 path that does not yet exist.
    '''

    return str(tmp_path / 'catalog.h5')

# ** fixture: items
@pytest.fixture
def items(h5_file: str) -> CatalogItemsRepository:
    '''
    Return an item repository aimed at the temporary file.
    '''

    return CatalogItemsRepository(h5_file=h5_file)

# ** fixture: meta
@pytest.fixture
def meta(h5_file: str) -> CatalogMetaRepository:
    '''
    Return a meta repository aimed at the same temporary file.
    '''

    return CatalogMetaRepository(h5_file=h5_file)

# ** fixture: catalog_cwd
@pytest.fixture
def catalog_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    '''
    Point App('catalog_client') at a temporary copy of config.yml.
    '''

    # Keep the example package importable after leaving its directory.
    monkeypatch.syspath_prepend(str(EXAMPLE_ROOT))

    # Rewrite the shared file path so the test does not write catalog.h5 in-tree.
    h5_file = tmp_path / 'catalog.h5'
    config = (EXAMPLE_ROOT / 'config.yml').read_text().replace('catalog.h5', str(h5_file))
    (tmp_path / 'config.yml').write_text(config)
    monkeypatch.chdir(tmp_path)
    return h5_file

# *** tests

# ** test: repositories_are_separate_classes
def test_repositories_are_separate_classes() -> None:
    '''
    Test that neither repository inherits both mixins.
    '''

    assert issubclass(CatalogItemsRepository, TableRepository)
    assert not issubclass(CatalogItemsRepository, NodeRepository)
    assert issubclass(CatalogMetaRepository, NodeRepository)
    assert not issubclass(CatalogMetaRepository, TableRepository)

# ** test: catalog_client_uses_app_run
def test_catalog_client_uses_app_run() -> None:
    '''
    Test that the client constructs App('catalog_client') and does not build a repository.
    '''

    source = (EXAMPLE_ROOT / 'catalog_client.py').read_text()

    assert "App('catalog_client')" in source
    assert 'app.run' in source
    assert 'CatalogItemsRepository(' not in source
    assert 'CatalogMetaRepository(' not in source

# ** test: add_catalog_item_rejects_duplicate_sku
def test_add_catalog_item_rejects_duplicate_sku(items: CatalogItemsRepository) -> None:
    '''
    Test that AddCatalogItem rejects a duplicate sku.
    '''

    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items},
        sku='WIDGET-1',
        name='Widget',
        price=10.0,
    )

    with pytest.raises(TiferetError) as exc_info:
        DomainEvent.handle(
            AddCatalogItem,
            dependencies={'catalog_item_service': items},
            sku='WIDGET-1',
            name='Other',
            price=12.0,
        )

    assert exc_info.value.error_code == CATALOG_ITEM_EXISTS_ID
    listed = DomainEvent.handle(
        ListCatalogItems,
        dependencies={'catalog_item_service': items},
    )
    assert [item.sku for item in listed] == ['WIDGET-1']

# ** test: apply_item_discount_rules
def test_apply_item_discount_rules(items: CatalogItemsRepository) -> None:
    '''
    Test missing, non-positive, and out-of-range discount rules, then a valid replace.
    '''

    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items},
        sku='WIDGET-1',
        name='Widget',
        price=10.0,
    )
    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items},
        sku='FREE-1',
        name='Free',
        price=0.0,
    )

    with pytest.raises(TiferetError) as missing:
        DomainEvent.handle(
            ApplyItemDiscount,
            dependencies={'catalog_item_service': items},
            sku='MISSING',
            discount=0.1,
        )
    assert missing.value.error_code == CATALOG_ITEM_NOT_FOUND_ID

    with pytest.raises(TiferetError) as non_positive:
        DomainEvent.handle(
            ApplyItemDiscount,
            dependencies={'catalog_item_service': items},
            sku='FREE-1',
            discount=0.1,
        )
    assert non_positive.value.error_code == CATALOG_ITEM_PRICE_INVALID_ID

    with pytest.raises(TiferetError) as outside:
        DomainEvent.handle(
            ApplyItemDiscount,
            dependencies={'catalog_item_service': items},
            sku='WIDGET-1',
            discount=1.5,
        )
    assert outside.value.error_code == CATALOG_DISCOUNT_INVALID_ID

    discounted = DomainEvent.handle(
        ApplyItemDiscount,
        dependencies={'catalog_item_service': items},
        sku='WIDGET-1',
        discount=0.25,
    )

    assert discounted.price == 7.5
    listed = items.list()
    widget = [item for item in listed if item.sku == 'WIDGET-1']
    assert len(widget) == 1
    assert widget[0].price == 7.5

# ** test: remove_catalog_item_rejects_missing_sku
def test_remove_catalog_item_rejects_missing_sku(items: CatalogItemsRepository) -> None:
    '''
    Test that RemoveCatalogItem rejects a missing sku.
    '''

    with pytest.raises(TiferetError) as exc_info:
        DomainEvent.handle(
            RemoveCatalogItem,
            dependencies={'catalog_item_service': items},
            sku='MISSING',
        )

    assert exc_info.value.error_code == CATALOG_ITEM_NOT_FOUND_ID

# ** test: save_catalog_meta_rejects_empty_currency
def test_save_catalog_meta_rejects_empty_currency(meta: CatalogMetaRepository) -> None:
    '''
    Test that SaveCatalogMeta rejects an empty currency.
    '''

    with pytest.raises(TiferetError) as exc_info:
        DomainEvent.handle(
            SaveCatalogMeta,
            dependencies={'catalog_meta_service': meta},
            title='Workshop',
            currency='  ',
        )

    assert exc_info.value.error_code == CATALOG_META_CURRENCY_EMPTY_ID

# ** test: get_catalog_meta_raises_not_found
def test_get_catalog_meta_raises_not_found(meta: CatalogMetaRepository) -> None:
    '''
    Test that GetCatalogMeta raises not-found when the node is absent.
    '''

    with pytest.raises(TiferetError) as exc_info:
        DomainEvent.handle(
            GetCatalogMeta,
            dependencies={'catalog_meta_service': meta},
        )

    assert exc_info.value.error_code == CATALOG_META_NOT_FOUND_ID

# ** test: verify_and_compact_calls_assert_schema_and_compact
def test_verify_and_compact_calls_assert_schema_and_compact(
        items: CatalogItemsRepository,
        meta: CatalogMetaRepository,
    ) -> None:
    '''
    Test that VerifyAndCompactCatalog calls assert_schema and compact.
    '''

    source = inspect.getsource(VerifyAndCompactCatalog.execute)
    assert 'assert_schema' in source
    assert 'compact()' in source

    DomainEvent.handle(
        AddCatalogItem,
        dependencies={'catalog_item_service': items},
        sku='WIDGET-1',
        name='Widget',
        price=10.0,
    )
    DomainEvent.handle(
        SaveCatalogMeta,
        dependencies={'catalog_meta_service': meta},
        title='Workshop',
        currency='USD',
    )

    DomainEvent.handle(
        VerifyAndCompactCatalog,
        dependencies={'catalog_item_service': items},
    )

    listed = items.list()
    stored_meta = meta.get()
    assert [item.sku for item in listed] == ['WIDGET-1']
    assert stored_meta.title == 'Workshop'
    assert stored_meta.currency == 'USD'
    assert items.table_cls is CatalogItemTableObject

# ** test: app_run_adds_and_lists_items
def test_app_run_adds_and_lists_items(catalog_cwd: Path) -> None:
    '''
    Test that app.run adds an item and lists it through config.yml.
    '''

    app = App('catalog_client')
    added = app.run(
        'catalog.add_item',
        data=dict(sku='APP-1', name='App Item', price=8.0),
    )
    listed = app.run('catalog.list_items', data={})

    assert added.sku == 'APP-1'
    assert added.price == 8.0
    assert [item.sku for item in listed] == ['APP-1']
    assert catalog_cwd.exists()

# ** test: app_run_saves_meta_and_compacts
def test_app_run_saves_meta_and_compacts(catalog_cwd: Path) -> None:
    '''
    Test that app.run saves meta and compacts through config.yml.
    '''

    app = App('catalog_client')
    app.run(
        'catalog.add_item',
        data=dict(sku='APP-1', name='App Item', price=8.0),
    )
    saved = app.run(
        'catalog.save_meta',
        data=dict(title='Field', currency='EUR'),
    )
    loaded = app.run('catalog.get_meta', data={})
    app.run('catalog.verify_and_compact', data={})
    listed = app.run('catalog.list_items', data={})

    assert saved.currency == 'EUR'
    assert loaded.title == 'Field'
    assert loaded.currency == 'EUR'
    assert [item.sku for item in listed] == ['APP-1']
