"""tiferet_h5 Utils H5 Tests"""

# *** imports

# ** core
import inspect
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar, Dict

# ** infra
import numpy as np
import pytest
import tables
from pydantic import Field

# ** app
from tiferet.interfaces import ServiceError

from ...interfaces import H5Service
from ...mappers.core import TableObject
from ..h5 import (
    H5_CONN_NOT_INITIALIZED_ID,
    H5_CONN_NOT_INITIALIZED_MESSAGE,
    H5_FILE_ALREADY_OPEN_ID,
    H5_FILE_NOT_FOUND_ID,
    H5_GROUP_CREATE_FAILED_ID,
    H5_INDEX_FAILED_ID,
    H5_INVALID_FILE_ID,
    H5_INVALID_MODE_ID,
    H5_NODE_NOT_FOUND_ID,
    H5Client,
    normalize_row,
)

# *** constants

# ** constant: h5_extensions
H5_EXTENSIONS = ['.h5', '.hdf5']

# *** classes

# ** class: sample_table_object
class SampleTableObject(TableObject):
    '''Minimal TableObject for H5Client integration tests.'''

    # * attribute: name
    name: str = Field(default='', description='Name.')

    # * attribute: value
    value: float = Field(default=0.0, description='Numeric value.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name':  tables.StringCol(128),
        'value': tables.Float64Col(),
    }

# ** class: sku_table_object
class SkuTableObject(TableObject):
    '''TableObject with an indexable sku column for index tests.'''

    # * attribute: sku
    sku: str = Field(default='', description='Stock keeping unit.')

    # * attribute: missing
    missing: str = Field(default='', description='Unindexed companion column.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'sku': tables.StringCol(32),
        'missing': tables.StringCol(32),
    }

# *** fixtures

# ** fixture: h5_path
@pytest.fixture
def h5_path(tmp_path: Path) -> Path:
    '''
    Return a path to a temporary HDF5 file (does not yet exist).
    '''
    return tmp_path / 'test.h5'

