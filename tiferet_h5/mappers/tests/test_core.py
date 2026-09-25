"""tiferet_h5 Mapper Core Tests"""

# *** imports

# ** core
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

# ** infra
import numpy as np
import pytest
import tables
from pydantic import AliasChoices, Field

# ** app
from tiferet.domain import DomainObject
from tiferet.mappers import Aggregate

from ..core import NodeObject, TableObject
from .core import NodeObjectTestBase, TableObjectTestBase

# *** constants

# ** constant: sample_name
SAMPLE_NAME = 'Widget'

# ** constant: sample_score
SAMPLE_SCORE = 3.14

# *** classes

# ** class: item_table_object
class ItemTableObject(TableObject):
    '''Minimal TableObject subclass for testing.'''

    # * attribute: name
    name: str = Field(default='', description='Item name.')

    # * attribute: score
    score: float = Field(default=0.0, description='Item score.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name':  tables.StringCol(64),
        'score': tables.Float64Col(),
    }

# ** class: aliased_table_object
class AliasedTableObject(TableObject):
    '''TableObject subclass with field/column aliasing for testing.'''

    # * attribute: group_id
    group_id: str = Field(
        default='',
        serialization_alias='grp',
        validation_alias=AliasChoices('grp', 'group_id'),
        description='Group identifier; stored as "grp" in HDF5.',
    )

    # * attribute: label
    label: str = Field(default='', description='Label.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'grp':   tables.StringCol(64),
        'label': tables.StringCol(128),
    }

# ** class: item_aggregate
class ItemAggregate(Aggregate):
    '''Minimal Aggregate for map() testing.'''

    # * attribute: name
    name: str = Field(default='', description='Item name.')

    # * attribute: score
    score: float = Field(default=0.0, description='Item score.')

# ** class: item_domain
class ItemDomain(DomainObject):
    '''Minimal DomainObject for from_model() testing.'''

    # * attribute: name
    name: str = Field(default='', description='Item name.')

    # * attribute: score
    score: float = Field(default=0.0, description='Item score.')

# ** class: meta_node_object
class MetaNodeObject(NodeObject):
    '''NodeObject subclass with aliased field for testing.'''

    # * attribute: name
    name: str = Field(default='', description='Name.')

    # * attribute: description
    description: str = Field(
        default='',
        serialization_alias='desc',
        validation_alias=AliasChoices('desc', 'description'),
        description='Description; stored as "desc" in HDF5.',
    )

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }

# ** class: nullable_note_table_object
class NullableNoteTableObject(TableObject):
    '''
    TableObject with one declared nullable string and one ordinary string.

    ``note`` defaults to ``''`` so a dropped ``None`` is visible as an empty
    string rather than a silent default of ``None``.
    '''

    # * attribute: name
    name: str = Field(default='', description='Item name.')

    # * attribute: note
    note: Optional[str] = Field(default='', description='Optional note.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name': tables.StringCol(64),
        'note': tables.StringCol(128),
    }

    # * attribute: _NULLABLE_FIELDS
    _NULLABLE_FIELDS: ClassVar[List[str]] = [
        'note',
    ]

# ** class: aliased_nullable_table_object
class AliasedNullableTableObject(TableObject):
    '''
    TableObject whose nullable field is stored under a serialization alias.
    '''

    # * attribute: service_id
    service_id: Optional[str] = Field(
        default='',
        serialization_alias='svc',
        validation_alias=AliasChoices('svc', 'service_id'),
        description='Optional service id; stored as "svc".',
    )

    # * attribute: label
    label: str = Field(default='', description='Label.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'svc': tables.StringCol(64),
        'label': tables.StringCol(64),
    }

    # * attribute: _NULLABLE_FIELDS
    _NULLABLE_FIELDS: ClassVar[List[str]] = [
        'service_id',
    ]

# ** class: nullable_note_domain
class NullableNoteDomain(DomainObject):
    '''
    Domain object for nullable mapper ``from_model`` tests.
    '''

    # * attribute: name
    name: str = Field(default='', description='Item name.')

    # * attribute: note
    note: Optional[str] = Field(default='', description='Optional note.')

