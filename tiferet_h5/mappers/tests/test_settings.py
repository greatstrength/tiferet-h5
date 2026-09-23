"""tiferet_h5 Mapper Settings Tests"""

# *** imports

# ** core
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

# ** infra
import numpy as np
import pytest
import tables
from pydantic import AliasChoices, Field, ValidationError

# ** app
from tiferet.domain import DomainObject
from tiferet.mappers import Aggregate

from ..settings import NodeObject, TableObject
from .settings import NodeObjectTestBase, TableObjectTestBase

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


# ** class: meta_aggregate
class MetaAggregate(Aggregate):
    '''Minimal Aggregate for MetaNodeObject map()/from_model() testing.'''

    # * attribute: name
    name: str = Field(default='', description='Name.')

    # * attribute: description
    description: str = Field(default='', description='Description.')


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
        'svc':   tables.StringCol(64),
        'label': tables.StringCol(64),
    }

    # * attribute: _NULLABLE_FIELDS
    _NULLABLE_FIELDS: ClassVar[List[str]] = [
        'service_id',
    ]

# ** class: optional_name_table_object
class OptionalNameTableObject(TableObject):
    '''
    TableObject that accepts None without declaring ``_NULLABLE_FIELDS``.
    '''

    # * attribute: name
    name: Optional[str] = Field(default='', description='Name.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'name': tables.StringCol(64),
    }

# ** class: nullable_note_domain
class NullableNoteDomain(DomainObject):
    '''
    Domain object for nullable mapper ``from_model`` tests.
    '''

    # * attribute: name
    name: str = Field(default='', description='Item name.')

    # * attribute: note
    note: Optional[str] = Field(default='', description='Optional note.')

# ** class: nullable_note_aggregate
class NullableNoteAggregate(Aggregate):
    '''
    Aggregate for nullable mapper ``map`` tests.

    ``note`` defaults to ``''`` so a dropped ``None`` fails an ``is None`` check.
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

# ** class: optional_note_node_object
class OptionalNoteNodeObject(NodeObject):
    '''
    NodeObject that accepts None without declaring ``_NULLABLE_FIELDS``.
    '''

    # * attribute: name
    name: str = Field(default='', description='Name.')

    # * attribute: note
    note: Optional[str] = Field(default='', description='Note.')

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }

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

# ** fixture: optional_name_h5_table
@pytest.fixture
def optional_name_h5_table(tmp_path: Path):
    '''
    Open a temporary HDF5 file and yield a table with no nullable fields.
    '''
    h5_path = tmp_path / 'optional-name.h5'
    h5file = tables.open_file(str(h5_path), mode='w')
    table = h5file.create_table('/', 'items', OptionalNameTableObject.get_description())
    yield table
    h5file.close()

# *** tests

# ** test: TestItemTableObject
class TestItemTableObject(TableObjectTestBase):
    '''
    Harness-driven tests for ItemTableObject.
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


# ** test: TestMetaNodeObject
class TestMetaNodeObject(NodeObjectTestBase):
    '''
    Harness-driven tests for MetaNodeObject.
    '''

    # * attribute: node_cls
    node_cls = MetaNodeObject

    # * attribute: aggregate_cls
    aggregate_cls = MetaAggregate

    # * attribute: sample_data
    sample_data = {'name': 'Calculator', 'description': 'Arithmetic ops'}

    # * attribute: aggregate_sample_data
    aggregate_sample_data = {'name': 'Calculator', 'description': 'Arithmetic ops'}

    # * attribute: equality_fields
    equality_fields = ['name', 'description']


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


# ** test: verify_schema_missing_column
def test_verify_schema_missing_column(h5_table) -> None:
    '''
    Test that verify_schema() reports a column declared in _H5_TYPES but absent in the table.
    '''
    class MissingColObject(TableObject):
        name: str = Field(default='')
        score: float = Field(default=0.0)
        missing: str = Field(default='')
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name':    tables.StringCol(64),
            'score':   tables.Float64Col(),
            'missing': tables.StringCol(64),
        }

    mismatches = MissingColObject.verify_schema(h5_table)

    assert len(mismatches) == 1
    assert 'missing' in mismatches[0]
    assert 'declared in _H5_TYPES' in mismatches[0]

