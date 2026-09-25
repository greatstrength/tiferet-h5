"""tiferet_h5 Mappers Core"""

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

# ** function: nullable_field_index
# >> see: @guides/mappers.md#nullable-field-index
def nullable_field_index(model_cls: Type) -> Dict[str, str]:
    '''
    Map each ``_NULLABLE_FIELDS`` name to its aliased dump key.

    The value is the key ``model_dump(by_alias=True)`` would emit:
    ``serialization_alias`` when set, otherwise ``alias``, otherwise the
    canonical field name. Names that are not fields on ``model_cls`` are
    skipped.

    :param model_cls: The mapper class declaring ``_NULLABLE_FIELDS``.
    :type model_cls: Type
    :return: Canonical field name to dump key. Empty when nothing is nullable.
    :rtype: Dict[str, str]
    '''

    # Skip the lookup when the class has not opted in.
    index: Dict[str, str] = {}
    nullable_fields = getattr(model_cls, '_NULLABLE_FIELDS', [])
    if not nullable_fields:
        return index

    # Map each declared field to the key an aliased dump would emit.
    model_fields = getattr(model_cls, 'model_fields', {})
    for field_name in nullable_fields:
        field_info = model_fields.get(field_name)
        if field_info is None:
            continue
        alias = getattr(field_info, 'serialization_alias', None) or getattr(field_info, 'alias', None)
        if isinstance(alias, str) and alias:
            index[field_name] = alias
        else:
            index[field_name] = field_name

    # Return the field-to-key index.
    return index

# ** function: preserve_nullable_nones
# >> see: @guides/mappers.md#preserve-nullable-nones
def preserve_nullable_nones(
    model_cls: Type,
    data: Dict[str, Any],
    model: Any,
    *,
    by_alias: bool = False,
    exclude: Any = None,
    include: Any = None,
) -> Dict[str, Any]:
    '''
    Put declared ``None`` values back into an ``exclude_none`` dump.

    A field that is not ``None`` on ``model`` is left alone. An explicit
    ``exclude``, or an ``include`` that does not name the field, is honored.
    ``by_alias`` writes the key from ``nullable_field_index``; otherwise the
    canonical field name is used.

    :param model_cls: The mapper class declaring ``_NULLABLE_FIELDS``.
    :type model_cls: Type
    :param data: The serialized dict to update.
    :type data: Dict[str, Any]
    :param model: The model whose field values are authoritative.
    :type model: Any
    :param by_alias: Whether to write serialization-alias keys.
    :type by_alias: bool
    :param exclude: Field names an explicit dump exclude left out.
    :type exclude: Any
    :param include: Field names an explicit dump include kept.
    :type include: Any
    :return: The same dict, with declared ``None`` values preserved.
    :rtype: Dict[str, Any]
    '''

    # Nothing to preserve when the class declares no nullable fields.
    index = nullable_field_index(model_cls)
    if not index:
        return data

    # Collect names an explicit exclude or include leaves out.
    def listed_names(spec: Any) -> set:
        if isinstance(spec, dict):
            return {name for name, flag in spec.items() if flag and isinstance(name, str)}
        if isinstance(spec, (set, list, tuple, frozenset)):
            return {name for name in spec if isinstance(name, str)}
        return set()

    excluded = listed_names(exclude)
    included = listed_names(include) if include is not None else None

    # Reinsert None only for declared fields that are actually None on model.
    source_fields = getattr(type(model), 'model_fields', None)
    for field_name, dump_key in index.items():
        if field_name in excluded or dump_key in excluded:
            continue
        if included is not None and field_name not in included and dump_key not in included:
            continue
        if source_fields is not None and field_name not in source_fields:
            continue
        if getattr(model, field_name, None) is not None:
            continue
        data[dump_key if by_alias else field_name] = None

    # Return the dict with declared Nones restored.
    return data