# ** class: nullable_note_node_object
class NullableNoteNodeObject(NodeObject):
    '''
    NodeObject with one declared nullable string.  The attrs role excludes None.
    '''

    # * attribute: name
    name: str = Field(default='', description='Name.')

    # * attribute: note
    note: Optional[str] = Field(default='', description='Optional note.')

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }

    # * attribute: _NULLABLE_FIELDS
    _NULLABLE_FIELDS: ClassVar[List[str]] = [
        'note',
    ]

# ** class: aliased_nullable_node_object
class AliasedNullableNodeObject(NodeObject):
    '''
    NodeObject whose nullable field is stored under a serialization alias.
    '''

    # * attribute: service_id
    service_id: Optional[str] = Field(
        default='',
        serialization_alias='svc',
        validation_alias=AliasChoices('svc', 'service_id'),
        description='Optional service id; stored as "svc".',
    )

    # * attribute: label
    label: str = Field(default='', description='Label.')

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }

    # * attribute: _NULLABLE_FIELDS
    _NULLABLE_FIELDS: ClassVar[List[str]] = [
        'service_id',
    ]

# *** fixtures

# ** fixture: h5_table
@pytest.fixture
def h5_table(tmp_path: Path):
    '''
    Open a temporary HDF5 file and yield a live table for row I/O tests.
    Closes the file after the test.
    '''
    h5_path = tmp_path / 'test.h5'
    h5file = tables.open_file(str(h5_path), mode='w')
    table = h5file.create_table('/', 'items', ItemTableObject.get_description())
    yield table
    h5file.close()

# ** fixture: aliased_h5_table
@pytest.fixture
def aliased_h5_table(tmp_path: Path):
    '''
    Open a temporary HDF5 file and yield a live aliased table for alias tests.
    '''
    h5_path = tmp_path / 'aliased.h5'
    h5file = tables.open_file(str(h5_path), mode='w')
    table = h5file.create_table('/', 'items', AliasedTableObject.get_description())
    yield table
    h5file.close()

# ** fixture: nullable_h5_table
@pytest.fixture
def nullable_h5_table(tmp_path: Path):
    '''
    Open a temporary HDF5 file and yield a live nullable-note table.
    '''
    h5_path = tmp_path / 'nullable.h5'
    h5file = tables.open_file(str(h5_path), mode='w')
    table = h5file.create_table('/', 'items', NullableNoteTableObject.get_description())
    yield table
    h5file.close()

# ** fixture: aliased_nullable_h5_table
@pytest.fixture
def aliased_nullable_h5_table(tmp_path: Path):
    '''
    Open a temporary HDF5 file and yield a live aliased nullable table.
    '''
    h5_path = tmp_path / 'aliased-nullable.h5'
    h5file = tables.open_file(str(h5_path), mode='w')
    table = h5file.create_table('/', 'items', AliasedNullableTableObject.get_description())
    yield table
    h5file.close()

# *** tests

# ** test: get_description_auto_generates
def test_get_description_auto_generates() -> None:
    '''
    Test that get_description() auto-generates an IsDescription subclass from _H5_TYPES.
    '''
    # Reset cached description so we test generation, not caching.
    ItemTableObject._DESCRIPTION = None

    desc = ItemTableObject.get_description()

    assert issubclass(desc, tables.IsDescription)
    assert 'name' in desc.columns
    assert 'score' in desc.columns

# ** test: get_description_cached
def test_get_description_cached() -> None:
    '''
    Test that get_description() returns the same class on subsequent calls.
    '''
    first  = ItemTableObject.get_description()
    second = ItemTableObject.get_description()

    assert first is second

# ** test: get_description_requires_h5_types
def test_get_description_requires_h5_types() -> None:
    '''
    Test that get_description() raises ValueError when _H5_TYPES is empty.
    '''
    class EmptyTableObject(TableObject):
        _H5_TYPES: ClassVar[Dict[str, Any]] = {}
        _DESCRIPTION: ClassVar[Optional[type]] = None

    with pytest.raises(ValueError, match='must define _H5_TYPES or _DESCRIPTION'):
        EmptyTableObject.get_description()