# ** fixture: existing_h5
@pytest.fixture
def existing_h5(h5_path: Path) -> Path:
    '''
    Create a minimal HDF5 file and return its path.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_group('/data')
    return h5_path

# ** fixture: h5_with_table
@pytest.fixture
def h5_with_table(h5_path: Path) -> Path:
    '''
    Create an HDF5 file with a pre-populated table and return its path.
    '''
    with H5Client(h5_path, mode='w') as h5:
        t = h5.create_table('/items', SampleTableObject.get_description())
        SampleTableObject(name='Alpha', value=1.0).to_row(t)
        SampleTableObject(name='Beta',  value=2.0).to_row(t)
        SampleTableObject(name='Gamma', value=3.0).to_row(t)
        t.flush()
    return h5_path

# *** tests

# ** test: verify_mode_valid
@pytest.mark.parametrize('mode', ['r', 'r+', 'w', 'w-', 'a'])
def test_verify_mode_valid(h5_path: Path, mode: str) -> None:
    '''
    Test that verify_mode() passes silently for all valid PyTables modes.
    '''
    client = H5Client(h5_path, mode=mode)
    client.verify_mode()  # must not raise

# ** test: verify_mode_invalid
def test_verify_mode_invalid(h5_path: Path) -> None:
    '''
    Test that verify_mode() raises H5_INVALID_MODE for an unrecognised mode.
    '''
    client = H5Client(h5_path, mode='x')
    with pytest.raises(ServiceError) as exc_info:
        client.verify_mode()

    assert exc_info.value.error_code == H5_INVALID_MODE_ID
    assert exc_info.value.error_code == 'H5_INVALID_MODE'

# ** test: verify_file_read_not_found
def test_verify_file_read_not_found(tmp_path: Path) -> None:
    '''
    Test that verify_file() raises H5_FILE_NOT_FOUND when the file is absent in read mode.
    '''
    missing = tmp_path / 'missing.h5'
    with pytest.raises(ServiceError) as exc_info:
        H5Client.verify_file(missing, mode='r')

    assert exc_info.value.error_code == H5_FILE_NOT_FOUND_ID
    assert exc_info.value.error_code == 'H5_FILE_NOT_FOUND'

# ** test: verify_file_read_wrong_extension
def test_verify_file_read_wrong_extension(tmp_path: Path) -> None:
    '''
    Test that verify_file() raises H5_INVALID_FILE when the extension is not .h5/.hdf5.
    '''
    bad_ext = tmp_path / 'data.yaml'
    bad_ext.touch()
    with pytest.raises(ServiceError) as exc_info:
        H5Client.verify_file(bad_ext, mode='r')

    assert exc_info.value.error_code == H5_INVALID_FILE_ID
    assert exc_info.value.error_code == 'H5_INVALID_FILE'

# ** test: verify_file_write_parent_missing
def test_verify_file_write_parent_missing(tmp_path: Path) -> None:
    '''
    Test that verify_file() raises H5_FILE_NOT_FOUND when the parent dir is absent.
    '''
    nested = tmp_path / 'nonexistent_dir' / 'data.h5'
    with pytest.raises(ServiceError) as exc_info:
        H5Client.verify_file(nested, mode='w')

    assert exc_info.value.error_code == H5_FILE_NOT_FOUND_ID

# ** test: open_file_creates_file
def test_open_file_creates_file(h5_path: Path) -> None:
    '''
    Test that open_file() in append mode creates the HDF5 file if absent.
    '''
    client = H5Client(h5_path, mode='a')
    client.open_file()

    assert client.h5file is not None
    assert h5_path.exists()

    client.close_file()

# ** test: close_file_resets_handle
def test_close_file_resets_handle(h5_path: Path) -> None:
    '''
    Test that close_file() sets h5file back to None.
    '''
    client = H5Client(h5_path, mode='a')
    client.open_file()
    client.close_file()

    assert client.h5file is None

# ** test: context_manager_opens_and_closes
def test_context_manager_opens_and_closes(h5_path: Path) -> None:
    '''
    Test that the context manager opens the file on entry and closes it on exit.
    '''
    with H5Client(h5_path, mode='w') as h5:
        assert h5.h5file is not None

    assert h5.h5file is None

# ** test: open_file_already_open
def test_open_file_already_open(h5_path: Path) -> None:
    '''
    Test that opening an already-open client raises H5_FILE_ALREADY_OPEN.
    '''
    client = H5Client(h5_path, mode='a')
    client.open_file()
    with pytest.raises(ServiceError) as exc_info:
        client.open_file()

    assert exc_info.value.error_code == H5_FILE_ALREADY_OPEN_ID
    assert exc_info.value.error_code == 'H5_FILE_ALREADY_OPEN'
    client.close_file()

# ** test: open_file_corrupt_chains_cause
def test_open_file_corrupt_chains_cause(tmp_path: Path) -> None:
    '''
    Test that a failed open raises ServiceError chained to the driver exception.
    '''
    bad = tmp_path / 'bad.h5'
    bad.write_bytes(b'not an hdf5 file')
    client = H5Client(bad, mode='r')
    with pytest.raises(ServiceError) as exc_info:
        client.open_file()

    assert exc_info.value.error_code == H5_FILE_NOT_FOUND_ID
    assert isinstance(exc_info.value.__cause__, (tables.HDF5ExtError, OSError))

# ** test: operation_before_open_raises
def test_operation_before_open_raises(h5_path: Path) -> None:
    '''
    Test that calling node_exists() before open_file() raises H5_CONN_NOT_INITIALIZED.
    '''
    client = H5Client(h5_path, mode='a')
    with pytest.raises(ServiceError) as exc_info:
        client.node_exists('/')

    assert exc_info.value.error_code == H5_CONN_NOT_INITIALIZED_ID
    assert exc_info.value.error_code == 'H5_CONN_NOT_INITIALIZED'
    assert exc_info.value.message == H5_CONN_NOT_INITIALIZED_MESSAGE

# ** test: node_exists_true
def test_node_exists_true(existing_h5: Path) -> None:
    '''
    Test that node_exists() returns True for an existing node path.
    '''
    with H5Client(existing_h5, mode='r') as h5:
        assert h5.node_exists('/data') is True

# ** test: node_exists_false
def test_node_exists_false(existing_h5: Path) -> None:
    '''
    Test that node_exists() returns False for a non-existent path.
    '''
    with H5Client(existing_h5, mode='r') as h5:
        assert h5.node_exists('/does_not_exist') is False

# ** test: create_group
def test_create_group(h5_path: Path) -> None:
    '''
    Test that create_group() creates a navigable group node.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_group('/features')
        assert h5.node_exists('/features') is True

