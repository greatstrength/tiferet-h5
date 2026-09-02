"""tiferet_h5 Integration Tests Settings"""

# *** imports

# ** core
from pathlib import Path
from typing import Any, ClassVar, Dict

# ** infra
import pytest
import tables
from pydantic import AliasChoices, Field

# ** app
from tiferet.domain import DomainObject
from tiferet.mappers import Aggregate

from ..mappers.settings import NodeObject, TableObject
from ..repos.core import NodeRepository, TableRepository
from ..repos.h5 import H5Repository
from ..utils.h5 import H5Client

# *** classes

# ** class: widget_domain_object
class WidgetDomainObject(DomainObject):
    '''Read-only domain object at the top of the stack under test.'''

    # * attribute: name
    name: str = Field(default='', description='Widget name.')

    # * attribute: price
    price: float = Field(default=0.0, description='Widget price.')


# ** class: widget_aggregate
class WidgetAggregate(Aggregate):
    '''Mutable aggregate counterpart to WidgetDomainObject.'''

    # * attribute: name
    name: str = Field(default='', description='Widget name.')

    # * attribute: price
    price: float = Field(default=0.0, description='Widget price.')


# ** class: widget_table_object
class WidgetTableObject(TableObject):
    '''TableObject mapper bridging WidgetDomainObject/WidgetAggregate to an HDF5 table row.'''

    # * attribute: name
    name: str = Field(default='', description='Widget name.')

    # * attribute: price
    price: float = Field(default=0.0, description='Widget price.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name':  tables.StringCol(64),
        'price': tables.Float64Col(),
    }


# ** class: catalog_meta_node_object
class CatalogMetaNodeObject(NodeObject):
    '''NodeObject mapper for the catalog's own group-level metadata.'''

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


# ** class: compressed_widget_repository
class CompressedWidgetRepository(TableRepository, H5Repository):
    '''
    TableRepository with a repository-level compression default set, so
    save() exercises RFP-004's compression and RFP-005's forwarding of it
    together with RFP-002's schema-version stamping.
    '''

    # * attribute: table_cls
    table_cls = WidgetTableObject

    # * attribute: table_path
    table_path = '/catalog/items'

    # * attribute: filters
    filters = tables.Filters(complib='zlib', complevel=5)


# ** class: catalog_meta_repository
class CatalogMetaRepository(NodeRepository, H5Repository):
    '''NodeRepository half of a two-repository combination sharing one HDF5 file.'''

    # * attribute: node_cls
    node_cls = CatalogMetaNodeObject

    # * attribute: node_path
    node_path = '/catalog'


# *** fixtures

# ** fixture: h5_file
@pytest.fixture
def h5_file(tmp_path: Path) -> str:
    '''
    Return a path (as str) to a not-yet-existing HDF5 file for integration tests.
    '''
    return str(tmp_path / 'catalog.h5')


# *** tests

# ** test_int: domain_to_h5client_round_trip_with_compression_and_schema_version
def test_int_domain_to_h5client_round_trip_with_compression_and_schema_version(h5_file: str) -> None:
    '''
    Exercise the full domain -> mapper -> repo -> H5Client stack together:
    a WidgetDomainObject is mapped through WidgetTableObject, persisted via a
    TableRepository that also carries a repository-level `filters` default
    (RFP-004/RFP-005), reads back into a WidgetAggregate, and is verified
    against its stamped schema_version (RFP-002) -- none of these features
    were previously exercised in the same table at once.
    '''

    # Domain -> mapper: construct the table object from a domain instance.
    domain_obj = WidgetDomainObject(name='Bolt', price=1.5)
    table_obj = WidgetTableObject.from_model(domain_obj)

    # Repo: save() creates the table with compression applied and stamps
    # schema_version in the same call.
    repo = CompressedWidgetRepository(h5_file)
    repo.save(table_obj)

    # H5Client: confirm compression actually landed on the live table.
    with repo.client(mode='r') as h5:
        table = h5.get_table('/catalog/items')
        assert table.filters.complib == 'zlib'
        assert table.filters.complevel == 5

    # Mapper -> domain: read back and map onto the aggregate.
    [result] = repo.list()
    aggregate = result.map(WidgetAggregate)

    assert isinstance(aggregate, WidgetAggregate)
    assert aggregate.name == 'Bolt'
    assert abs(aggregate.price - 1.5) < 1e-9

    # Schema integrity: opt-in verification passes against the stamped version.
    repo.verify()  # must not raise