# ** test: verify_schema_extra_column
def test_verify_schema_extra_column(h5_table) -> None:
    '''
    Test that verify_schema() reports a column present in the table but no
    longer declared in _H5_TYPES (schema drift in the opposite direction from
    a missing column).
    '''
    class UndeclaresScoreObject(TableObject):
        name: str = Field(default='')
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name': tables.StringCol(64),
        }

    mismatches = UndeclaresScoreObject.verify_schema(h5_table)

    assert len(mismatches) == 1
    assert 'score' in mismatches[0]
    assert 'not declared in _H5_TYPES' in mismatches[0]

# ** test: verify_schema_type_mismatch
def test_verify_schema_type_mismatch(h5_table) -> None:
    '''
    Test that verify_schema() reports a PyTables type mismatch for a column
    declared with a different type than the one actually present in the table.
    '''
    class WrongTypeObject(TableObject):
        name: str = Field(default='')
        score: int = Field(default=0)
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name':  tables.StringCol(64),
            'score': tables.Int32Col(),  # actual column is Float64Col
        }

    mismatches = WrongTypeObject.verify_schema(h5_table)

    assert len(mismatches) == 1
    assert 'score' in mismatches[0]
    assert 'type mismatch' in mismatches[0]

# ** test: verify_schema_string_width_mismatch
def test_verify_schema_string_width_mismatch(h5_table) -> None:
    '''
    Test that verify_schema() reports a StringCol width mismatch, which the
    PyTables "string" type identifier alone does not distinguish.
    '''
    class NarrowNameObject(TableObject):
        name: str = Field(default='')
        score: float = Field(default=0.0)
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name':  tables.StringCol(16),  # actual column is StringCol(64)
            'score': tables.Float64Col(),
        }

    mismatches = NarrowNameObject.verify_schema(h5_table)

    assert len(mismatches) == 1
    assert 'name' in mismatches[0]
    assert 'width mismatch' in mismatches[0]

# ** test: schema_fingerprint_deterministic
def test_schema_fingerprint_deterministic() -> None:
    '''
    Test that schema_fingerprint() returns the same value across repeated calls
    and is unaffected by _H5_TYPES declaration order.
    '''
    class OrderAObject(TableObject):
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name':  tables.StringCol(64),
            'score': tables.Float64Col(),
        }

    class OrderBObject(TableObject):
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'score': tables.Float64Col(),
            'name':  tables.StringCol(64),
        }

    assert OrderAObject.schema_fingerprint() == OrderAObject.schema_fingerprint()
    assert OrderAObject.schema_fingerprint() == OrderBObject.schema_fingerprint()

# ** test: schema_fingerprint_changes_with_schema
def test_schema_fingerprint_changes_with_schema() -> None:
    '''
    Test that schema_fingerprint() changes when a column's declared width changes.
    '''
    class NarrowObject(TableObject):
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name': tables.StringCol(16),
        }

    class WideObject(TableObject):
        _H5_TYPES: ClassVar[Dict[str, Any]] = {
            'name': tables.StringCol(64),
        }

    assert NarrowObject.schema_fingerprint() != WideObject.schema_fingerprint()

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


# ** test: node_object_coerces_numeric_str_field
def test_node_object_coerces_numeric_str_field() -> None:
    '''
    Test that NodeObject, which does not override TransferObject's
    model_config, inherits the coerce_numbers_to_str=True default and
    silently coerces a numeric value assigned to a str field.
    '''
    obj = MetaNodeObject(name=42, description='Arithmetic ops')

    assert obj.name == '42'
    assert isinstance(obj.name, str)

# ** test: table_object_rejects_numeric_str_field
def test_table_object_rejects_numeric_str_field() -> None:
    '''
    Test that TableObject's explicit coerce_numbers_to_str=False override
    still rejects a numeric value assigned to a str field, in contrast to
    NodeObject/plain DomainObject subclasses that inherit the new default.
    '''
    with pytest.raises(ValidationError):
        ItemTableObject(name=42, score=SAMPLE_SCORE)

# ** test: table_nullable_field_round_trips_none
def test_table_nullable_field_round_trips_none(nullable_h5_table) -> None:
    '''
    Test that a declared nullable string round-trips None, and an undeclared
    empty string on the same row stays empty.
    '''
    NullableNoteTableObject(name='', note=None).to_row(nullable_h5_table)
    nullable_h5_table.flush()

    restored = NullableNoteTableObject.from_row(list(nullable_h5_table.iterrows())[0])

    assert restored.note is None
    assert restored.name == ''