# ** test: create_group_nested
def test_create_group_nested(h5_path: Path) -> None:
    '''
    Test that create_group() creates intermediate parent groups automatically.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_group('/features/calc')
        assert h5.node_exists('/features/calc') is True

# ** test: get_group_found
def test_get_group_found(existing_h5: Path) -> None:
    '''
    Test that get_group() returns the group object for an existing path.
    '''
    with H5Client(existing_h5, mode='r') as h5:
        group = h5.get_group('/data')
        assert group is not None

# ** test: get_group_not_found
def test_get_group_not_found(existing_h5: Path) -> None:
    '''
    Test that get_group() raises H5_NODE_NOT_FOUND for a missing path.
    '''
    with H5Client(existing_h5, mode='r') as h5:
        with pytest.raises(ServiceError) as exc_info:
            h5.get_group('/does_not_exist')

    assert exc_info.value.error_code == H5_NODE_NOT_FOUND_ID
    assert exc_info.value.error_code == 'H5_NODE_NOT_FOUND'
    assert isinstance(exc_info.value.__cause__, tables.NoSuchNodeError)

# ** test: create_table
def test_create_table(h5_path: Path) -> None:
    '''
    Test that create_table() creates a table node with the given schema.
    '''
    with H5Client(h5_path, mode='w') as h5:
        t = h5.create_table('/items', SampleTableObject.get_description())
        assert t is not None
        assert set(t.colnames) == {'name', 'value'}

# ** test: get_or_create_table_creates
def test_get_or_create_table_creates(h5_path: Path) -> None:
    '''
    Test that get_or_create_table() creates the table when the node does not exist.
    '''
    with H5Client(h5_path, mode='w') as h5:
        t = h5.get_or_create_table('/items', SampleTableObject.get_description())
        assert t is not None
        assert h5.node_exists('/items') is True

# ** test: get_or_create_table_gets_existing
def test_get_or_create_table_gets_existing(h5_with_table: Path) -> None:
    '''
    Test that get_or_create_table() returns the existing table without truncating.
    '''
    with H5Client(h5_with_table, mode='a') as h5:
        t = h5.get_or_create_table('/items', SampleTableObject.get_description())
        assert t.nrows == 3

# ** test: append_rows_and_read_all
def test_append_rows_and_read_all(h5_path: Path) -> None:
    '''
    Test that append_rows() writes rows and read_rows() returns all of them.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_table('/items', SampleTableObject.get_description())
        h5.append_rows('/items', [
            {'name': 'Alpha', 'value': 1.0},
            {'name': 'Beta',  'value': 2.0},
        ])

    with H5Client(h5_path, mode='r') as h5:
        rows = h5.read_rows('/items')

    assert len(rows) == 2
    assert rows[0]['name'] == 'Alpha'
    assert rows[1]['name'] == 'Beta'

# ** test: read_rows_sliced
def test_read_rows_sliced(h5_with_table: Path) -> None:
    '''
    Test that read_rows() with start/stop returns only the sliced subset.
    '''
    with H5Client(h5_with_table, mode='r') as h5:
        rows = h5.read_rows('/items', start=1, stop=3)

    assert len(rows) == 2
    assert rows[0]['name'] == 'Beta'
    assert rows[1]['name'] == 'Gamma'

# ** test: read_rows_condition
def test_read_rows_condition(h5_with_table: Path) -> None:
    '''
    Test that read_rows() with a condition string filters correctly.
    '''
    with H5Client(h5_with_table, mode='r') as h5:
        rows = h5.read_rows('/items', condition='value > 1.5')

    assert len(rows) == 2
    names = {r['name'] for r in rows}
    assert names == {'Beta', 'Gamma'}

# ** test: query
def test_query(h5_with_table: Path) -> None:
    '''
    Test that query() returns only rows matching the condition string.
    '''
    with H5Client(h5_with_table, mode='r') as h5:
        rows = h5.query('/items', 'name == b"Alpha"')

    assert len(rows) == 1
    assert rows[0]['name'] == 'Alpha'

