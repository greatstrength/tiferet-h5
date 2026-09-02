"""tiferet_h5 Repos Core Tests"""

# *** imports

# ** core
from pathlib import Path
from typing import Any, ClassVar, Dict

# ** infra
import pytest
import tables
from pydantic import AliasChoices, Field

# ** app
from tiferet.interfaces import ServiceError

from ...mappers.settings import NodeObject, TableObject
from ..core import NodeRepository, TableRepository
from ..h5 import H5Repository

# *** constants

# ** constant: schema_version_attr
SCHEMA_VERSION_ATTR = 'schema_version'

# *** classes

# ** class: widget_table_object
class WidgetTableObject(TableObject):
    '''Minimal TableObject subclass for TableRepository tests.'''

    # * attribute: name
    name: str = Field(default='', description='Widget name.')

    # * attribute: price
    price: float = Field(default=0.0, description='Widget price.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name':  tables.StringCol(64),
        'price': tables.Float64Col(),
    }


# ** class: drifted_widget_table_object
class DriftedWidgetTableObject(TableObject):
    '''TableObject subclass declaring a schema that drifts from WidgetTableObject, for verify() tests.'''

    # * attribute: name
    name: str = Field(default='', description='Widget name.')

    # * attribute: sku
    sku: str = Field(default='', description='Column absent from the live table.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name': tables.StringCol(64),
        'sku':  tables.StringCol(32),
    }


# ** class: widget_meta_node_object
class WidgetMetaNodeObject(NodeObject):
    '''Minimal NodeObject subclass for NodeRepository tests.'''

    # * attribute: catalog_name
    catalog_name: str = Field(
        default='',
        serialization_alias='name',
        validation_alias=AliasChoices('name', 'catalog_name'),
        description='Catalog display name; stored as "name" in HDF5.',
    )

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }


# ** class: widget_repository
class WidgetRepository(TableRepository, H5Repository):
    '''Concrete TableRepository-backed repository for testing.'''

    # * attribute: table_cls
    table_cls = WidgetTableObject

    # * attribute: table_path
    table_path = '/widgets/{catalog}'


# ** class: widget_meta_repository
class WidgetMetaRepository(NodeRepository, H5Repository):
    '''Concrete NodeRepository-backed repository for testing.'''

    # * attribute: node_cls
    node_cls = WidgetMetaNodeObject

    # * attribute: node_path
    node_path = '/widgets_meta'


# ** class: catalog_items_repository
class CatalogItemsRepository(TableRepository, H5Repository):
    '''TableRepository half of a two-repository combination sharing one HDF5 file.'''

    # * attribute: table_cls
    table_cls = WidgetTableObject

    # * attribute: table_path
    table_path = '/catalog/items'


# ** class: catalog_meta_repository
class CatalogMetaRepository(NodeRepository, H5Repository):
    '''NodeRepository half of a two-repository combination sharing one HDF5 file.'''

    # * attribute: node_cls
    node_cls = WidgetMetaNodeObject

    # * attribute: node_path
    node_path = '/catalog'


# *** fixtures

# ** fixture: h5_file
@pytest.fixture
def h5_file(tmp_path: Path) -> str:
    '''
    Return a path (as str) to a not-yet-existing HDF5 file for repository tests.
    '''
    return str(tmp_path / 'widgets.h5')


# ** fixture: widget_repo
@pytest.fixture
def widget_repo(h5_file: str) -> WidgetRepository:
    '''
    Return a WidgetRepository bound to a fresh temp file.
    '''
    return WidgetRepository(h5_file)


# ** fixture: widget_meta_repo
@pytest.fixture
def widget_meta_repo(h5_file: str) -> WidgetMetaRepository:
    '''
    Return a WidgetMetaRepository bound to a fresh temp file.
    '''
    return WidgetMetaRepository(h5_file)


# *** tests