# ** test_int: indexed_streaming_query_across_many_rows
def test_int_indexed_streaming_query_across_many_rows(h5_file: str) -> None:
    '''
    Exercise streaming reads (RFP-003) together with indexing (RFP-003) on
    the same table -- an indexed column resolved via iter_query(), the
    lazy/generator path, rather than the eager read_rows()/query() pair
    already covered by the unit suite.
    '''

    with H5Client(h5_file, mode='w') as h5:
        h5.create_table('/items', WidgetTableObject.get_description())
        h5.append_rows('/items', [
            {'name': f'item-{i}', 'price': float(i)}
            for i in range(50)
        ])
        h5.create_index('/items', 'price')

    with H5Client(h5_file, mode='r') as h5:
        assert h5.is_indexed('/items', 'price') is True

        matches = list(h5.iter_query('/items', 'price >= 40.0'))

    assert len(matches) == 10
    assert sorted(row['price'] for row in matches) == [float(i) for i in range(40, 50)]


# ** test_int: compact_preserves_schema_version_and_index_after_deletions
def test_int_compact_preserves_schema_version_and_index_after_deletions(h5_file: str) -> None:
    '''
    Exercise compaction (RFP-004) against a table that simultaneously has an
    active index (RFP-003), a stamped schema_version (RFP-002), and pending
    deletions -- verifying all three survive the copy-and-rewrite together,
    not just individually as the unit suites already check.
    '''

    repo = CompressedWidgetRepository(h5_file)
    for i in range(10):
        repo.save(WidgetTableObject(name=f'item-{i}', price=float(i)))

    with repo.client() as h5:
        h5.create_index('/catalog/items', 'price')

    # Delete roughly half the rows before compacting.
    removed = repo.delete('price < 5.0')
    assert removed == 5

    with repo.client() as h5:
        h5.compact()

    # Schema version and column drift are both still clean post-compaction.
    repo.verify()  # must not raise

    # The index survives the rewrite.
    with repo.client(mode='r') as h5:
        assert h5.is_indexed('/catalog/items', 'price') is True

        # Compression also survives, since CompressedWidgetRepository.filters
        # applies at table creation and compact() preserves existing filters
        # by default (no explicit override passed here).
        table = h5.get_table('/catalog/items')
        assert table.filters.complib == 'zlib'

    # Only the un-deleted rows remain.
    remaining = sorted(obj.price for obj in repo.list())
    assert remaining == [5.0, 6.0, 7.0, 8.0, 9.0]


# ** test_int: two_repository_composition_end_to_end
def test_int_two_repository_composition_end_to_end(h5_file: str) -> None:
    '''
    Exercise the documented two-repository-instances-per-file composition
    pattern (RFP-005) -- a TableRepository and a NodeRepository operating
    independently against one shared file -- through the full domain stack,
    rather than TableObject/NodeObject instances constructed directly as
    the unit suite does.
    '''

    items_repo = CompressedWidgetRepository(h5_file)
    meta_repo = CatalogMetaRepository(h5_file)

    meta_repo.save(CatalogMetaNodeObject(catalog_name='Hardware Catalog'))
    items_repo.save(WidgetTableObject.from_model(WidgetDomainObject(name='Bolt', price=1.5)))
    items_repo.save(WidgetTableObject.from_model(WidgetDomainObject(name='Nut', price=0.5)))

    meta = meta_repo.get()
    items = [obj.map(WidgetAggregate) for obj in items_repo.list()]

    assert meta.catalog_name == 'Hardware Catalog'
    assert len(items) == 2
    assert {item.name for item in items} == {'Bolt', 'Nut'}
    assert all(isinstance(item, WidgetAggregate) for item in items)