# ** test: iter_rows_matches_read_rows
def test_iter_rows_matches_read_rows(h5_with_table: Path) -> None:
    '''
    Test that iter_rows() yields the same dicts as read_rows(), one row at a time.
    '''
    assert not normalize_row.__name__.startswith('_')

    with H5Client(h5_with_table, mode='r') as h5:
        expected = h5.read_rows('/items')
        stream = h5.iter_rows('/items')

        assert isinstance(expected, list)
        assert isinstance(stream, Iterator)
        assert not isinstance(stream, list)

        # Consume one row before the rest to prove the source is lazy.
        first = next(stream)
        rest = []
        for row in stream:
            rest.append(row)

    assert len(expected) == 3
    assert [first, *rest] == expected

# ** test: iter_query_filters
def test_iter_query_filters(h5_with_table: Path) -> None:
    '''
    Test that iter_query() yields only rows matching the condition.
    '''
    with H5Client(h5_with_table, mode='r') as h5:
        rows = []
        for row in h5.iter_query('/items', 'value > 1.5'):
            rows.append(row)

    assert len(rows) == 2
    names = {row['name'] for row in rows}
    assert names == {'Beta', 'Gamma'}

# ** test: remove_rows
def test_remove_rows(h5_with_table: Path) -> None:
    '''
    Test that remove_rows() deletes matching rows and returns the count.
    '''
    with H5Client(h5_with_table, mode='a') as h5:
        removed = h5.remove_rows('/items', 'value < 2.5')

    assert removed == 2

    with H5Client(h5_with_table, mode='r') as h5:
        rows = h5.read_rows('/items')

    assert len(rows) == 1
    assert rows[0]['name'] == 'Gamma'

# ** test: create_and_get_array
def test_create_and_get_array(h5_path: Path) -> None:
    '''
    Test that create_array() stores data and get_array() retrieves it.
    '''
    data = np.array([1.0, 2.0, 3.0])
    with H5Client(h5_path, mode='w') as h5:
        h5.create_group('/measurements')
        h5.create_array('/measurements/temps', data, title='Temperatures')

    with H5Client(h5_path, mode='r') as h5:
        arr = h5.get_array('/measurements/temps')
        result = arr.read()

    np.testing.assert_array_equal(result, data)

# ** test: set_and_get_node_attr
def test_set_and_get_node_attr(h5_path: Path) -> None:
    '''
    Test that set_node_attr() stores a value and get_node_attr() returns it as a Python native.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_group('/catalog')
        h5.set_node_attr('/catalog', 'schema_ver', '1.0')

    with H5Client(h5_path, mode='r') as h5:
        val = h5.get_node_attr('/catalog', 'schema_ver')

    assert val == '1.0'
    assert isinstance(val, str)

# ** test: get_node_attrs_excludes_system_attrs
def test_get_node_attrs_excludes_system_attrs(h5_path: Path) -> None:
    '''
    Test that get_node_attrs() returns only user-defined attributes, excluding
    HDF5/PyTables system attributes such as CLASS, TITLE, and VERSION.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_group('/catalog', title='Catalog Group')
        h5.set_node_attr('/catalog', 'schema_ver', '1.0')
        h5.set_node_attr('/catalog', 'owner', 'test')

    with H5Client(h5_path, mode='r') as h5:
        attrs = h5.get_node_attrs('/catalog')

    assert 'schema_ver' in attrs
    assert 'owner' in attrs
    assert 'CLASS' not in attrs
    assert 'TITLE' not in attrs
    assert 'VERSION' not in attrs

# ** test: get_node_attrs_normalizes_numpy
def test_get_node_attrs_normalizes_numpy(h5_path: Path) -> None:
    '''
    Test that get_node_attrs() converts numpy scalar attribute values to Python natives.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_group('/data')
        node = h5.h5file.get_node('/data')
        node._v_attrs['count'] = np.int64(42)

    with H5Client(h5_path, mode='r') as h5:
        attrs = h5.get_node_attrs('/data')

    assert attrs['count'] == 42
    assert isinstance(attrs['count'], int)

# ** test: get_node_attr_not_found
def test_get_node_attr_not_found(existing_h5: Path) -> None:
    '''
    Test that get_group() raises H5_NODE_NOT_FOUND for a missing node.
    '''
    with H5Client(existing_h5, mode='r') as h5:
        with pytest.raises(ServiceError) as exc_info:
            h5.get_node_attrs('/missing')

    assert exc_info.value.error_code == H5_NODE_NOT_FOUND_ID
    assert isinstance(exc_info.value.__cause__, tables.NoSuchNodeError)

# ** test: flush_does_not_close
def test_flush_does_not_close(h5_path: Path) -> None:
    '''
    Test that flush() does not close the file handle.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.flush()
        assert h5.h5file is not None

