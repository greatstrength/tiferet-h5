"""tiferet_h5 Mapper Settings"""

# *** imports

# ** core
from typing import Any, ClassVar, Dict, List, Optional, Type

# ** infra
import tables
from pydantic import ConfigDict

# ** app
from tiferet.domain import DomainObject
from tiferet.mappers import Aggregate, TransferObject

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
        type-appropriate defaults.  Callers should invoke ``table.flush()`` when
        the write sequence is complete.

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
        Python-native types before ``model_validate`` is called.

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

        # Construct and return the mapper instance.
        return cls.model_validate(data)

    # * method: to_primitive
    def to_primitive(self, **overrides) -> Dict[str, Any]:
        '''
        Serialize this object to a plain Python dict.

        Retains a compatible signature with ``TransferObject.to_primitive``
        for use when dict-based serialization is needed alongside row-based
        storage.

        :param overrides: Additional key-value pairs merged into the result.
        :type overrides: dict
        :return: A dict of Python-native field values.
        :rtype: Dict[str, Any]
        '''

        # Dump to dict using canonical field names, excluding None values.
        data = self.model_dump(exclude_none=True)

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

        # Apply overrides so they take priority.
        data.update(overrides)

        # Validate and construct the table object.
        return cls.model_validate(data)

    # * method: verify_schema
    @classmethod
    def verify_schema(cls, table: tables.Table) -> List[str]:
        '''
        Verify that an open table's column schema matches ``_H5_TYPES``.

        Returns a list of mismatch descriptions.  An empty list indicates the
        schema is fully consistent with the declared columns.

        :param table: The open PyTables ``Table`` to check against.
        :type table: tables.Table
        :return: A list of mismatch strings (empty if fully compatible).
        :rtype: List[str]
        '''

        # Collect mismatches between declared H5 columns and actual table cols.
        mismatches: List[str] = []

        # Check for columns declared in _H5_TYPES that are absent in the table.
        for field_name in cls._H5_TYPES:
            if field_name not in table.colnames:
                mismatches.append(
                    f'Column "{field_name}" declared in _H5_TYPES '
                    f'but not found in table at {table._v_pathname}.'
                )

        # Return all collected mismatch descriptions.
        return mismatches


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
    '''

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True},
    }

    # * method: to_attrs
    def to_attrs(self, role: str = 'to_h5.attrs', **overrides) -> Dict[str, Any]:
        '''
        Serialize this object to a flat dict suitable for HDF5 node attributes.

        Defaults to the ``"to_h5.attrs"`` role which applies
        ``by_alias=True``, ensuring that Pydantic ``serialization_alias``
        values are used as the HDF5 attribute key names rather than the
        canonical Python field names.  Pass an explicit ``role`` to override.

        Callers assign the returned dict entries directly to
        ``node._v_attrs``.

        :param role: Serialization role forwarded to ``to_primitive``.
            Defaults to ``"to_h5.attrs"``.
        :type role: str
        :param overrides: Additional key-value pairs merged into the result.
        :type overrides: dict
        :return: A flat dict of attribute name -> Python-native value pairs.
        :rtype: Dict[str, Any]
        '''

        # Delegate serialization to to_primitive with the h5 attrs role.
        return self.to_primitive(role=role, **overrides)

    # * method: from_attrs (static)
    @classmethod
    def from_attrs(cls, attrs: Dict[str, Any], **overrides) -> 'NodeObject':
        '''
        Construct a ``NodeObject`` from an HDF5 node attribute dict.

        Attribute values that are bytes are decoded to ``str``; NumPy scalars
        are converted to Python natives before ``model_validate`` is called.

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

        # Apply caller overrides.
        data.update(overrides)

        # Construct and return the node object.
        return cls.model_validate(data)
