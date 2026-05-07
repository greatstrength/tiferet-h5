"""tiferet_h5 Domain H5 Tests"""

# *** imports

# ** infra
import pytest

# ** app
from ..h5 import H5Column, H5TableSchema, H5Node

# *** fixtures

# ** fixture: sample_column
@pytest.fixture
def sample_column() -> H5Column:
    '''
    A basic H5Column instance for testing.
    '''
    return H5Column(name='id', dtype='string256')


# ** fixture: sample_schema
@pytest.fixture
def sample_schema() -> H5TableSchema:
    '''
    An H5TableSchema with two columns for testing.
    '''
    return H5TableSchema(
        node_path='/features/calc',
        title='Calc Features',
        columns=[
            H5Column(name='id',   dtype='string256'),
            H5Column(name='name', dtype='string256'),
            H5Column(name='score', dtype='float64'),
        ],
    )


# *** tests

# ** test: h5_column_required_fields
def test_h5_column_required_fields() -> None:
    '''
    Test that H5Column constructs correctly with only required fields.
    '''
    col = H5Column(name='price', dtype='float64')

    assert col.name == 'price'
    assert col.dtype == 'float64'
    assert col.default is None
    assert col.position is None


# ** test: h5_column_with_default
def test_h5_column_with_default() -> None:
    '''
    Test that H5Column stores an explicit default value.
    '''
    col = H5Column(name='active', dtype='bool', default=True)

    assert col.default is True


# ** test: h5_column_with_position
def test_h5_column_with_position() -> None:
    '''
    Test that H5Column stores an explicit position.
    '''
    col = H5Column(name='id', dtype='string256', position=0)

    assert col.position == 0


# ** test: h5_table_schema_required_fields
def test_h5_table_schema_required_fields() -> None:
    '''
    Test that H5TableSchema constructs with only node_path.
    '''
    schema = H5TableSchema(node_path='/items')

    assert schema.node_path == '/items'
    assert schema.title is None
    assert schema.columns == []


# ** test: h5_table_schema_with_title_and_columns
def test_h5_table_schema_with_title_and_columns(sample_schema: H5TableSchema) -> None:
    '''
    Test that H5TableSchema stores title and columns correctly.
    '''
    assert sample_schema.node_path == '/features/calc'
    assert sample_schema.title == 'Calc Features'
    assert len(sample_schema.columns) == 3


# ** test: h5_table_schema_get_column_found
def test_h5_table_schema_get_column_found(sample_schema: H5TableSchema) -> None:
    '''
    Test that get_column returns the correct H5Column when the name exists.
    '''
    col = sample_schema.get_column('name')

    assert col is not None
    assert col.name == 'name'
    assert col.dtype == 'string256'


# ** test: h5_table_schema_get_column_not_found
def test_h5_table_schema_get_column_not_found(sample_schema: H5TableSchema) -> None:
    '''
    Test that get_column returns None when the column name does not exist.
    '''
    col = sample_schema.get_column('nonexistent')

    assert col is None


# ** test: h5_table_schema_column_names
def test_h5_table_schema_column_names(sample_schema: H5TableSchema) -> None:
    '''
    Test that column_names returns names in declaration order.
    '''
    names = sample_schema.column_names()

    assert names == ['id', 'name', 'score']


# ** test: h5_node_required_fields
def test_h5_node_required_fields() -> None:
    '''
    Test that H5Node constructs correctly with only required fields.
    '''
    node = H5Node(path='/features/calc', node_type='group')

    assert node.path == '/features/calc'
    assert node.node_type == 'group'
    assert node.title is None
    assert node.attrs == {}


# ** test: h5_node_with_title_and_attrs
def test_h5_node_with_title_and_attrs() -> None:
    '''
    Test that H5Node stores title and attrs snapshot correctly.
    '''
    node = H5Node(
        path='/features/calc/steps',
        node_type='table',
        title='Feature Steps',
        attrs={'schema_ver': '1.0'},
    )

    assert node.title == 'Feature Steps'
    assert node.attrs == {'schema_ver': '1.0'}


# ** test: h5_node_types
@pytest.mark.parametrize('node_type', ['group', 'table', 'array', 'leaf'])
def test_h5_node_types(node_type: str) -> None:
    '''
    Test that H5Node accepts all valid node type strings.
    '''
    node = H5Node(path='/some/path', node_type=node_type)

    assert node.node_type == node_type