# ** test: table_aliased_nullable_field_round_trips_none
def test_table_aliased_nullable_field_round_trips_none(aliased_nullable_h5_table) -> None:
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

# ** test: table_undeclared_none_reads_back_as_empty_string
def test_table_undeclared_none_reads_back_as_empty_string(optional_name_h5_table) -> None:
    '''
    Test that a class which does not set _NULLABLE_FIELDS still encodes None
    as b'' and reads it back as ''.
    '''
    OptionalNameTableObject(name=None).to_row(optional_name_h5_table)
    optional_name_h5_table.flush()

    restored = OptionalNameTableObject.from_row(list(optional_name_h5_table.iterrows())[0])

    assert restored.name == ''
    assert OptionalNameTableObject._NULLABLE_FIELDS == []

# ** test: table_declared_empty_string_collapses_to_none_on_read
def test_table_declared_empty_string_collapses_to_none_on_read(nullable_h5_table) -> None:
    '''
    Test that a declared field stored as '' reads back as None, and that
    from_model keeps a genuine empty string until it crosses storage.
    '''
    kept = NullableNoteTableObject.from_model(NullableNoteDomain(name='Widget', note=''))
    kept.to_row(nullable_h5_table)
    nullable_h5_table.flush()

    restored = NullableNoteTableObject.from_row(list(nullable_h5_table.iterrows())[0])

    assert kept.note == ''
    assert restored.note is None

# ** test: table_from_model_storage_map_preserves_none
def test_table_from_model_storage_map_preserves_none(nullable_h5_table) -> None:
    '''
    Test that from_model -> to_row -> from_row -> map keeps None for a
    declared field instead of substituting the string default.
    '''
    table_obj = NullableNoteTableObject.from_model(NullableNoteDomain(name='Widget', note=None))
    table_obj.to_row(nullable_h5_table)
    nullable_h5_table.flush()

    restored = NullableNoteTableObject.from_row(list(nullable_h5_table.iterrows())[0])
    mapped = restored.map(NullableNoteAggregate)

    assert table_obj.note is None
    assert table_obj.to_primitive()['note'] is None
    assert restored.note is None
    assert mapped.note is None

# ** test: node_nullable_field_round_trips_none
def test_node_nullable_field_round_trips_none() -> None:
    '''
    Test that to_attrs emits the empty sentinel for a declared None even when
    the role sets exclude_none, and from_attrs restores None from bytes.
    '''
    attrs = NullableNoteNodeObject(name='Widget', note=None).to_attrs()
    raw = {
        key: value.encode('utf-8') if isinstance(value, str) else value
        for key, value in attrs.items()
    }
    restored = NullableNoteNodeObject.from_attrs(raw)

    assert attrs['note'] == ''
    assert attrs['name'] == 'Widget'
    assert restored.note is None
    assert restored.name == 'Widget'

# ** test: node_aliased_nullable_field_round_trips_none
def test_node_aliased_nullable_field_round_trips_none() -> None:
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

# ** test: node_undeclared_empty_string_stays_empty
def test_node_undeclared_empty_string_stays_empty() -> None:
    '''
    Test that a class which does not set _NULLABLE_FIELDS still drops None
    under exclude_none and reads a stored empty string as ''.
    '''
    attrs = OptionalNoteNodeObject(name='Widget', note=None).to_attrs()
    restored = OptionalNoteNodeObject.from_attrs({'name': 'Widget', 'note': ''})

    assert 'note' not in attrs
    assert restored.note == ''
    assert OptionalNoteNodeObject._NULLABLE_FIELDS == []

# ** test: node_from_model_attrs_map_preserves_none
def test_node_from_model_attrs_map_preserves_none() -> None:
    '''
    Test that from_model -> to_attrs -> from_attrs -> map keeps None for a
    declared field instead of substituting the string default.
    '''
    node_obj = NullableNoteNodeObject.from_model(NullableNoteDomain(name='Widget', note=None))
    attrs = node_obj.to_attrs()
    restored = NullableNoteNodeObject.from_attrs(attrs)
    mapped = restored.map(NullableNoteAggregate)

    assert node_obj.note is None
    assert node_obj.to_primitive()['note'] is None
    assert attrs['note'] == ''
    assert restored.note is None
    assert mapped.note is None

# ** test: node_explicit_exclude_still_omits_nullable_field
def test_node_explicit_exclude_still_omits_nullable_field() -> None:
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
