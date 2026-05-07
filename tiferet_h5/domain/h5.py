"""tiferet_h5 Domain H5"""

# *** imports

# ** core
from typing import Any, Dict, List, Optional

# ** infra
from pydantic import Field

# ** app
from tiferet.domain import DomainObject

# *** models

# ** model: h5_column
class H5Column(DomainObject):
    '''
    A domain object representing a single typed column in an HDF5 table schema.

    Captures the column name, PyTables type descriptor string, an optional
    default value, and an optional explicit sort position.
    '''

    # * attribute: name
    name: str = Field(
        ...,
        description='The column name as it appears in the HDF5 table.',
    )

    # * attribute: dtype
    dtype: str = Field(
        ...,
        description=(
            'PyTables type descriptor string, e.g. "string256", "float64", '
            '"int64", "bool". For StringCol the format is "string<N>" where '
            'N is the byte width.'
        ),
    )

    # * attribute: default
    default: Optional[Any] = Field(
        default=None,
        description='Optional default value used when a field is absent during row writes.',
    )

    # * attribute: position
    position: Optional[int] = Field(
        default=None,
        description='Optional explicit column position for ordering within the table.',
    )


# ** model: h5_table_schema
class H5TableSchema(DomainObject):
    '''
    A domain object representing the full schema of an HDF5 table node.

    Serves as the Tiferet-side representation of a PyTables ``IsDescription``
    subclass, capturing the node path, optional title, and ordered column
    definitions. Used to drive table creation and mapper schema introspection.
    '''

    # * attribute: node_path
    node_path: str = Field(
        ...,
        description='Absolute HDF5 node path for the table, e.g. "/features/calc".',
    )

    # * attribute: title
    title: Optional[str] = Field(
        default=None,
        description='Optional human-readable title stored as HDF5 table metadata.',
    )

    # * attribute: columns
    columns: List[H5Column] = Field(
        default_factory=list,
        description='Ordered list of column definitions that compose the table schema.',
    )

    # * method: get_column
    def get_column(self, name: str) -> Optional[H5Column]:
        '''
        Retrieve a column definition by name.

        :param name: The column name to look up.
        :type name: str
        :return: The matching H5Column, or None if not found.
        :rtype: Optional[H5Column]
        '''

        # Search columns by name and return the first match.
        return next((col for col in self.columns if col.name == name), None)

    # * method: column_names
    def column_names(self) -> List[str]:
        '''
        Return an ordered list of column names.

        :return: Column names in definition order.
        :rtype: List[str]
        '''

        # Return the name attribute from each column in order.
        return [col.name for col in self.columns]


# ** model: h5_node
class H5Node(DomainObject):
    '''
    A lightweight domain object describing any navigable node in an HDF5 file.

    Captures the absolute path, node type classification, an optional title,
    and a snapshot of the node's attribute set.
    '''

    # * attribute: path
    path: str = Field(
        ...,
        description='Absolute HDF5 node path, e.g. "/features/calc/add".',
    )

    # * attribute: node_type
    node_type: str = Field(
        ...,
        description=(
            'Node type classification: "group", "table", "array", or "leaf".'
        ),
    )

    # * attribute: title
    title: Optional[str] = Field(
        default=None,
        description='Optional human-readable title stored as node metadata.',
    )

    # * attribute: attrs
    attrs: Dict[str, Any] = Field(
        default_factory=dict,
        description='Snapshot of the node attribute set (_v_attrs) as a plain dict.',
    )