# ** test: save_creates_table_and_appends_row
def test_save_creates_table_and_appends_row(widget_repo: WidgetRepository) -> None:
    '''
    Test that save() creates the table on first write and the row is readable back.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')

    results = widget_repo.list(catalog='hardware')

    assert len(results) == 1
    assert results[0].name == 'Bolt'
    assert abs(results[0].price - 1.5) < 1e-9


# ** test: save_stamps_schema_version_on_creation
def test_save_stamps_schema_version_on_creation(widget_repo: WidgetRepository) -> None:
    '''
    Test that save() stamps a schema_version node attribute matching
    table_cls.schema_fingerprint() the first time the table is created.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')

    with widget_repo.client(mode='r') as h5:
        attrs = h5.get_node_attrs('/widgets/hardware')

    assert attrs[SCHEMA_VERSION_ATTR] == WidgetTableObject.schema_fingerprint()


# ** test: save_applies_repository_level_filters
def test_save_applies_repository_level_filters(h5_file: str) -> None:
    '''
    Test that a repository-level `filters` class attribute is forwarded to
    table creation automatically -- the piece RFP-004 explicitly deferred
    to this repository layer.
    '''
    class CompressedWidgetRepository(TableRepository, H5Repository):
        table_cls = WidgetTableObject
        table_path = '/widgets/hardware'
        filters = tables.Filters(complib='zlib', complevel=5)

    repo = CompressedWidgetRepository(h5_file)
    repo.save(WidgetTableObject(name='Bolt', price=1.5))

    with repo.client(mode='r') as h5:
        table = h5.get_table('/widgets/hardware')
        assert table.filters.complib == 'zlib'
        assert table.filters.complevel == 5


# ** test: get_returns_matching_row
def test_get_returns_matching_row(widget_repo: WidgetRepository) -> None:
    '''
    Test that get() returns the first row matching a condition.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')
    widget_repo.save(WidgetTableObject(name='Nut',  price=0.5), catalog='hardware')

    result = widget_repo.get('name == b"Nut"', catalog='hardware')

    assert result is not None
    assert result.name == 'Nut'


# ** test: get_returns_none_when_no_match
def test_get_returns_none_when_no_match(widget_repo: WidgetRepository) -> None:
    '''
    Test that get() returns None rather than raising when no row matches.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')

    result = widget_repo.get('name == b"Missing"', catalog='hardware')

    assert result is None


# ** test: list_with_condition_filters
def test_list_with_condition_filters(widget_repo: WidgetRepository) -> None:
    '''
    Test that list() with a condition returns only matching rows.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')
    widget_repo.save(WidgetTableObject(name='Nut',  price=0.5), catalog='hardware')

    results = widget_repo.list('price > 1.0', catalog='hardware')

    assert len(results) == 1
    assert results[0].name == 'Bolt'


# ** test: iter_list_streams_matching_rows
def test_iter_list_streams_matching_rows(widget_repo: WidgetRepository) -> None:
    '''
    Test that iter_list() lazily yields TableObject instances matching a condition.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')
    widget_repo.save(WidgetTableObject(name='Nut',  price=0.5), catalog='hardware')

    names = [obj.name for obj in widget_repo.iter_list('price > 1.0', catalog='hardware')]

    assert names == ['Bolt']


# ** test: delete_removes_matching_rows
def test_delete_removes_matching_rows(widget_repo: WidgetRepository) -> None:
    '''
    Test that delete() removes matching rows and returns the removed count.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')
    widget_repo.save(WidgetTableObject(name='Nut',  price=0.5), catalog='hardware')

    removed = widget_repo.delete('name == b"Nut"', catalog='hardware')

    assert removed == 1
    assert [obj.name for obj in widget_repo.list(catalog='hardware')] == ['Bolt']


# ** test: exists_true_and_false
def test_exists_true_and_false(widget_repo: WidgetRepository) -> None:
    '''
    Test that exists() reflects whether any row matches a condition.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')

    assert widget_repo.exists('name == b"Bolt"', catalog='hardware') is True
    assert widget_repo.exists('name == b"Missing"', catalog='hardware') is False