# ** function: restore_null_sentinels
# >> see: @guides/mappers.md#restore-null-sentinels
def restore_null_sentinels(model_cls: Type, data: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Restore ``None`` for declared fields stored as the empty-string sentinel.

    Applied after decode, before ``model_validate``. For a declared field,
    stored ``''``, stored ``b''``, and stored ``None`` become Python ``None``.
    A field that is not listed is unchanged, including a stored ``''``.

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

    # Match the canonical name, the aliased dump key, and validation aliases.
    storage_keys = set(index) | set(index.values())
    model_fields = getattr(model_cls, 'model_fields', {})
    for field_name in index:
        validation_alias = getattr(model_fields.get(field_name), 'validation_alias', None)
        if isinstance(validation_alias, str):
            storage_keys.add(validation_alias)
            continue
        for choice in getattr(validation_alias, 'choices', []) or []:
            if isinstance(choice, str):
                storage_keys.add(choice)

    # Rewrite only declared keys whose value is the empty-string sentinel.
    for key, value in list(data.items()):
        if key not in storage_keys:
            continue
        if value == '' or value == b'' or value is None:
            data[key] = None

    # Return the data for the caller to validate.
    return data

# ** function: apply_attr_null_sentinels
# >> see: @guides/mappers.md#apply-attr-null-sentinels
def apply_attr_null_sentinels(model_cls: Type, data: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Replace a preserved ``None`` with the empty-string attribute sentinel.

    ``to_attrs`` must emit ``''`` for a declared nullable field rather than
    drop that key via ``exclude_none``. Keys already written under an alias
    are converted in place. Undeclared ``None`` values are not rewritten.

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
    declared_keys = set(index) | set(index.values())
    for key, value in list(data.items()):
        if key in declared_keys and value is None:
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
      ``''``.  HDF5 column names are never listed here.

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
    * ``verify_schema(table)`` -- classmethod; returns mismatch strings for a
      missing declared column, an undeclared live column, a PyTables type
      mismatch, or a ``StringCol`` itemsize mismatch.  Does not raise.
    * ``schema_fingerprint()`` -- classmethod; returns a stable 12-character
      marker derived from ``_H5_TYPES``.  Does not write the marker.
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
    # >> see: @guides/mappers.md#nullable-fields
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
        ``None`` as ``b''`` on a ``StringCol``; ``from_row`` restores it.  An
        undeclared ``None`` still encodes as ``b''`` and reads back as ``''``.
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
        nullable field whose decoded value is ``''`` or ``None`` is restored
        to ``None``.  Undeclared fields are not rewritten.

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

        Reports a declared column missing from the live table, a live column
        absent from ``_H5_TYPES``, a PyTables ``type`` mismatch, and a
        ``StringCol`` ``itemsize`` mismatch.  Returns a list of mismatch
        descriptions and does not raise.  An empty list indicates the schema
        is fully consistent with the declared columns.

        :param table: The open PyTables ``Table`` to check against.
        :type table: tables.Table
        :return: A list of mismatch strings (empty if fully compatible).
        :rtype: List[str]
        '''

        # Collect mismatches between declared H5 columns and actual table cols.
        mismatches: List[str] = []

        # Check declared columns for absence, then type and itemsize drift.
        for field_name, declared_col in cls._H5_TYPES.items():
            if field_name not in table.colnames:
                mismatches.append(
                    f'Column "{field_name}" declared in _H5_TYPES '
                    f'but not found in table at {table._v_pathname}.'
                )
                continue

            # Compare PyTables type identifiers for columns present on both sides.
            actual_col = table.coldescrs[field_name]
            if declared_col.type != actual_col.type:
                mismatches.append(
                    f'Column "{field_name}" type mismatch at {table._v_pathname}: '
                    f'declared "{declared_col.type}", found "{actual_col.type}".'
                )

            # String columns share the "string" type, so compare itemsize apart from type.
            elif declared_col.type == 'string' and declared_col.itemsize != actual_col.itemsize:
                mismatches.append(
                    f'Column "{field_name}" StringCol itemsize mismatch at '
                    f'{table._v_pathname}: declared {declared_col.itemsize}, '
                    f'found {actual_col.itemsize}.'
                )

        # Report live columns that are no longer declared.
        for col_name in table.colnames:
            if col_name not in cls._H5_TYPES:
                mismatches.append(
                    f'Column "{col_name}" present in table at {table._v_pathname} '
                    f'but not declared in _H5_TYPES.'
                )

        # Return all collected mismatch descriptions.
        return mismatches

    # * method: schema_fingerprint (static)
    @classmethod
    def schema_fingerprint(cls) -> str:
        '''
        Return a stable marker for the declared ``_H5_TYPES`` schema.

        The marker changes when a column name, PyTables type, or string width
        changes, and ignores declaration order.  It is derived from the
        declaration and is not written to a file.

        :return: The first 12 hexadecimal characters of the schema digest.
        :rtype: str
        '''

        # Build one canonical part per declared column, sorted by name.
        parts = []
        for name, col in sorted(cls._H5_TYPES.items()):
            itemsize = getattr(col, 'itemsize', '')
            parts.append(f'{name}:{col.type}:{itemsize}')

        # Hash the joined schema and return the short hex prefix.
        canonical = '|'.join(parts)
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        return digest[:12]

# ** class: node_object
class NodeObject(TransferObject):
    '''
    Base mapper class for attribute-oriented HDF5 node storage.

    ``NodeObject`` extends Tiferet's ``TransferObject`` with two additional
    methods for mapping domain objects to and from HDF5 node attribute sets
    (``_v_attrs``).  It is used when lightweight metadata -- e.g. config values,
    version markers, single-value settings -- is stored as node attributes
    rather than as table rows.

    Subclasses retain ``_ROLES``, ``map``, and the inherited construction
    path from ``TransferObject``.  ``to_primitive`` and ``from_model`` keep
    declared nullable ``None`` values, and ``to_attrs`` / ``from_attrs``
    layer the empty-string sentinel on top for attribute I/O.

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
    stays ``''``.
    '''

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True},
    }

    # * attribute: _NULLABLE_FIELDS
    # >> see: @guides/mappers.md#nullable-fields
    _NULLABLE_FIELDS: ClassVar[List[str]] = []

    # * method: to_primitive
    def to_primitive(self, role: str = None, **overrides) -> Dict[str, Any]:
        '''
        Serialize this object to a dict, preserving declared nullable ``None`` values.

        ``TransferObject.to_primitive`` starts from ``exclude_none=True``.
        Fields listed in ``_NULLABLE_FIELDS`` are put back as Python ``None``
        so ``map`` does not substitute a string default.  An explicit
        ``exclude`` or ``include`` is still honored.

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
            exclude=kwargs.get('exclude'),
            include=kwargs.get('include'),
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
        A declared nullable field whose decoded value is ``''`` or ``None``
        is restored to ``None``.  Undeclared fields are not rewritten.

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
        not set ``_NULLABLE_FIELDS`` use the inherited construction unchanged.

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

        # Dump canonical values, including undeclared Nones, then preserve declared ones.
        data = model.model_dump(by_alias=False)
        preserve_nullable_nones(cls, data, model)

        # Apply overrides so they take priority.
        data.update(overrides)

        # Validate and return the node object.
        return cls.model_validate(data)