# ** test: ensure_parent_groups_root
def test_ensure_parent_groups_root(h5_path: Path) -> None:
    '''
    Test that ensure_parent_groups('/') is a no-op and does not raise.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.ensure_parent_groups('/')

    assert not H5Client.ensure_parent_groups.__name__.startswith('_')
    assert H5_GROUP_CREATE_FAILED_ID == 'H5_GROUP_CREATE_FAILED'

# ** test: ensure_parent_groups_unopened
def test_ensure_parent_groups_unopened(h5_path: Path) -> None:
    '''
    Test that ensure_parent_groups() raises H5_CONN_NOT_INITIALIZED before open.
    '''
    client = H5Client(h5_path, mode='a')
    with pytest.raises(ServiceError) as exc_info:
        client.ensure_parent_groups('/a')

    assert exc_info.value.error_code == H5_CONN_NOT_INITIALIZED_ID

# ** test: create_table_auto_creates_parents
def test_create_table_auto_creates_parents(h5_path: Path) -> None:
    '''
    Test that create_table() creates missing intermediate groups, then the table.
    '''
    with H5Client(h5_path, mode='w') as h5:
        table = h5.create_table('/a/b/items', SampleTableObject.get_description())

        assert table is not None
        assert h5.node_exists('/a') is True
        assert h5.node_exists('/a/b') is True
        assert h5.node_exists('/a/b/items') is True

# ** test: ensure_parent_groups_failure_raises
def test_ensure_parent_groups_failure_raises(h5_path: Path, monkeypatch) -> None:
    '''
    Test that a PyTables failure inside parent-group creation raises
    H5_GROUP_CREATE_FAILED with the driver exception chained as the cause.
    '''
    with H5Client(h5_path, mode='w') as h5:

        # Force the next group create to fail at the driver.
        def fail_create(*args, **kwargs):
            raise tables.NodeError('create failed')

        monkeypatch.setattr(h5.h5file, 'create_group', fail_create)
        with pytest.raises(ServiceError) as exc_info:
            h5.ensure_parent_groups('/missing/parent')

    assert exc_info.value.error_code == H5_GROUP_CREATE_FAILED_ID
    assert exc_info.value.error_code == 'H5_GROUP_CREATE_FAILED'
    assert isinstance(exc_info.value.__cause__, tables.NodeError)

# ** test: index_method_signatures
def test_index_method_signatures() -> None:
    '''
    Test that H5Service and H5Client expose the column-index signatures.
    '''
    assert H5_INDEX_FAILED_ID == 'H5_INDEX_FAILED'

    for cls in (H5Service, H5Client):
        create_index = inspect.signature(cls.create_index)
        is_indexed = inspect.signature(cls.is_indexed)
        reindex = inspect.signature(cls.reindex)

        assert list(create_index.parameters) == ['self', 'path', 'column', 'kwargs']
        assert create_index.parameters['kwargs'].kind is inspect.Parameter.VAR_KEYWORD
        assert create_index.return_annotation is None

        assert list(is_indexed.parameters) == ['self', 'path', 'column']
        assert is_indexed.return_annotation is bool

        assert list(reindex.parameters) == ['self', 'path', 'column']
        assert reindex.parameters['column'].default is None
        assert reindex.return_annotation is None

# ** test: create_index_and_is_indexed
def test_create_index_and_is_indexed(h5_path: Path) -> None:
    '''
    Test that create_index() builds a CSI index and is_indexed() reports it.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_table('/items', SkuTableObject.get_description())
        h5.append_rows('/items', [{'sku': 'A-1', 'missing': 'x'}])

        assert h5.is_indexed('/items', 'sku') is False
        h5.create_index('/items', 'sku', filters=tables.Filters(complevel=1))
        assert h5.is_indexed('/items', 'sku') is True

        index = h5.get_table('/items').cols.sku.index
        assert index.kind == 'full'
        assert index.filters.complevel == 1

