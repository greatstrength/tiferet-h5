"""tiferet_h5 Repos Core Tests"""

# *** imports

# ** core
import inspect
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterator

# ** infra
import pytest
import tables
from pydantic import Field

# ** app
from ...mappers import TableObject
from ...utils import H5Client
from ..core import SCHEMA_VERSION_ATTR, TableRepository
from ..h5 import H5Repository

# *** classes

# ** class: item_table_object
class ItemTableObject(TableObject):
    '''
    Minimal table object for repository mixin tests.
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
    Table repository composed with a fixed path for mixin tests.
    '''

    # * attribute: table_cls
    table_cls: ClassVar[type] = ItemTableObject

    # * attribute: table_path
    table_path: ClassVar[str] = '/items'

# ** class: grouped_item_repository
class GroupedItemRepository(TableRepository, H5Repository):
    '''
    Table repository whose path contains a caller-supplied placeholder.
    '''

    # * attribute: table_cls
    table_cls: ClassVar[type] = ItemTableObject

    # * attribute: table_path
    table_path: ClassVar[str] = '/groups/{group_id}/items'

# ** class: unstamped_item_repository
class UnstampedItemRepository(ItemTableRepository):
    '''
    Table repository that opts out of the first-write schema stamp.
    '''

    # * attribute: stamp_schema_version
    stamp_schema_version: ClassVar[bool] = False

# *** fixtures

# ** fixture: h5_path
@pytest.fixture
def h5_path(tmp_path: Path) -> str:
    '''
    Return a path string to a temporary HDF5 file that does not yet exist.
    '''

    return str(tmp_path / 'repo_core.h5')

# ** fixture: repo
@pytest.fixture
def repo(h5_path: str) -> ItemTableRepository:
    '''
    Return an item table repository aimed at the temporary HDF5 path.
    '''

    return ItemTableRepository(h5_file=h5_path)

# *** tests

# ** test: table_repository_is_exported
def test_table_repository_is_exported() -> None:
    '''
    Test that TableRepository is exported and is not itself an H5Repository.
    '''

    import tiferet_h5
    import tiferet_h5.repos as repos

    assert repos.TableRepository is TableRepository
    assert tiferet_h5.TableRepository is TableRepository
    assert not issubclass(TableRepository, H5Repository)
    assert '__init__' not in TableRepository.__dict__

# ** test: table_repository_save_get
def test_table_repository_save_get(repo: ItemTableRepository) -> None:
    '''
    Test that a composed subclass can save and get one row.
    '''

    # Append one row through the H5Repository companion.
    repo.save(ItemTableObject(name='Widget', value=1.5))

    # Read that row back by its stored name.
    found = repo.get('name == b"Widget"')

    assert isinstance(found, ItemTableObject)
    assert found.name == 'Widget'
    assert found.value == 1.5
    assert repo.get('name == b"Missing"') is None