# ** test: normalize_value_bytes
def test_normalize_value_bytes() -> None:
    '''
    Test that normalize_value decodes bytes to str.
    '''
    result = TableObject.normalize_value(b'hello')

    assert result == 'hello'
    assert isinstance(result, str)

# ** test: normalize_value_numpy_scalar
def test_normalize_value_numpy_scalar() -> None:
    '''
    Test that normalize_value converts a numpy scalar to a Python native.
    '''
    result = TableObject.normalize_value(np.float64(3.14))

    assert isinstance(result, float)
    assert abs(result - 3.14) < 1e-9

# ** test: normalize_value_python_native
def test_normalize_value_python_native() -> None:
    '''
    Test that normalize_value passes through plain Python types unchanged.
    '''
    assert TableObject.normalize_value('hello') == 'hello'
    assert TableObject.normalize_value(42) == 42
    assert TableObject.normalize_value(True) is True

# ** test: encode_value_str_to_bytes_for_string_col
def test_encode_value_str_to_bytes_for_string_col() -> None:
    '''
    Test that encode_value encodes str to bytes for a StringCol column.
    '''
    col = tables.StringCol(64)
    result = TableObject.encode_value('hello', col)

    assert result == b'hello'

# ** test: encode_value_none_string_col
def test_encode_value_none_string_col() -> None:
    '''
    Test that encode_value substitutes b'' for None on a StringCol.
    '''
    col = tables.StringCol(64)
    result = TableObject.encode_value(None, col)

    assert result == b''

# ** test: encode_value_none_bool_col
def test_encode_value_none_bool_col() -> None:
    '''
    Test that encode_value substitutes False for None on a BoolCol.
    '''
    col = tables.BoolCol()
    result = TableObject.encode_value(None, col)

    assert result is False

# ** test: encode_value_none_numeric_col
def test_encode_value_none_numeric_col() -> None:
    '''
    Test that encode_value substitutes 0 for None on a numeric column.
    '''
    col = tables.Float64Col()
    result = TableObject.encode_value(None, col)

    assert result == 0

# ** test: to_row_from_row_round_trip
def test_to_row_from_row_round_trip(h5_table) -> None:
    '''
    Test that to_row() followed by from_row() preserves field values.
    '''
    obj = ItemTableObject(name=SAMPLE_NAME, score=SAMPLE_SCORE)
    obj.to_row(h5_table)
    h5_table.flush()

    rows = list(h5_table.iterrows())
    assert len(rows) == 1

    restored = ItemTableObject.from_row(rows[0])

    assert restored.name == SAMPLE_NAME
    assert abs(restored.score - SAMPLE_SCORE) < 1e-9

# ** test: to_row_alias_applied_to_column
def test_to_row_alias_applied_to_column(aliased_h5_table) -> None:
    '''
    Test that to_row() writes to the alias column name, not the Python field name.
    '''
    obj = AliasedTableObject(group_id='calc', label='add')
    obj.to_row(aliased_h5_table)
    aliased_h5_table.flush()

    rows = list(aliased_h5_table.iterrows())
    assert rows[0]['grp'] == b'calc'

# ** test: from_row_resolves_alias
def test_from_row_resolves_alias(aliased_h5_table) -> None:
    '''
    Test that from_row() resolves alias column names back to Python field names.
    '''
    AliasedTableObject(group_id='calc', label='add').to_row(aliased_h5_table)
    aliased_h5_table.flush()

    rows = [{'grp': r['grp'], 'label': r['label']} for r in aliased_h5_table.iterrows()]
    restored = AliasedTableObject.from_row(rows[0])

    assert restored.group_id == 'calc'
    assert restored.label == 'add'

# ** test: to_primitive_uses_canonical_names
def test_to_primitive_uses_canonical_names() -> None:
    '''
    Test that to_primitive() returns canonical field names (not aliases).
    '''
    obj = ItemTableObject(name=SAMPLE_NAME, score=SAMPLE_SCORE)
    data = obj.to_primitive()

    assert 'name' in data
    assert 'score' in data
    assert data['name'] == SAMPLE_NAME

