"""tiferet_h5 Cross-Feature Integration Tests"""

# *** imports

# ** core
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

# ** infra
import pytest
import tables
from pydantic import AliasChoices, Field

# ** app
from tiferet.interfaces import ServiceError

from ..mappers import NodeObject, TableObject
from ..repos import H5Repository, NodeRepository, TableRepository
from ..utils import H5Client

# *** classes

# ** class: item_table_object
class ItemTableObject(TableObject):
    '''
    Minimal table object shared by the cross-feature tests.
    '''

    # * attribute: name
    name: str = Field(default='', description='Item name.')

    # * attribute: value
    value: float = Field(default=0.0, description='Numeric value.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name': tables.StringCol(64),
        'value': tables.Float64Col(),
    }

# ** class: item_table_repository
class ItemTableRepository(TableRepository, H5Repository):
    '''
    Table repository composed alone, with a create-time compression policy.
    '''

    # * attribute: table_cls
    table_cls: ClassVar[type] = ItemTableObject

    # * attribute: table_path
    table_path: ClassVar[str] = '/items'

    # * attribute: filters
    filters: ClassVar[Optional[tables.Filters]] = tables.Filters(complevel=1)

# ** class: meta_node_object
class MetaNodeObject(NodeObject):
    '''
    Minimal node object for the shared-file repository test.
    '''

    # * attribute: catalog_name
    catalog_name: str = Field(
        default='',
        serialization_alias='name',
        validation_alias=AliasChoices('name', 'catalog_name'),
        description='Catalog display name stored as name.',
    )

    # * attribute: note
    note: Optional[str] = Field(default=None, description='Optional note.')

    # * attribute: _NULLABLE_FIELDS
    _NULLABLE_FIELDS: ClassVar[List[str]] = [
        'note',
    ]

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {
            'by_alias': True,
            'exclude_none': True,
        },
    }

# ** class: meta_node_repository
class MetaNodeRepository(NodeRepository, H5Repository):
    '''
    Node repository composed alone, not mixed with TableRepository.
    '''

    # * attribute: node_cls
    node_cls: ClassVar[type] = MetaNodeObject

    # * attribute: node_path
    node_path: ClassVar[str] = '/catalog'

# *** tests

# ** test: schema_assertion_against_repository_table
def test_schema_assertion_against_repository_table(tmp_path: Path) -> None:
    '''
    Test that a table written by TableRepository.save passes assert_schema.

    :param tmp_path: Temporary directory supplied by pytest.
    :type tmp_path: Path
    '''

    # Save one row. The first create stamps schema_version and applies filters.
    h5_path = str(tmp_path / 'schema.h5')
    repo = ItemTableRepository(h5_file=h5_path)
    repo.save(ItemTableObject(name='Widget', value=1.5))

    # A matching declaration does not raise, including the stored fingerprint.
    with H5Client(h5_path, mode='r') as h5:
        h5.assert_schema(repo.table_path, ItemTableObject)
        assert h5.get_table(repo.table_path).filters.complevel == 1

    # Column drift still raises, so a no-op assert_schema cannot pass.
    class DriftedItem(TableObject):
        '''Declares a column the repository table does not have.'''

        name: str = Field(default='')
        value: float = Field(default=0.0)
        note: str = Field(default='')
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name': tables.StringCol(64),
            'value': tables.Float64Col(),
            'note': tables.StringCol(16),
        }

    with H5Client(h5_path, mode='r') as h5:
        with pytest.raises(ServiceError) as exc_info:
            h5.assert_schema(repo.table_path, DriftedItem)

    assert exc_info.value.error_code == 'H5_SCHEMA_MISMATCH'

# ** test: streaming_and_index
def test_streaming_and_index(tmp_path: Path) -> None:
    '''
    Test that iter_query streams rows after create_index and is_indexed is true.

    :param tmp_path: Temporary directory supplied by pytest.
    :type tmp_path: Path
    '''

    h5_path = tmp_path / 'stream.h5'
    with H5Client(h5_path, mode='a') as h5:
        h5.create_table('/items', ItemTableObject.get_description())
        h5.append_rows('/items', [
            {'name': 'Alpha', 'value': 1.0},
            {'name': 'Beta', 'value': 2.0},
        ])

        # Index the queried column, then stream without building a list first.
        h5.create_index('/items', 'name')
        assert h5.is_indexed('/items', 'name') is True

        stream = h5.iter_query('/items', 'value > 1.5')
        assert isinstance(stream, Iterator)
        assert not isinstance(stream, list)
        assert list(stream) == [{'name': 'Beta', 'value': 2.0}]

        # iter_rows remains available on the indexed table.
        rows = list(h5.iter_rows('/items'))
        assert [row['name'] for row in rows] == ['Alpha', 'Beta']

# ** test: compact_keeps_column_index
def test_compact_keeps_column_index(tmp_path: Path) -> None:
    '''
    Test that compact() keeps a column index after a row is deleted.

    :param tmp_path: Temporary directory supplied by pytest.
    :type tmp_path: Path
    '''

    h5_path = tmp_path / 'compact.h5'
    with H5Client(h5_path, mode='a') as h5:
        h5.create_table('/items', ItemTableObject.get_description())
        h5.append_rows('/items', [
            {'name': 'Alpha', 'value': 1.0},
            {'name': 'Beta', 'value': 2.0},
        ])
        h5.create_index('/items', 'name')
        assert h5.is_indexed('/items', 'name') is True

        # Delete one row, then rewrite the file.
        removed = h5.remove_rows('/items', 'name == b"Alpha"')
        assert removed == 1
        h5.compact()

        # The copied index must still be present, and the survivor readable.
        assert h5.is_indexed('/items', 'name') is True
        assert h5.get_table('/items').cols.name.index.kind == 'full'
        assert h5.read_rows('/items') == [{'name': 'Beta', 'value': 2.0}]

    # Reopen the replaced file so a dropped on-disk index fails this test.
    with H5Client(h5_path, mode='r') as h5:
        assert h5.is_indexed('/items', 'name') is True
        assert list(h5.iter_rows('/items')) == [{'name': 'Beta', 'value': 2.0}]

# ** test: table_and_node_repositories_share_a_file
def test_table_and_node_repositories_share_a_file(tmp_path: Path) -> None:
    '''
    Test that separate table and node repositories round-trip one file.

    :param tmp_path: Temporary directory supplied by pytest.
    :type tmp_path: Path
    '''

    # Two instances, two mixins, one filesystem path. Not one combined class.
    h5_path = str(tmp_path / 'shared.h5')
    table_repo = ItemTableRepository(h5_file=h5_path)
    node_repo = MetaNodeRepository(h5_file=h5_path)

    assert type(table_repo) is not type(node_repo)
    assert issubclass(ItemTableRepository, TableRepository)
    assert not issubclass(ItemTableRepository, NodeRepository)
    assert issubclass(MetaNodeRepository, NodeRepository)
    assert not issubclass(MetaNodeRepository, TableRepository)
    assert table_repo.h5_file == node_repo.h5_file == h5_path

    # Both mixins round-trip through the same file.
    table_repo.save(ItemTableObject(name='Widget', value=1.5))
    node_repo.save(MetaNodeObject(catalog_name='Catalog', note='kept'))

    found = table_repo.get('name == b"Widget"')
    meta = node_repo.get()

    assert found is not None
    assert found.name == 'Widget'
    assert found.value == 1.5
    assert meta is not None
    assert meta.catalog_name == 'Catalog'
    assert meta.note == 'kept'
    assert node_repo.exists() is True
