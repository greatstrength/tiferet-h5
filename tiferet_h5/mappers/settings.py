"""tiferet_h5 Mapper Settings"""

# *** imports

# ** core
import hashlib
from typing import Any, ClassVar, Dict, List, Optional, Type

# ** infra
import tables
from pydantic import ConfigDict

# ** app
from tiferet.domain import DomainObject
from tiferet.mappers import Aggregate, TransferObject

# *** functions

# ** function: field_alias_names
def field_alias_names(field_info: Any) -> List[str]:
    '''
    Collect HDF5-facing alias names declared on a Pydantic field.

    Includes ``serialization_alias``, ``alias``, and string members of
    ``validation_alias`` so a stored column or attribute key can be matched
    back to the canonical Python field name. Callers of ``_NULLABLE_FIELDS``
    list canonical names; this lookup is how those names meet aliased storage.

    :param field_info: The Pydantic field metadata.
    :type field_info: Any
    :return: Alias names, excluding the canonical field name.
    :rtype: List[str]
    '''

    # Start with the aliases used when serializing by alias.
    names: List[str] = []
    serialization_alias = getattr(field_info, 'serialization_alias', None)
    alias = getattr(field_info, 'alias', None)
    for candidate in (serialization_alias, alias):
        if isinstance(candidate, str) and candidate not in names:
            names.append(candidate)

    # Include string validation aliases so read keys resolve too.
    validation_alias = getattr(field_info, 'validation_alias', None)
    if isinstance(validation_alias, str):
        choices = [validation_alias]
    else:
        choices = list(getattr(validation_alias, 'choices', []) or [])
    for choice in choices:
        if isinstance(choice, str) and choice not in names:
            names.append(choice)

    # Return the collected alias names.
    return names

# ** function: nullable_field_index
def nullable_field_index(model_cls: Type) -> Dict[str, str]:
    '''
    Map storage and canonical keys to canonical ``_NULLABLE_FIELDS`` names.

    Keys are the Python field name plus any declared alias. Values are always
    the canonical field name. Unknown names are skipped so an undeclared key
    is never rewritten.

    :param model_cls: The mapper class declaring ``_NULLABLE_FIELDS``.
    :type model_cls: Type
    :return: A key-to-field-name index. Empty when nothing is nullable.
    :rtype: Dict[str, str]
    '''

    # Skip the lookup entirely when the class opts out.
    index: Dict[str, str] = {}
    nullable_fields = getattr(model_cls, '_NULLABLE_FIELDS', [])
    if not nullable_fields:
        return index

    # Index each declared field under its canonical name and aliases.
    model_fields = getattr(model_cls, 'model_fields', {})
    for field_name in nullable_fields:
        field_info = model_fields.get(field_name)
        if field_info is None:
            continue
        index[field_name] = field_name
        for alias in field_alias_names(field_info):
            index[alias] = field_name

    # Return the completed index.
    return index