# ** test: map_produces_aggregate
def test_map_produces_aggregate() -> None:
    '''
    Test that map() constructs the target Aggregate with matching field values.
    '''
    obj = ItemTableObject(name=SAMPLE_NAME, score=SAMPLE_SCORE)
    agg = obj.map(ItemAggregate)

    assert isinstance(agg, ItemAggregate)
    assert agg.name == SAMPLE_NAME
    assert abs(agg.score - SAMPLE_SCORE) < 1e-9

# ** test: from_model_creates_table_object
def test_from_model_creates_table_object() -> None:
    '''
    Test that from_model() creates a TableObject from a DomainObject.
    '''
    domain_obj = ItemDomain(name=SAMPLE_NAME, score=SAMPLE_SCORE)
    table_obj = ItemTableObject.from_model(domain_obj)

    assert isinstance(table_obj, ItemTableObject)
    assert table_obj.name == SAMPLE_NAME
    assert abs(table_obj.score - SAMPLE_SCORE) < 1e-9

# ** test: verify_schema_pass
def test_verify_schema_pass(h5_table) -> None:
    '''
    Test that verify_schema() returns an empty list when columns match.
    '''
    mismatches = ItemTableObject.verify_schema(h5_table)

    assert mismatches == []

# ** test: verify_schema_fail
def test_verify_schema_fail(h5_table) -> None:
    '''
    Test that verify_schema() reports columns declared in _H5_TYPES but absent in the table.
    '''
    class ExtraColObject(TableObject):
        name: str = Field(default='')
        score: float = Field(default=0.0)
        missing: str = Field(default='')
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name':    tables.StringCol(64),
            'score':   tables.Float64Col(),
            'missing': tables.StringCol(64),
        }

    mismatches = ExtraColObject.verify_schema(h5_table)

    assert len(mismatches) == 1
    assert 'missing' in mismatches[0]
    assert 'declared in _H5_TYPES' in mismatches[0]

# ** test: verify_schema_extra_column
def test_verify_schema_extra_column(h5_table) -> None:
    '''
    Test that verify_schema() reports a live column absent from _H5_TYPES.
    '''
    class MissingScoreObject(TableObject):
        name: str = Field(default='')
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name': tables.StringCol(64),
        }

    mismatches = MissingScoreObject.verify_schema(h5_table)

    assert len(mismatches) == 1
    assert 'score' in mismatches[0]
    assert 'not declared in _H5_TYPES' in mismatches[0]

# ** test: verify_schema_type_mismatch
def test_verify_schema_type_mismatch(h5_table) -> None:
    '''
    Test that verify_schema() reports a PyTables type mismatch and does not raise.
    '''
    class WrongTypeObject(TableObject):
        name: str = Field(default='')
        score: int = Field(default=0)
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name':  tables.StringCol(64),
            'score': tables.Int32Col(),
        }

    mismatches = WrongTypeObject.verify_schema(h5_table)

    assert len(mismatches) == 1
    assert 'score' in mismatches[0]
    assert 'type mismatch' in mismatches[0]

# ** test: verify_schema_string_itemsize_mismatch
def test_verify_schema_string_itemsize_mismatch(h5_table) -> None:
    '''
    Test that verify_schema() reports a StringCol itemsize mismatch.
    '''
    class NarrowNameObject(TableObject):
        name: str = Field(default='')
        score: float = Field(default=0.0)
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name':  tables.StringCol(16),
            'score': tables.Float64Col(),
        }

    mismatches = NarrowNameObject.verify_schema(h5_table)

    assert len(mismatches) == 1
    assert 'name' in mismatches[0]
    assert 'itemsize mismatch' in mismatches[0]

# ** test: node_object_to_attrs_applies_alias
def test_node_object_to_attrs_applies_alias() -> None:
    '''
    Test that NodeObject.to_attrs() uses serialization_alias as the attribute key.
    '''
    obj = MetaNodeObject(name='Calculator', description='Arithmetic ops')
    attrs = obj.to_attrs()

    assert 'desc' in attrs
    assert 'description' not in attrs
    assert attrs['desc'] == 'Arithmetic ops'
    assert attrs['name'] == 'Calculator'