# ** test: table_repository_missing_file_does_not_create
def test_table_repository_missing_file_does_not_create(
        repo: ItemTableRepository,
        h5_path: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
    '''
    Test that missing-file reads return empty results and do not create the file.
    '''

    # Fail the test if a read constructs a client.
    def fail_client(*args, **kwargs):
        raise AssertionError('missing-file reads must not open an H5Client.')

    monkeypatch.setattr('tiferet_h5.repos.h5.H5Client', fail_client)

    # Reads must stay empty without creating the path.
    stream = repo.iter_list()
    assert Path(h5_path).exists() is False
    assert repo.get('name == b"Widget"') is None
    assert repo.list() == []
    assert repo.exists('name == b"Widget"') is False
    assert isinstance(stream, Iterator)
    assert list(stream) == []
    assert Path(h5_path).exists() is False

# ** test: table_repository_verify_is_opt_in
def test_table_repository_verify_is_opt_in(
        repo: ItemTableRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
    '''
    Test that verify calls assert_schema and save, get, and list do not.
    '''

    calls = []

    # Record schema checks without requiring the utils method to exist yet.
    def record_assert_schema(self, path, table_cls, check_version=True):
        calls.append((path, table_cls))

    monkeypatch.setattr(H5Client, 'assert_schema', record_assert_schema, raising=False)

    # Ordinary CRUD must not opt into the schema check.
    repo.save(ItemTableObject(name='Widget', value=1.5))
    assert repo.get('name == b"Widget"') is not None
    assert len(repo.list()) == 1
    assert calls == []

    # verify is the only caller.
    repo.verify()
    assert calls == [('/items', ItemTableObject)]

# ** test: table_repository_save_omits_filters
def test_table_repository_save_omits_filters() -> None:
    '''
    Test that save does not reference filters or assert_schema.
    '''

    source = inspect.getsource(TableRepository.save)

    assert 'filters' not in source
    assert 'assert_schema' not in source

# ** test: save_stamps_schema_version_once
def test_save_stamps_schema_version_once(
        repo: ItemTableRepository,
        h5_path: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
    '''
    Test that the first save stamps schema_version and a later save leaves it.
    '''

    # The attribute name and the default flag are part of the stamp contract.
    assert SCHEMA_VERSION_ATTR == 'schema_version'
    assert TableRepository.stamp_schema_version is True

    # The first save creates the table and writes the current fingerprint.
    expected = ItemTableObject.schema_fingerprint()
    repo.save(ItemTableObject(name='Alpha', value=1.0))

    with H5Client(h5_path, mode='r') as h5:
        stamped = h5.get_node_attr('/items', SCHEMA_VERSION_ATTR)

    assert stamped == expected

    # A later fingerprint must not replace the stamp or call set_node_attr.
    calls = []
    original = H5Client.set_node_attr

    def record_set_node_attr(self, path, name, value):
        calls.append((path, name, value))
        return original(self, path, name, value)

    # Drift the live fingerprint without rewriting the stored stamp.
    def drifted(cls) -> str:
        return 'drifted000000'

    monkeypatch.setattr(H5Client, 'set_node_attr', record_set_node_attr)
    monkeypatch.setattr(ItemTableObject, 'schema_fingerprint', classmethod(drifted))

    assert ItemTableObject.schema_fingerprint() != expected
    repo.save(ItemTableObject(name='Beta', value=2.0))

    assert calls == []
    with H5Client(h5_path, mode='r') as h5:
        assert h5.get_node_attr('/items', SCHEMA_VERSION_ATTR) == expected

    found = repo.get('name == b"Beta"')
    assert found is not None
    assert found.name == 'Beta'

# ** test: save_skips_stamp_when_disabled
def test_save_skips_stamp_when_disabled(
        h5_path: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
    '''
    Test that a subclass with stamp_schema_version false does not set the attribute.
    '''

    # Fail if the opt-out path still writes a node attribute.
    def fail_set_node_attr(self, path, name, value):
        raise AssertionError('disabled stamp must not call set_node_attr.')

    monkeypatch.setattr(H5Client, 'set_node_attr', fail_set_node_attr)

    # Save through a repository that opts out of the stamp.
    repo = UnstampedItemRepository(h5_file=h5_path)
    assert repo.stamp_schema_version is False
    repo.save(ItemTableObject(name='Alpha', value=1.0))

    # The table exists, but schema_version was not written.
    with H5Client(h5_path, mode='r') as h5:
        attrs = h5.get_node_attrs('/items')

    assert SCHEMA_VERSION_ATTR not in attrs
    assert repo.get('name == b"Alpha"') is not None

# ** test: table_repository_list_and_iter_list
def test_table_repository_list_and_iter_list(repo: ItemTableRepository) -> None:
    '''
    Test that list and iter_list return mapped rows, including a filtered stream.
    '''

    # Append two rows.
    repo.save(ItemTableObject(name='Alpha', value=1.0))
    repo.save(ItemTableObject(name='Beta', value=2.0))

    # list materializes every row in append order.
    listed = repo.list()
    assert [item.name for item in listed] == ['Alpha', 'Beta']
    assert all(isinstance(item, ItemTableObject) for item in listed)

    # iter_list yields the filtered subset without building the caller's list.
    stream = repo.iter_list(condition='value > 1.5')
    assert isinstance(stream, Iterator)
    assert not isinstance(stream, list)
    streamed = list(stream)

    assert len(streamed) == 1
    assert streamed[0].name == 'Beta'
    assert streamed[0].value == 2.0

# ** test: table_repository_delete_returns_removed_count
def test_table_repository_delete_returns_removed_count(repo: ItemTableRepository) -> None:
    '''
    Test that delete returns the count from remove_rows.
    '''

    # Append two rows, then remove one.
    repo.save(ItemTableObject(name='Alpha', value=1.0))
    repo.save(ItemTableObject(name='Beta', value=2.0))
    removed = repo.delete('value < 1.5')

    assert removed == 1
    remaining = repo.list()
    assert len(remaining) == 1
    assert remaining[0].name == 'Beta'

# ** test: table_repository_exists
def test_table_repository_exists(repo: ItemTableRepository) -> None:
    '''
    Test that exists reports a matching row and ignores a miss.
    '''

    repo.save(ItemTableObject(name='Alpha', value=1.0))

    assert repo.exists('name == b"Alpha"') is True
    assert repo.exists('name == b"Missing"') is False

# ** test: table_repository_missing_node_returns_empty
def test_table_repository_missing_node_returns_empty(
        repo: ItemTableRepository,
        h5_path: str,
    ) -> None:
    '''
    Test that a present file with no table node reads as empty and is not created.
    '''

    # Create a valid file that does not contain the table node.
    with H5Client(h5_path, mode='w') as h5:
        h5.create_group('/other')

    # Reads must not create the missing table.
    assert repo.get('name == b"Alpha"') is None
    assert repo.list() == []
    assert list(repo.iter_list()) == []
    assert repo.exists('name == b"Alpha"') is False

    with H5Client(h5_path, mode='r') as h5:
        assert h5.node_exists('/items') is False

# ** test: table_repository_formats_path_kwargs
def test_table_repository_formats_path_kwargs(h5_path: str) -> None:
    '''
    Test that path kwargs are applied only when supplied.
    '''

    repo = GroupedItemRepository(h5_file=h5_path)
    assert repo.resolve_table_path() == '/groups/{group_id}/items'

    # Save and read through the formatted path.
    repo.save(ItemTableObject(name='Widget', value=1.5), group_id='calc')
    found = repo.get('name == b"Widget"', group_id='calc')

    assert found is not None
    assert found.name == 'Widget'
    assert repo.get('name == b"Widget"', group_id='other') is None
    assert repo.exists('name == b"Widget"', group_id='calc') is True
    assert repo.delete('name == b"Widget"', group_id='calc') == 1
    assert repo.exists('name == b"Widget"', group_id='calc') is False