# ** test: verify_passes_for_matching_schema
def test_verify_passes_for_matching_schema(widget_repo: WidgetRepository) -> None:
    '''
    Test that verify() does not raise when the live table matches table_cls.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')

    widget_repo.verify(catalog='hardware')  # must not raise


# ** test: verify_raises_on_schema_drift
def test_verify_raises_on_schema_drift(widget_repo: WidgetRepository) -> None:
    '''
    Test that verify() is opt-in enforcement -- save()/get()/list() never
    call it automatically -- and raises a structured ServiceError when the
    live table has drifted from a different table_cls's declared schema.
    '''
    widget_repo.save(WidgetTableObject(name='Bolt', price=1.5), catalog='hardware')

    class DriftedRepository(TableRepository, H5Repository):
        table_cls = DriftedWidgetTableObject
        table_path = '/widgets/{catalog}'

    drifted_repo = DriftedRepository(widget_repo.h5_file)

    with pytest.raises(ServiceError):
        drifted_repo.verify(catalog='hardware')


# ** test: resolve_table_path_without_kwargs
def test_resolve_table_path_without_kwargs(h5_file: str) -> None:
    '''
    Test that resolve_table_path() returns a fixed path unchanged when no
    path_kwargs are given, so simple declared-path repositories need no template.
    '''
    class FixedPathRepository(TableRepository, H5Repository):
        table_cls = WidgetTableObject
        table_path = '/widgets/fixed'

    repo = FixedPathRepository(h5_file)

    assert repo.resolve_table_path() == '/widgets/fixed'


# ** test: node_repository_save_creates_group_and_sets_attrs
def test_node_repository_save_creates_group_and_sets_attrs(widget_meta_repo: WidgetMetaRepository) -> None:
    '''
    Test that save() creates the group node on first write and sets attrs.
    '''
    widget_meta_repo.save(WidgetMetaNodeObject(catalog_name='Hardware'))

    with widget_meta_repo.client(mode='r') as h5:
        attrs = h5.get_node_attrs('/widgets_meta')

    assert attrs['name'] == 'Hardware'


# ** test: node_repository_get_returns_node_object
def test_node_repository_get_returns_node_object(widget_meta_repo: WidgetMetaRepository) -> None:
    '''
    Test that get() returns a NodeObject reconstructed from the node's attrs.
    '''
    widget_meta_repo.save(WidgetMetaNodeObject(catalog_name='Hardware'))

    result = widget_meta_repo.get()

    assert isinstance(result, WidgetMetaNodeObject)
    assert result.catalog_name == 'Hardware'


# ** test: node_repository_get_returns_none_when_not_exists
def test_node_repository_get_returns_none_when_not_exists(widget_meta_repo: WidgetMetaRepository) -> None:
    '''
    Test that get() returns None when the node does not exist yet.
    '''
    assert widget_meta_repo.get() is None


# ** test: node_repository_exists_true_and_false
def test_node_repository_exists_true_and_false(widget_meta_repo: WidgetMetaRepository) -> None:
    '''
    Test that exists() reflects whether the node has been created yet.
    '''
    assert widget_meta_repo.exists() is False

    widget_meta_repo.save(WidgetMetaNodeObject(catalog_name='Hardware'))

    assert widget_meta_repo.exists() is True


# ** test: node_repository_has_no_delete_method
def test_node_repository_has_no_delete_method() -> None:
    '''
    Test that NodeRepository deliberately ships no delete() -- H5Service has
    no generic node-removal primitive, and adding one is out of scope here.
    '''
    assert not hasattr(NodeRepository, 'delete')


# ** test: two_mixin_repositories_share_one_file
def test_two_mixin_repositories_share_one_file(h5_file: str) -> None:
    '''
    Test that a TableRepository-backed and a NodeRepository-backed
    repository instance can operate independently against the same HDF5
    file -- the supported way to combine both shapes, since mixing both
    into one class collides on save()/get()/exists() under Python's MRO.
    '''
    items_repo = CatalogItemsRepository(h5_file)
    meta_repo = CatalogMetaRepository(h5_file)

    meta_repo.save(WidgetMetaNodeObject(catalog_name='Catalog Root'))
    items_repo.save(WidgetTableObject(name='Bolt', price=1.5))

    meta = meta_repo.get()
    items = items_repo.list()

    assert meta.catalog_name == 'Catalog Root'
    assert len(items) == 1
    assert items[0].name == 'Bolt'