# ** test: node_object_from_attrs_resolves_alias
def test_node_object_from_attrs_resolves_alias() -> None:
    '''
    Test that NodeObject.from_attrs() maps alias keys back to Python field names.
    '''
    raw = {'name': 'Calculator', 'desc': 'Arithmetic ops'}
    obj = MetaNodeObject.from_attrs(raw)

    assert obj.name == 'Calculator'
    assert obj.description == 'Arithmetic ops'

# ** test: node_object_from_attrs_decodes_bytes
def test_node_object_from_attrs_decodes_bytes() -> None:
    '''
    Test that NodeObject.from_attrs() decodes bytes values to str.
    '''
    raw = {'name': b'Calculator', 'desc': b'Arithmetic ops'}
    obj = MetaNodeObject.from_attrs(raw)

    assert obj.name == 'Calculator'
    assert obj.description == 'Arithmetic ops'

# ** test: node_object_round_trip
def test_node_object_round_trip() -> None:
    '''
    Test that to_attrs() followed by from_attrs() preserves all field values.
    '''
    original = MetaNodeObject(name='Calculator', description='Arithmetic ops')
    attrs = original.to_attrs()
    restored = MetaNodeObject.from_attrs(attrs)

    assert restored.name == original.name
    assert restored.description == original.description

# ** test: nullable_row_round_trip
def test_nullable_row_round_trip(nullable_h5_table) -> None:
    '''
    Test that a declared nullable string round-trips None, and an undeclared
    empty string on the same row stays empty.
    '''
    NullableNoteTableObject(name='', note=None).to_row(nullable_h5_table)
    nullable_h5_table.flush()

    row = list(nullable_h5_table.iterrows())[0]
    restored = NullableNoteTableObject.from_row(row)

    assert row['note'] == b''
    assert restored.note is None
    assert restored.name == ''

# ** test: nullable_empty_string_reads_as_none
def test_nullable_empty_string_reads_as_none(nullable_h5_table) -> None:
    '''
    Test that a declared field stored as '' reads back as None.
    '''
    row = nullable_h5_table.row
    row['name'] = b'Widget'
    row['note'] = b''
    row.append()
    nullable_h5_table.flush()

    restored = NullableNoteTableObject.from_row(list(nullable_h5_table.iterrows())[0])

    assert restored.note is None
    assert restored.name == 'Widget'

# ** test: undeclared_empty_string_stays_empty
def test_undeclared_empty_string_stays_empty(h5_table) -> None:
    '''
    Test that a class with the default empty list still reads a stored '' as ''.
    '''
    row = h5_table.row
    row['name'] = b''
    row['score'] = 0
    row.append()
    h5_table.flush()

    restored = ItemTableObject.from_row(list(h5_table.iterrows())[0])

    assert restored.name == ''
    assert TableObject._NULLABLE_FIELDS == []
    assert NodeObject._NULLABLE_FIELDS == []
    assert ItemTableObject._NULLABLE_FIELDS == []

# ** test: nullable_aliased_row_round_trip
def test_nullable_aliased_row_round_trip(aliased_nullable_h5_table) -> None:
    '''
    Test that a nullable field listed by its Python name still round-trips None
    when the HDF5 column is the serialization alias.
    '''
    AliasedNullableTableObject(service_id=None, label='').to_row(aliased_nullable_h5_table)
    aliased_nullable_h5_table.flush()

    row = list(aliased_nullable_h5_table.iterrows())[0]
    restored = AliasedNullableTableObject.from_row(row)

    assert row['svc'] == b''
    assert restored.service_id is None
    assert restored.label == ''

# ** test: from_model_preserves_nullable_none
def test_from_model_preserves_nullable_none() -> None:
    '''
    Test that from_model keeps a declared None instead of the string default.
    '''
    table_obj = NullableNoteTableObject.from_model(NullableNoteDomain(name='Widget', note=None))
    node_obj = NullableNoteNodeObject.from_model(NullableNoteDomain(name='Widget', note=None))

    assert table_obj.note is None
    assert table_obj.to_primitive()['note'] is None
    assert node_obj.note is None
    assert node_obj.to_primitive()['note'] is None