# ** test: create_index_failure_chains_cause
def test_create_index_failure_chains_cause(h5_path: Path) -> None:
    '''
    Test that a second create_index() raises H5_INDEX_FAILED and chains the cause.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_table('/items', SkuTableObject.get_description())
        h5.create_index('/items', 'sku')
        with pytest.raises(ServiceError) as exc_info:
            h5.create_index('/items', 'sku')

    assert exc_info.value.error_code == H5_INDEX_FAILED_ID
    assert exc_info.value.error_code == 'H5_INDEX_FAILED'
    assert exc_info.value.__cause__ is not None

# ** test: reindex_unindexed_column_raises
def test_reindex_unindexed_column_raises(h5_path: Path) -> None:
    '''
    Test that reindex() raises H5_INDEX_FAILED for a column that was never indexed.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_table('/items', SkuTableObject.get_description())
        with pytest.raises(ServiceError) as exc_info:
            h5.reindex('/items', 'missing')

    assert exc_info.value.error_code == H5_INDEX_FAILED_ID
    assert exc_info.value.error_code == 'H5_INDEX_FAILED'

# ** test: reindex_existing_columns
def test_reindex_existing_columns(h5_path: Path) -> None:
    '''
    Test that reindex() rebuilds a named index and, with no column, every indexed column.
    '''
    with H5Client(h5_path, mode='w') as h5:
        h5.create_table('/items', SkuTableObject.get_description())
        h5.append_rows('/items', [{'sku': 'A-1', 'missing': 'x'}])

        # No indexes yet: omitting the column recomputes an empty set.
        h5.reindex('/items')
        assert h5.is_indexed('/items', 'sku') is False

        h5.create_index('/items', 'sku')
        h5.append_rows('/items', [{'sku': 'B-2', 'missing': 'y'}])
        h5.reindex('/items', 'sku')
        h5.reindex('/items')

        assert h5.is_indexed('/items', 'sku') is True
        assert h5.is_indexed('/items', 'missing') is False

# ** test: append_rows_and_flush_do_not_reindex
def test_append_rows_and_flush_do_not_reindex(h5_path: Path, monkeypatch) -> None:
    '''
    Test that append_rows() and flush() do not call reindex().
    '''
    calls = []

    def record_reindex(*args, **kwargs):
        calls.append((args, kwargs))

    with H5Client(h5_path, mode='w') as h5:
        h5.create_table('/items', SkuTableObject.get_description())
        h5.create_index('/items', 'sku')
        monkeypatch.setattr(h5, 'reindex', record_reindex)
        h5.append_rows('/items', [{'sku': 'B-2', 'missing': 'y'}])
        h5.flush()

    assert calls == []
    assert 'reindex' not in inspect.getsource(H5Client.append_rows)
    assert 'reindex' not in inspect.getsource(H5Client.flush)

# ** test: index_missing_node_raises
def test_index_missing_node_raises(existing_h5: Path) -> None:
    '''
    Test that index operations raise H5_NODE_NOT_FOUND for a missing node.
    '''
    with H5Client(existing_h5, mode='a') as h5:
        for action in (
            lambda: h5.create_index('/missing', 'sku'),
            lambda: h5.is_indexed('/missing', 'sku'),
            lambda: h5.reindex('/missing', 'sku'),
        ):
            with pytest.raises(ServiceError) as exc_info:
                action()

            assert exc_info.value.error_code == H5_NODE_NOT_FOUND_ID

# ** test: index_unopened_raises
def test_index_unopened_raises(h5_path: Path) -> None:
    '''
    Test that index operations raise H5_CONN_NOT_INITIALIZED before open.
    '''
    client = H5Client(h5_path, mode='a')
    for action in (
        lambda: client.create_index('/items', 'sku'),
        lambda: client.is_indexed('/items', 'sku'),
        lambda: client.reindex('/items'),
    ):
        with pytest.raises(ServiceError) as exc_info:
            action()

        assert exc_info.value.error_code == H5_CONN_NOT_INITIALIZED_ID
