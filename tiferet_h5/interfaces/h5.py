"""tiferet_h5 Interfaces H5"""

# *** imports

# ** core
from abc import abstractmethod
from typing import Any, Dict, Iterator, List, Optional

# ** app
from tiferet.interfaces import FileService

# *** interfaces

# ** interface: h5_service
class H5Service(FileService):
    '''
    Service contract for HDF5 file operations via PyTables.

    Extends ``FileService`` with group, table, index, array, and attribute
    operations that map to the hierarchical structure of an HDF5 file.  All
    methods operate on the open file handle established by ``open_file`` /
    ``__enter__``.
    '''

    # * method: flush
    @abstractmethod
    def flush(self) -> None:
        '''
        Flush all pending write buffers to disk.

        Must be called after a sequence of ``append_rows`` operations when
        explicit durability is required before ``close_file``.
        '''
        raise NotImplementedError()

    # * method: node_exists
    @abstractmethod
    def node_exists(self, path: str) -> bool:
        '''
        Check whether a node exists at the given HDF5 path.

        :param path: Absolute HDF5 node path, e.g. ``"/features/calc"``.
        :type path: str
        :return: True if the node exists, otherwise False.
        :rtype: bool
        '''
        raise NotImplementedError()

    # * method: create_group
    @abstractmethod
    def create_group(self,
            path: str,
            title: str = '',
            create_parents: bool = True,
        ) -> Any:
        '''
        Create a group node at the specified path.

        :param path: Absolute HDF5 path for the new group.
        :type path: str
        :param title: Optional human-readable title for the group.
        :type title: str
        :param create_parents: Whether to create intermediate parent groups.
        :type create_parents: bool
        :return: The created PyTables group object.
        :rtype: Any
        '''
        raise NotImplementedError()

    # * method: get_group
    @abstractmethod
    def get_group(self, path: str) -> Any:
        '''
        Retrieve the group node at the specified path.

        :param path: Absolute HDF5 path for the group.
        :type path: str
        :return: The PyTables group object.
        :rtype: Any
        '''
        raise NotImplementedError()

    # * method: create_table
    @abstractmethod
    def create_table(self,
            path: str,
            description: type,
            title: str = '',
            **kwargs,
        ) -> Any:
        '''
        Create a table node at the specified path using an ``IsDescription`` schema.

        :param path: Absolute HDF5 path for the new table,
            e.g. ``"/features/calc"``.
        :type path: str
        :param description: A ``tables.IsDescription`` subclass defining the
            table schema.
        :type description: type
        :param title: Optional human-readable title for the table.
        :type title: str
        :param kwargs: Additional keyword arguments forwarded to
            ``tables.File.create_table``.
        :type kwargs: dict
        :return: The created PyTables table object.
        :rtype: Any
        '''
        raise NotImplementedError()

    # * method: get_table
    @abstractmethod
    def get_table(self, path: str) -> Any:
        '''
        Retrieve the table node at the specified path.

        :param path: Absolute HDF5 path for the table.
        :type path: str
        :return: The PyTables table object.
        :rtype: Any
        '''
        raise NotImplementedError()

    # * method: get_or_create_table
    @abstractmethod
    def get_or_create_table(self,
            path: str,
            description: type,
            title: str = '',
            **kwargs,
        ) -> Any:
        '''
        Return an existing table or create it if it does not yet exist.

        :param path: Absolute HDF5 path for the table.
        :type path: str
        :param description: ``IsDescription`` subclass used when creating.
        :type description: type
        :param title: Optional title used when creating.
        :type title: str
        :param kwargs: Extra kwargs forwarded to ``create_table`` when creating.
        :type kwargs: dict
        :return: The existing or newly created PyTables table object.
        :rtype: Any
        '''
        raise NotImplementedError()

    # * method: append_rows
    @abstractmethod
    def append_rows(self,
            path: str,
            rows: List[Dict[str, Any]],
        ) -> None:
        '''
        Append one or more rows to the table at ``path``.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param rows: List of dicts mapping column names to values.  String
            values are automatically encoded to bytes.
        :type rows: List[Dict[str, Any]]
        '''
        raise NotImplementedError()

    # * method: read_rows
    @abstractmethod
    def read_rows(self,
            path: str,
            start: Optional[int] = None,
            stop: Optional[int] = None,
            condition: Optional[str] = None,
        ) -> List[Dict[str, Any]]:
        '''
        Read rows from the table at ``path``, optionally filtered or sliced.

        When ``condition`` is provided it is applied as a PyTables in-kernel
        query; ``start`` / ``stop`` are applied as slice indices otherwise.

        :param path: Absolute HDF5 path for the source table.
        :type path: str
        :param start: Optional start row index (inclusive).
        :type start: Optional[int]
        :param stop: Optional stop row index (exclusive).
        :type stop: Optional[int]
        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :return: List of dicts with Python-native values (bytes decoded to str).
        :rtype: List[Dict[str, Any]]
        '''
        raise NotImplementedError()

    # * method: query
    @abstractmethod
    def query(self,
            path: str,
            condition: str,
            **kwargs,
        ) -> List[Dict[str, Any]]:
        '''
        Execute an in-kernel PyTables condition query against the table at ``path``.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param condition: PyTables condition string,
            e.g. ``'(group_id == b"calc") & (active == True)'``.
        :type condition: str
        :param kwargs: Additional kwargs forwarded to ``table.where``.
        :type kwargs: dict
        :return: Matching rows as a list of dicts with Python-native values.
        :rtype: List[Dict[str, Any]]
        '''
        raise NotImplementedError()

    # * method: iter_rows
    @abstractmethod
    def iter_rows(self,
            path: str,
            start: Optional[int] = None,
            stop: Optional[int] = None,
            condition: Optional[str] = None,
        ) -> Iterator[Dict[str, Any]]:
        '''
        Yield rows from the table at ``path`` without building a result list.

        When ``condition`` is provided it is applied as a PyTables in-kernel
        query; ``start`` / ``stop`` are applied as slice indices otherwise.

        :param path: Absolute HDF5 path for the source table.
        :type path: str
        :param start: Optional start row index (inclusive).
        :type start: Optional[int]
        :param stop: Optional stop row index (exclusive).
        :type stop: Optional[int]
        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :return: Normalized row dicts, one at a time.
        :rtype: Iterator[Dict[str, Any]]
        '''
        raise NotImplementedError()

    # * method: iter_query
    @abstractmethod
    def iter_query(self,
            path: str,
            condition: str,
            **kwargs,
        ) -> Iterator[Dict[str, Any]]:
        '''
        Yield rows matching an in-kernel PyTables condition.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param condition: PyTables condition string,
            e.g. ``'(group_id == b"calc") & (active == True)'``.
        :type condition: str
        :param kwargs: Additional kwargs forwarded to ``table.where``.
        :type kwargs: dict
        :return: Matching rows as normalized dicts, one at a time.
        :rtype: Iterator[Dict[str, Any]]
        '''
        raise NotImplementedError()

    # * method: remove_rows
    @abstractmethod
    def remove_rows(self, path: str, condition: str) -> int:
        '''
        Remove all rows matching ``condition`` from the table at ``path``.

        Deletion is performed in reverse index order to preserve row indices.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param condition: PyTables condition string identifying rows to delete.
        :type condition: str
        :return: The number of rows removed.
        :rtype: int
        '''
        raise NotImplementedError()

    # * method: create_array
    @abstractmethod
    def create_array(self,
            path: str,
            data: Any,
            title: str = '',
        ) -> Any:
        '''
        Create an array node at the specified path.

        :param path: Absolute HDF5 path for the new array.
        :type path: str
        :param data: The array data (NumPy array or Python sequence).
        :type data: Any
        :param title: Optional human-readable title.
        :type title: str
        :return: The created PyTables array object.
        :rtype: Any
        '''
        raise NotImplementedError()

    # * method: get_array
    @abstractmethod
    def get_array(self, path: str) -> Any:
        '''
        Retrieve the array node at the specified path.

        :param path: Absolute HDF5 path for the array.
        :type path: str
        :return: The PyTables array object.
        :rtype: Any
        '''
        raise NotImplementedError()

    # * method: set_node_attr
    @abstractmethod
    def set_node_attr(self, path: str, name: str, value: Any) -> None:
        '''
        Set a metadata attribute on the node at ``path``.

        :param path: Absolute HDF5 node path.
        :type path: str
        :param name: Attribute name.
        :type name: str
        :param value: Attribute value (must be picklable or a NumPy scalar).
        :type value: Any
        '''
        raise NotImplementedError()

    # * method: get_node_attr
    @abstractmethod
    def get_node_attr(self, path: str, name: str) -> Any:
        '''
        Retrieve a metadata attribute from the node at ``path``.

        :param path: Absolute HDF5 node path.
        :type path: str
        :param name: Attribute name.
        :type name: str
        :return: The attribute value.
        :rtype: Any
        '''
        raise NotImplementedError()

    # * method: get_node_attrs
    @abstractmethod
    def get_node_attrs(self, path: str) -> Dict[str, Any]:
        '''
        Retrieve all metadata attributes from the node at ``path`` as a dict.

        Bytes values are decoded to ``str`` and NumPy scalars are converted to
        Python-native types.  The returned dict is suitable for direct use with
        ``NodeObject.from_attrs()``.

        :param path: Absolute HDF5 node path.
        :type path: str
        :return: All node attributes as a plain Python dict.
        :rtype: Dict[str, Any]
        '''
        raise NotImplementedError()

    # * method: create_index
    @abstractmethod
    def create_index(self, path: str, column: str, **kwargs) -> None:
        '''
        Create a fully sorted CSI index on ``column`` of the table at ``path``.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param column: Name of the column to index.
        :type column: str
        :param kwargs: Additional kwargs forwarded to the index builder.
        :type kwargs: dict
        '''
        raise NotImplementedError()

    # * method: is_indexed
    @abstractmethod
    def is_indexed(self, path: str, column: str) -> bool:
        '''
        Return whether ``column`` of the table at ``path`` currently has an index.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param column: Name of the column to check.
        :type column: str
        :return: True if the column is indexed, otherwise False.
        :rtype: bool
        '''
        raise NotImplementedError()

    # * method: reindex
    @abstractmethod
    def reindex(self, path: str, column: Optional[str] = None) -> None:
        '''
        Recompute an existing column index, or every indexed column on the table.

        When ``column`` was never indexed, the call raises rather than no-opping.
        When ``column`` is omitted, every currently indexed column is recomputed.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param column: Column to reindex.  Omit to reindex every indexed column.
        :type column: Optional[str]
        '''
        raise NotImplementedError()