# ** test: nullable_attrs_round_trip
def test_nullable_attrs_round_trip() -> None:
    '''
    Test that to_attrs emits the empty sentinel for a declared None even when
    the role sets exclude_none, and from_attrs restores None.
    '''
    attrs = NullableNoteNodeObject(name='Widget', note=None).to_attrs()
    restored = NullableNoteNodeObject.from_attrs(attrs)

    assert attrs['note'] == ''
    assert attrs['name'] == 'Widget'
    assert restored.note is None
    assert restored.name == 'Widget'

# ** test: nullable_attrs_empty_string_reads_as_none
def test_nullable_attrs_empty_string_reads_as_none() -> None:
    '''
    Test that a declared attribute stored as '' or b'' reads back as None.
    '''
    restored = NullableNoteNodeObject.from_attrs({'name': 'Widget', 'note': ''})
    restored_bytes = NullableNoteNodeObject.from_attrs({'name': b'Widget', 'note': b''})

    assert restored.note is None
    assert restored_bytes.note is None
    assert restored.name == 'Widget'

# ** test: nullable_aliased_attrs_round_trip
def test_nullable_aliased_attrs_round_trip() -> None:
    '''
    Test that a nullable field listed by its Python name round-trips None
    when the attribute key is the serialization alias.
    '''
    attrs = AliasedNullableNodeObject(service_id=None, label='').to_attrs()
    restored = AliasedNullableNodeObject.from_attrs(attrs)

    assert attrs['svc'] == ''
    assert 'service_id' not in attrs
    assert restored.service_id is None
    assert restored.label == ''

# ** test: nullable_attrs_honors_explicit_exclude
def test_nullable_attrs_honors_explicit_exclude() -> None:
    '''
    Test that an explicit role exclude still omits a nullable field.
    exclude_none must not drop it; exclude must.
    '''
    class ExcludedNoteNode(NullableNoteNodeObject):
        '''NodeObject that excludes the nullable note from attribute output.'''

        # * attribute: _ROLES
        _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
            'to_h5.attrs': {
                'by_alias': True,
                'exclude_none': True,
                'exclude': {'note'},
            },
        }

    attrs = ExcludedNoteNode(name='Widget', note=None).to_attrs()

    assert 'note' not in attrs
    assert attrs['name'] == 'Widget'

# ** test: test_harness_item_table
class TestHarnessItemTable(TableObjectTestBase):
    '''
    Proves TableObjectTestBase collects tests from class variables alone.
    '''

    # * attribute: table_cls
    table_cls = ItemTableObject

    # * attribute: sample_data
    sample_data = {'name': SAMPLE_NAME, 'score': SAMPLE_SCORE}

    # * attribute: equality_fields
    equality_fields = ['name', 'score']

# ** test: test_harness_item_table_mapped
class TestHarnessItemTableMapped(TableObjectTestBase):
    '''
    Proves map and from_model run when their optional classes are set.
    '''

    # * attribute: table_cls
    table_cls = ItemTableObject

    # * attribute: aggregate_cls
    aggregate_cls = ItemAggregate

    # * attribute: domain_cls
    domain_cls = ItemDomain

    # * attribute: sample_data
    sample_data = {'name': SAMPLE_NAME, 'score': SAMPLE_SCORE}

    # * attribute: aggregate_sample_data
    aggregate_sample_data = {'name': SAMPLE_NAME, 'score': SAMPLE_SCORE}

    # * attribute: equality_fields
    equality_fields = ['name', 'score']

# ** test: test_harness_meta_node
class TestHarnessMetaNode(NodeObjectTestBase):
    '''
    Proves NodeObjectTestBase collects attribute round-trip tests.
    '''

    # * attribute: node_cls
    node_cls = MetaNodeObject

    # * attribute: sample_data
    sample_data = {'name': 'Calculator', 'description': 'Arithmetic ops'}

    # * attribute: equality_fields
    equality_fields = ['name', 'description']