# ** function: restore_null_sentinels
def restore_null_sentinels(model_cls: Type, data: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Restore ``None`` for declared nullable fields whose stored value is empty.

    Applied after decode, before ``model_validate``. Only exact empty-string
    sentinels (``''`` or ``b''``) on keys that belong to ``_NULLABLE_FIELDS``
    are rewritten. Undeclared fields, including a genuine ``''``, are left
    unchanged. For a declared field, stored ``None`` and stored ``''`` are the
    same HDF5 value, so both read back as ``None``.

    :param model_cls: The mapper class declaring ``_NULLABLE_FIELDS``.
    :type model_cls: Type
    :param data: Decoded storage data, keyed by column or attribute name.
    :type data: Dict[str, Any]
    :return: The same dict, with declared empty sentinels restored to ``None``.
    :rtype: Dict[str, Any]
    '''

    # Nothing to restore when the class declares no nullable fields.
    index = nullable_field_index(model_cls)
    if not index:
        return data

    # Rewrite only declared keys whose value is the empty-string sentinel.
    for key, value in list(data.items()):
        if key not in index:
            continue
        if value == '' or value == b'':
            data[key] = None

    # Return the data for the caller to validate.
    return data

# ** function: serialization_name
def serialization_name(model_cls: Type, field_name: str, by_alias: bool) -> str:
    '''
    Return the key used for a field when serializing.

    :param model_cls: The mapper class that owns the field.
    :type model_cls: Type
    :param field_name: The canonical Python field name.
    :type field_name: str
    :param by_alias: Whether serialization aliases should be applied.
    :type by_alias: bool
    :return: The alias when ``by_alias`` is set and one exists; otherwise the field name.
    :rtype: str
    '''

    # Canonical names are the mapping-path keys.
    if not by_alias:
        return field_name

    # Prefer the serialization alias, matching model_dump(by_alias=True).
    field_info = model_cls.model_fields.get(field_name)
    if field_info is None:
        return field_name
    alias = field_info.serialization_alias or field_info.alias
    if isinstance(alias, str) and alias:
        return alias

    # Fall back to the canonical name when no alias is declared.
    return field_name

# ** function: omitted_field_names
def omitted_field_names(model_cls: Type, dump_kwargs: Dict[str, Any]) -> set:
    '''
    Return canonical field names that a ``model_dump`` call explicitly leaves out.

    ``exclude_none`` is ignored here: declared nullable ``None`` values are
    preserved even when that flag is set. An explicit ``exclude``, or an
    ``include`` that does not name the field, is honored.

    :param model_cls: The mapper class whose fields may be omitted.
    :type model_cls: Type
    :param dump_kwargs: Keyword arguments forwarded to ``model_dump``.
    :type dump_kwargs: Dict[str, Any]
    :return: Canonical field names that must stay absent.
    :rtype: set
    '''

    # Honor a set- or dict-style exclude.
    omitted = set()
    exclude = dump_kwargs.get('exclude')
    if isinstance(exclude, dict):
        omitted.update(
            name for name, flag in exclude.items() if flag and isinstance(name, str)
        )
    elif isinstance(exclude, (set, list, tuple, frozenset)):
        omitted.update(name for name in exclude if isinstance(name, str))

    # An include list omits every model field it does not name.
    include = dump_kwargs.get('include')
    if include is None:
        return omitted
    if isinstance(include, dict):
        included = {
            name for name, flag in include.items() if flag and isinstance(name, str)
        }
    elif isinstance(include, (set, list, tuple, frozenset)):
        included = {name for name in include if isinstance(name, str)}
    else:
        return omitted

    # Treat every field outside include as omitted.
    for field_name in model_cls.model_fields:
        if field_name not in included:
            omitted.add(field_name)

    # Return the names that must not be reinserted.
    return omitted

# ** function: preserve_nullable_nones
def preserve_nullable_nones(
    model_cls: Type,
    data: Dict[str, Any],
    source: Any,
    *,
    by_alias: bool = False,
    omitted: Optional[set] = None,
) -> Dict[str, Any]:
    '''
    Reinsert ``None`` for declared nullable fields dropped by ``exclude_none``.

    Does not convert a genuine empty string. A field that is not ``None`` on
    ``source``, or that was explicitly omitted, is left alone. This is the
    mapping-path hook: ``from_model``, ``to_primitive``, and ``map`` keep
    Python ``None`` instead of letting a string default replace it.

    :param model_cls: The mapper class declaring ``_NULLABLE_FIELDS``.
    :type model_cls: Type
    :param data: The serialized dict to update.
    :type data: Dict[str, Any]
    :param source: The model whose field values are authoritative.
    :type source: Any
    :param by_alias: Whether to write serialization-alias keys.
    :type by_alias: bool
    :param omitted: Canonical field names that must stay absent.
    :type omitted: Optional[set]
    :return: The same dict, with declared ``None`` values preserved.
    :rtype: Dict[str, Any]
    '''

    # Nothing to preserve when the class declares no nullable fields.
    nullable_fields = getattr(model_cls, '_NULLABLE_FIELDS', [])
    if not nullable_fields:
        return data

    # Reinsert None only for declared fields that are actually None on source.
    source_fields = getattr(type(source), 'model_fields', None)
    skipped = omitted or set()
    for field_name in nullable_fields:
        if field_name in skipped:
            continue
        if field_name not in getattr(model_cls, 'model_fields', {}):
            continue
        if source_fields is not None and field_name not in source_fields:
            continue
        if getattr(source, field_name, None) is not None:
            continue
        data[serialization_name(model_cls, field_name, by_alias)] = None

    # Return the dict with declared Nones restored.
    return data

# ** function: apply_attr_null_sentinels
def apply_attr_null_sentinels(model_cls: Type, data: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Replace preserved ``None`` values with the empty-string attribute sentinel.

    ``to_attrs`` must emit ``''`` for declared nullable fields rather than
    dropping those keys via ``exclude_none``. Keys already written under an
    alias are converted in place. Undeclared ``None`` values are not rewritten.

    :param model_cls: The mapper class declaring ``_NULLABLE_FIELDS``.
    :type model_cls: Type
    :param data: Attribute dict produced by ``to_primitive``.
    :type data: Dict[str, Any]
    :return: The same dict, with declared ``None`` values stored as ``''``.
    :rtype: Dict[str, Any]
    '''

    # Nothing to emit when the class declares no nullable fields.
    index = nullable_field_index(model_cls)
    if not index:
        return data

    # Convert declared Nones in place; leave every other value alone.
    for key, value in list(data.items()):
        if key in index and value is None:
            data[key] = ''

    # Return the attribute dict ready for node storage.
    return data

# *** classes

# ** class: table_object
class TableObject(DomainObject):
    '''
    Base mapper class for row-oriented HDF5 table storage.

    ``TableObject`` is the HDF5-native analogue to Tiferet's ``TransferObject``.
    Where ``TransferObject`` serializes via Pydantic ``model_dump()`` -> dict ->
    YAML/JSON, ``TableObject`` serializes to and from typed PyTables table rows
    (NumPy structured records).

    Subclasses declare:

    * ``_H5_TYPES`` -- a ``ClassVar[Dict[str, Any]]`` mapping field names to
      PyTables ``Col`` instances (e.g. ``tables.StringCol(256)``).  Used to
      auto-generate the ``IsDescription`` class when ``_DESCRIPTION`` is ``None``.
    * ``_DESCRIPTION`` -- an optional explicit ``tables.IsDescription`` subclass.
      When set, ``_H5_TYPES`` is ignored for schema generation.
    * ``_NULLABLE_FIELDS`` -- canonical Python field names whose ``None``
      values round-trip through the empty-string sentinel.  The default empty
      list keeps today's behavior, including a stored ``''`` that stays
      ``''``.  HDF5 column names are never listed here; alias resolution is
      separate.  For a declared field, stored ``None`` and stored ``''`` are
      the same value and both read back as ``None``.

    Key methods mirror ``TransferObject``:

    * ``get_description()`` -- returns the ``IsDescription`` class for table creation.
    * ``to_row(table)`` -- appends ``self`` as a new row to a PyTables ``Table``.
    * ``from_row(row)`` -- classmethod; constructs from a PyTables ``Row``,
      numpy record, or plain dict.
    * ``to_primitive(**overrides)`` -- dict serialization for compatibility.
    * ``map(target, **overrides)`` -- maps to a domain ``Aggregate``.
    * ``from_model(model, **overrides)`` -- classmethod; creates from a domain model.
    * ``normalize_value(value)`` -- static; decodes bytes and numpy scalars.
    * ``encode_value(value, col)`` -- static; encodes Python values for a column.
    * ``verify_schema(table)`` -- classmethod; checks live table matches ``_H5_TYPES``.
    '''

    # * attribute: model_config
    model_config = ConfigDict(
        extra='ignore',
        populate_by_name=True,
        validate_assignment=False,
        arbitrary_types_allowed=True,
        coerce_numbers_to_str=False,
    )

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {}

    # * attribute: _DESCRIPTION
    _DESCRIPTION: ClassVar[Optional[type]] = None

    # * attribute: _NULLABLE_FIELDS
    _NULLABLE_FIELDS: ClassVar[List[str]] = []

    # * method: get_description (static)
    @classmethod
    def get_description(cls) -> type:
        '''
        Return the PyTables ``IsDescription`` subclass for this mapper.

        If ``_DESCRIPTION`` is set explicitly it is returned directly.
        Otherwise the description is auto-generated from ``_H5_TYPES`` and
        cached on the class for subsequent calls.

        :return: A ``tables.IsDescription`` subclass.
        :rtype: type
        :raises ValueError: If neither ``_DESCRIPTION`` nor ``_H5_TYPES`` is set.
        '''

        # Return the explicit description if already set.
        if cls._DESCRIPTION is not None:
            return cls._DESCRIPTION

        # Require at least one column definition.
        if not cls._H5_TYPES:
            raise ValueError(
                f'{cls.__name__} must define _H5_TYPES or _DESCRIPTION '
                'before calling get_description().'
            )

        # Auto-generate an IsDescription subclass from _H5_TYPES.
        desc = type(
            f'{cls.__name__}Description',
            (tables.IsDescription,),
            dict(cls._H5_TYPES),
        )

        # Cache on the class so generation only happens once.
        cls._DESCRIPTION = desc

        # Return the generated description.
        return desc

    # * method: normalize_value (static)
    @staticmethod
    def normalize_value(value: Any) -> Any:
        '''
        Decode bytes to ``str`` and convert NumPy scalars to Python natives.

        Applied when reading values from a PyTables row or numpy record before
        constructing a ``TableObject`` via ``from_row``.

        :param value: A value read from a PyTables row or numpy record.
        :type value: Any
        :return: A Python-native equivalent.
        :rtype: Any
        '''

        # Decode bytes to UTF-8 string.
        if isinstance(value, bytes):
            return value.decode('utf-8')

        # Convert numpy scalars to native Python types.
        if hasattr(value, 'item'):
            return value.item()

        # Return as-is for plain Python types.
        return value

    # * method: encode_value (static)
    @staticmethod
    def encode_value(value: Any, col: Any) -> Any:
        '''
        Encode a Python value for storage in a PyTables column.

        String values are encoded to bytes for ``StringCol`` columns.
        ``None`` is replaced with a sensible default based on column type.

        :param value: The Python value to encode.
        :type value: Any
        :param col: The PyTables ``Col`` instance describing the column type.
        :type col: Any
        :return: The encoded value ready for row assignment.
        :rtype: Any
        '''

        # Handle None by substituting type-appropriate defaults.
        if value is None:
            if isinstance(col, tables.StringCol):
                return b''
            if isinstance(col, tables.BoolCol):
                return False
            return 0

        # Encode str to bytes for StringCol.
        if isinstance(value, str) and isinstance(col, tables.StringCol):
            return value.encode('utf-8')

        # Return the value unchanged for numeric and boolean columns.
        return value

    # * method: to_row
    def to_row(self, table: tables.Table) -> None:
        '''
        Append this object as a new row to a PyTables ``Table``.

        Column assignment uses ``model_dump(by_alias=True)`` so that Pydantic
        ``serialization_alias`` values are used as HDF5 column name keys.  This
        means ``_H5_TYPES`` keys should match the *alias* (HDF5 column name),
        not necessarily the Python field name.  ``None`` values are replaced with
        type-appropriate defaults.  A field listed in ``_NULLABLE_FIELDS`` stores
        ``None`` as ``b''`` on a ``StringCol`` and ``from_row`` restores it;
        an undeclared ``None`` still encodes as ``b''`` and reads back as ``''``.
        Callers should invoke ``table.flush()`` when the write sequence is complete.

        :param table: The open PyTables ``Table`` to append to.
        :type table: tables.Table
        '''

        # Obtain the row buffer from the table.
        row = table.row

        # Serialize using aliases so serialization_alias values become the keys.
        data = self.model_dump(by_alias=True)

        # Write each declared H5 column to the row buffer using the serialized data.
        for col_name, col_def in type(self)._H5_TYPES.items():
            raw_value = data.get(col_name)
            row[col_name] = self.encode_value(raw_value, col_def)

        # Commit the row buffer to the table.
        row.append()

    # * method: from_row (static)
    @classmethod
    def from_row(cls, row: Any) -> 'TableObject':
        '''
        Construct a ``TableObject`` instance from a PyTables row, numpy record,
        or plain dict.

        Bytes values are decoded to ``str``; NumPy scalars are converted to
        Python-native types before ``model_validate`` is called.  A declared
        nullable field whose decoded value is ``''`` is restored to ``None``.
        Undeclared fields are not rewritten.

        :param row: A ``tables.Row`` object, numpy record, or dict.
        :type row: Any
        :return: A new ``TableObject`` instance.
        :rtype: TableObject
        '''

        # Extract raw column data depending on the row type.
        if hasattr(row, 'table'):
            # tables.Row object -- iterate via the parent table colnames.
            raw = {col: row[col] for col in row.table.colnames}
        elif hasattr(row, 'dtype'):
            # Numpy record / structured array element.
            raw = {col: row[col] for col in row.dtype.names}
        else:
            # Plain dict (e.g. from read_rows).
            raw = dict(row)

        # Normalize bytes and numpy scalars to Python natives.
        data = {k: cls.normalize_value(v) for k, v in raw.items()}

        # Restore None for declared nullable fields stored as the empty sentinel.
        restore_null_sentinels(cls, data)

        # Construct and return the mapper instance.
        return cls.model_validate(data)

    # * method: to_primitive
    def to_primitive(self, **overrides) -> Dict[str, Any]:
        '''
        Serialize this object to a plain Python dict.

        Retains a compatible signature with ``TransferObject.to_primitive``
        for use when dict-based serialization is needed alongside row-based
        storage.  ``None`` is excluded except for fields listed in
        ``_NULLABLE_FIELDS``, which keep Python ``None`` so ``map`` does not
        substitute a string default.

        :param overrides: Additional key-value pairs merged into the result.
        :type overrides: dict
        :return: A dict of Python-native field values.
        :rtype: Dict[str, Any]
        '''

        # Dump to dict using canonical field names, excluding None values.
        data = self.model_dump(exclude_none=True)

        # Keep declared nullable Nones; undeclared Nones stay excluded.
        preserve_nullable_nones(type(self), data, self)

        # Merge caller overrides.
        data.update(overrides)

        # Return the serialized dict.
        return data

    # * method: map
    def map(self, target: Type[Aggregate], **overrides) -> Aggregate:
        '''
        Map this object to a domain ``Aggregate`` instance.

        :param target: The aggregate class to construct.
        :type target: Type[Aggregate]
        :param overrides: Additional keyword arguments merged into the data.
        :type overrides: dict
        :return: A new aggregate instance.
        :rtype: Aggregate
        '''

        # Serialize to dict and merge overrides.
        data = self.to_primitive()
        data.update(overrides)

        # Construct and return the target aggregate.
        return target(**data)

    # * method: from_model (static)
    @classmethod
    def from_model(cls, model: DomainObject, **overrides) -> 'TableObject':
        '''
        Create a ``TableObject`` instance from a domain model or aggregate.

        :param model: The source domain model instance.
        :type model: DomainObject
        :param overrides: Additional keyword arguments that take priority.
        :type overrides: dict
        :return: A new ``TableObject`` instance.
        :rtype: TableObject
        '''

        # Dump the model using canonical field names, excluding None.
        data = model.model_dump(by_alias=False, exclude_none=True)

        # Put declared nullable Nones back so a string default cannot replace them.
        preserve_nullable_nones(cls, data, model)

        # Apply overrides so they take priority.
        data.update(overrides)

        # Validate and construct the table object.
        return cls.model_validate(data)

    # * method: verify_schema
    @classmethod
    def verify_schema(cls, table: tables.Table) -> List[str]:
        '''
        Verify that an open table's column schema matches ``_H5_TYPES``.

        Detects schema drift in both directions: columns declared in
        ``_H5_TYPES`` that are absent from the live table, columns present in
        the live table but no longer declared, and type or ``StringCol``
        width drift for columns declared on both sides. Returns a list of
        mismatch descriptions; an empty list indicates the schema is fully
        consistent with the declared columns. This method never raises --
        pairing it with a real consequence is ``H5Client.assert_schema()``'s
        responsibility, since only the utils layer may import ``ServiceError``.

        :param table: The open PyTables ``Table`` to check against.
        :type table: tables.Table
        :return: A list of mismatch strings (empty if fully compatible).
        :rtype: List[str]
        '''

        # Collect mismatches between declared H5 columns and actual table cols.
        mismatches: List[str] = []

        # Check declared columns for absence, then type/width drift.
        for field_name, declared_col in cls._H5_TYPES.items():
            if field_name not in table.colnames:
                mismatches.append(
                    f'Column "{field_name}" declared in _H5_TYPES '
                    f'but not found in table at {table._v_pathname}.'
                )
                continue

            # Compare declared and actual PyTables type identifiers.
            actual_col = table.coldescrs[field_name]
            if declared_col.type != actual_col.type:
                mismatches.append(
                    f'Column "{field_name}" type mismatch at {table._v_pathname}: '
                    f'declared "{declared_col.type}", found "{actual_col.type}".'
                )

            # StringCol columns share the "string" type regardless of width,
            # so a byte-width mismatch must be checked separately.
            elif declared_col.type == 'string' and declared_col.itemsize != actual_col.itemsize:
                mismatches.append(
                    f'Column "{field_name}" StringCol width mismatch at '
                    f'{table._v_pathname}: declared {declared_col.itemsize}, '
                    f'found {actual_col.itemsize}.'
                )

        # Check for columns present in the table but no longer declared.
        for col_name in table.colnames:
            if col_name not in cls._H5_TYPES:
                mismatches.append(
                    f'Column "{col_name}" present in table at {table._v_pathname} '
                    f'but not declared in _H5_TYPES.'
                )

        # Return all collected mismatch descriptions.
        return mismatches

    # * method: schema_fingerprint
    @classmethod
    def schema_fingerprint(cls) -> str:
        '''
        Compute a deterministic fingerprint of the declared ``_H5_TYPES`` schema.

        The fingerprint is derived from each column's name, PyTables type
        identifier, and (for ``StringCol``) declared byte width, sorted by
        column name so field declaration order never affects the result. Two
        mapper classes with identical ``_H5_TYPES`` always produce the same
        fingerprint; any change to a column's name, type, or string width
        changes it. Auto-deriving the marker this way -- rather than a
        manually-bumped integer or human-assigned string -- means it can
        never silently drift out of sync with the schema it describes.

        Intended to be stamped as a ``schema_version`` node attribute on a
        table (e.g. via ``H5Client.set_node_attr``) so schema compatibility
        can be checked without opening and introspecting the table -- see
        ``H5Client.assert_schema()``.

        :return: A 12-character hexadecimal fingerprint string.
        :rtype: str
        '''

        # Build a canonical, column-order-independent representation.
        parts = sorted(
            f'{name}:{col.type}:{getattr(col, "itemsize", "")}'
            for name, col in cls._H5_TYPES.items()
        )
        canonical = '|'.join(parts)

        # Hash the canonical representation and truncate for a compact marker.
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12]


# ** class: node_object
class NodeObject(TransferObject):
    '''
    Base mapper class for attribute-oriented HDF5 node storage.

    ``NodeObject`` extends Tiferet's ``TransferObject`` with two additional
    methods for mapping domain objects to and from HDF5 node attribute sets
    (``_v_attrs``).  It is used when lightweight metadata -- e.g. config values,
    version markers, single-value settings -- is stored as node attributes
    rather than as table rows.

    Subclasses retain the full ``_ROLES`` / ``to_primitive`` / ``map`` /
    ``from_model`` behaviour inherited from ``TransferObject``.  The
    ``to_attrs`` and ``from_attrs`` methods layer on top for attribute I/O.

    A default ``_ROLES`` entry ``"to_h5.attrs"`` is provided with
    ``{"by_alias": True}`` so that Pydantic ``serialization_alias`` values
    are used as HDF5 attribute keys when ``to_attrs()`` is called without an
    explicit role.  Subclasses may extend ``_ROLES`` to add further roles
    (e.g. ``"to_h5.attrs"`` with additional ``exclude`` rules) while still
    inheriting this default.

    ``_NULLABLE_FIELDS`` lists canonical Python field names whose ``None``
    values round-trip through the empty-string sentinel.  ``to_attrs`` emits
    ``''`` for those fields even when the role sets ``exclude_none``.  The
    default empty list keeps today's behavior, including a stored ``''`` that
    stays ``''``.  For a declared field, stored ``None`` and stored ``''``
    are the same HDF5 value and both read back as ``None``.
    '''

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True},
    }

    # * attribute: _NULLABLE_FIELDS
    _NULLABLE_FIELDS: ClassVar[List[str]] = []

    # * method: to_primitive
    def to_primitive(self, role: str = None, **overrides) -> Dict[str, Any]:
        '''
        Serialize this object to a dict, preserving declared nullable ``None`` values.

        ``TransferObject.to_primitive`` starts from ``exclude_none=True``.
        Fields listed in ``_NULLABLE_FIELDS`` are put back as Python ``None``
        so ``map`` does not substitute a string default.  An explicit
        ``exclude`` or ``include`` is still honored.  Attribute storage uses
        ``to_attrs``, which turns those preserved ``None`` values into the
        empty-string sentinel.

        :param role: The serialization role to apply.
        :type role: str
        :param overrides: Additional keyword arguments passed to ``model_dump``.
        :type overrides: dict
        :return: The serialized dictionary.
        :rtype: Dict[str, Any]
        '''

        # Delegate, then stop when this class has not opted into the sentinel.
        data = super().to_primitive(role=role, **overrides)
        if not type(self)._NULLABLE_FIELDS:
            return data

        # Rebuild the dump kwargs so explicit omit rules are not undone.
        kwargs: Dict[str, Any] = {'exclude_none': True}
        if role and role in type(self)._ROLES:
            kwargs.update(type(self)._ROLES[role])
        kwargs.update(overrides)

        # Reinsert declared Nones under the same keys model_dump would use.
        return preserve_nullable_nones(
            type(self),
            data,
            self,
            by_alias=bool(kwargs.get('by_alias', False)),
            omitted=omitted_field_names(type(self), kwargs),
        )

    # * method: to_attrs
    def to_attrs(self, role: str = 'to_h5.attrs', **overrides) -> Dict[str, Any]:
        '''
        Serialize this object to a flat dict suitable for HDF5 node attributes.

        Defaults to the ``"to_h5.attrs"`` role which applies
        ``by_alias=True``, ensuring that Pydantic ``serialization_alias``
        values are used as the HDF5 attribute key names rather than the
        canonical Python field names.  Pass an explicit ``role`` to override.

        A field listed in ``_NULLABLE_FIELDS`` is emitted as ``''`` when its
        value is ``None``, even if the role sets ``exclude_none``.  Undeclared
        ``None`` values are still dropped when that flag is set.

        Callers assign the returned dict entries directly to
        ``node._v_attrs``.

        :param role: Serialization role forwarded to ``to_primitive``.
            Defaults to ``"to_h5.attrs"``.
        :type role: str
        :param overrides: Additional keyword arguments passed to ``model_dump``.
        :type overrides: dict
        :return: A flat dict of attribute name -> Python-native value pairs.
        :rtype: Dict[str, Any]
        '''

        # Serialize with the attrs role, which may exclude undeclared Nones.
        data = self.to_primitive(role=role, **overrides)

        # Emit the empty-string sentinel for declared Nones instead of dropping them.
        return apply_attr_null_sentinels(type(self), data)

    # * method: from_attrs (static)
    @classmethod
    def from_attrs(cls, attrs: Dict[str, Any], **overrides) -> 'NodeObject':
        '''
        Construct a ``NodeObject`` from an HDF5 node attribute dict.

        Attribute values that are bytes are decoded to ``str``; NumPy scalars
        are converted to Python natives before ``model_validate`` is called.
        A declared nullable field whose decoded value is ``''`` is restored
        to ``None``.  Undeclared fields are not rewritten.

        :param attrs: Dict of attribute name -> value pairs, typically obtained
            by reading from ``node._v_attrs``.
        :type attrs: Dict[str, Any]
        :param overrides: Additional key-value pairs that take priority.
        :type overrides: dict
        :return: A new ``NodeObject`` instance.
        :rtype: NodeObject
        '''

        # Normalize bytes and numpy scalars in attribute values.
        data: Dict[str, Any] = {}
        for k, v in attrs.items():
            if isinstance(v, bytes):
                data[k] = v.decode('utf-8')
            elif hasattr(v, 'item'):
                data[k] = v.item()
            else:
                data[k] = v

        # Restore None for declared nullable fields stored as the empty sentinel.
        restore_null_sentinels(cls, data)

        # Apply caller overrides.
        data.update(overrides)

        # Construct and return the node object.
        return cls.model_validate(data)

    # * method: from_model (static)
    @classmethod
    def from_model(cls, model: DomainObject, **overrides) -> 'NodeObject':
        '''
        Create a ``NodeObject`` from a domain model or aggregate.

        Declared nullable fields keep ``None`` instead of falling back to a
        string default when the source value is ``None``.  Classes that do
        not set ``_NULLABLE_FIELDS`` use the inherited ``TransferObject``
        construction unchanged.

        :param model: The source domain model or aggregate.
        :type model: DomainObject
        :param overrides: Additional keyword arguments that take priority.
        :type overrides: dict
        :return: A new ``NodeObject`` instance.
        :rtype: NodeObject
        '''

        # Keep today's construction when this class has not opted in.
        if not cls._NULLABLE_FIELDS:
            return super().from_model(model, **overrides)

        # Dump canonical values, then put declared Nones back if a dump dropped them.
        data = model.model_dump(by_alias=False)
        preserve_nullable_nones(cls, data, model)

        # Apply overrides so they take priority.
        data.update(overrides)

        # Validate and return the node object.
        return cls.model_validate(data)
