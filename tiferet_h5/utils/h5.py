"""tiferet_h5 Utils H5"""

# *** imports

# ** core
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

# ** infra
import tables

# ** app
from tiferet.interfaces import ServiceError
from tiferet.utils import FileLoader

from ..interfaces import H5Service

# *** constants (ids)

# ** constant: h5_file_not_found_id
H5_FILE_NOT_FOUND_ID = 'H5_FILE_NOT_FOUND'

# ** constant: h5_invalid_file_id
H5_INVALID_FILE_ID = 'H5_INVALID_FILE'

# ** constant: h5_invalid_mode_id
H5_INVALID_MODE_ID = 'H5_INVALID_MODE'

# ** constant: h5_file_already_open_id
H5_FILE_ALREADY_OPEN_ID = 'H5_FILE_ALREADY_OPEN'

# ** constant: h5_conn_not_initialized_id
H5_CONN_NOT_INITIALIZED_ID = 'H5_CONN_NOT_INITIALIZED'

# ** constant: h5_node_not_found_id
H5_NODE_NOT_FOUND_ID = 'H5_NODE_NOT_FOUND'

# ** constant: h5_group_create_failed_id
H5_GROUP_CREATE_FAILED_ID = 'H5_GROUP_CREATE_FAILED'

# ** constant: h5_table_create_failed_id
H5_TABLE_CREATE_FAILED_ID = 'H5_TABLE_CREATE_FAILED'

# ** constant: h5_query_failed_id
H5_QUERY_FAILED_ID = 'H5_QUERY_FAILED'

# ** constant: h5_write_failed_id
H5_WRITE_FAILED_ID = 'H5_WRITE_FAILED'

# ** constant: h5_index_failed_id
H5_INDEX_FAILED_ID = 'H5_INDEX_FAILED'

# ** constant: h5_schema_mismatch_id
H5_SCHEMA_MISMATCH_ID = 'H5_SCHEMA_MISMATCH'

# *** constants (messages)

# ** constant: h5_conn_not_initialized_message
H5_CONN_NOT_INITIALIZED_MESSAGE = (
    'HDF5 connection not initialized. Must be used within a "with" block.'
)

# ** constant: valid_h5_modes
VALID_H5_MODES = (
    'r',
    'r+',
    'w',
    'w-',
    'a',
)

# *** functions

# ** function: normalize_row
def normalize_row(table: Any, record: Any) -> Dict[str, Any]:
    '''
    Convert one table record into a dict of Python-native values.

    Bytes are decoded as UTF-8.  Values that expose ``item`` are reduced to
    their Python scalar.  Used by both eager reads and streaming iterators.

    :param table: The PyTables table that owns the record.
    :type table: Any
    :param record: A row, NumPy record, or mapping keyed by column name.
    :type record: Any
    :return: Column names mapped to Python-native values.
    :rtype: Dict[str, Any]
    '''

    # Read each column and reduce it to a Python-native value.
    row_dict = {}
    for col in table.colnames:
        val = record[col]
        if isinstance(val, bytes):
            val = val.decode('utf-8')
        elif hasattr(val, 'item'):
            val = val.item()
        row_dict[col] = val

    # Return the normalized row.
    return row_dict

# *** utils

# ** util: h5_client
class H5Client(FileLoader, H5Service):
    '''
    HDF5 file client with connection management and structured error handling.

    Extends ``FileLoader`` for path management and lifecycle conventions while
    implementing ``H5Service`` via the PyTables API.  The underlying file handle
    is stored as ``h5file`` (a ``tables.File`` object) rather than the text
    stream ``file`` used by ``FileLoader`` -- ``open_file`` and ``close_file``
    are fully overridden to reflect this.

    Valid open modes mirror PyTables:

    * ``'r'``  -- read-only; file must exist.
    * ``'r+'`` -- read-write; file must exist.
    * ``'w'``  -- write; truncates an existing file.
    * ``'w-'`` -- write; fails if file already exists.
    * ``'a'``  -- append / read-write; creates if absent (repo default).
    '''

    # * attribute: h5file
    h5file: Optional[tables.File]

    # * init
    def __init__(self,
            path: str | Path,
            mode: str = 'a',
            **kwargs,
        ):
        '''
        Initialize H5Client.

        :param path: Path to the HDF5 file (``str`` or ``Path``).
        :type path: str | Path
        :param mode: PyTables open mode (``'r'``, ``'r+'``, ``'w'``, ``'w-'``, ``'a'``).
        :type mode: str
        :param kwargs: Additional parameters passed to ``FileLoader``.
        :type kwargs: dict
        '''

        # Initialize the parent FileLoader with path and mode.
        super().__init__(path=path, mode=mode, **kwargs)

        # Initialize the HDF5 file handle to None.
        self.h5file = None

    # * method: verify_mode
    def verify_mode(self) -> None:
        '''
        Validate the HDF5 open mode string.

        :raises ServiceError: If the mode is not a valid PyTables mode.
        '''

        # Raise a structured error if the mode is not valid.
        if self.mode not in VALID_H5_MODES:
            ServiceError.raise_for(
                self,
                H5_INVALID_MODE_ID,
                message=(
                    f'Invalid H5 mode: {self.mode}. '
                    f'Supported modes: {", ".join(VALID_H5_MODES)}.'
                ),
                mode=self.mode,
            )

    # * method: verify_file (static)
    @staticmethod
    def verify_file(path: Path, mode: str = 'r') -> None:
        '''
        Verify the file path is suitable for the requested mode.

        For read modes (``'r'``, ``'r+'``) the file must exist and carry a
        ``.h5`` or ``.hdf5`` extension.  For write modes (``'w'``, ``'w-'``,
        ``'a'``) only the parent directory is required to exist.

        :param path: The resolved file path.
        :type path: Path
        :param mode: The PyTables open mode.
        :type mode: str
        :raises ServiceError: If validation fails.
        '''

        # For read modes verify extension and file existence.
        if mode in ('r', 'r+'):
            if path.suffix.lower() not in {'.h5', '.hdf5'}:
                ServiceError.raise_for(
                    H5Client,
                    H5_INVALID_FILE_ID,
                    message=f'Invalid HDF5 file extension: {path}. Expected .h5 or .hdf5.',
                    path=str(path),
                )
            if not path.exists():
                ServiceError.raise_for(
                    H5Client,
                    H5_FILE_NOT_FOUND_ID,
                    message=f'File not found: {path}.',
                    path=str(path),
                )

        # For write / append modes verify the parent directory exists.
        else:
            if not path.parent.exists():
                ServiceError.raise_for(
                    H5Client,
                    H5_FILE_NOT_FOUND_ID,
                    message=f'Parent directory not found for: {path}.',
                    path=str(path),
                )

    # * method: open_file
    def open_file(self) -> 'H5Client':
        '''
        Open the HDF5 file and store the handle in ``h5file``.

        :return: This ``H5Client`` instance (for use as a context manager).
        :rtype: H5Client
        :raises ServiceError: If the file is already open, the path or mode
            is invalid, or PyTables raises an exception.
        '''

        # Raise an error if the file handle is already open.
        if self.h5file is not None:
            ServiceError.raise_for(
                self,
                H5_FILE_ALREADY_OPEN_ID,
                message=f'H5 file is already open: {self.path}.',
                path=str(self.path),
            )

        # Validate the open mode.
        self.verify_mode()

        # Validate path and existence for the requested mode.
        self.verify_file(self.path, self.mode)

        try:

            # Open the HDF5 file via PyTables.
            self.h5file = tables.open_file(str(self.path), mode=self.mode)

        except (tables.HDF5ExtError, OSError) as e:

            # Wrap driver and filesystem open failures as structured errors.
            ServiceError.raise_for(
                self,
                H5_FILE_NOT_FOUND_ID,
                message=f'Failed to open HDF5 file at {self.path}: {e}.',
                cause=e,
                original_error=str(e),
                path=str(self.path),
            )

        # Return self so the context manager pattern works.
        return self

    # * method: close_file
    def close_file(self) -> None:
        '''
        Flush pending writes and close the HDF5 file handle.
        '''

        # Flush and close the file handle if it is open, then reset to None.
        if self.h5file is not None:
            self.h5file.flush()
            self.h5file.close()
            self.h5file = None

    # * method: flush
    def flush(self) -> None:
        '''
        Flush all pending write buffers to disk without closing the file.

        :raises ServiceError: If the file is not open.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        # Flush the open file handle.
        self.h5file.flush()

    # * method: __enter__
    def __enter__(self) -> 'H5Client':
        '''
        Enter the runtime context and open the HDF5 file.

        :return: This ``H5Client`` instance with an active file handle.
        :rtype: H5Client
        '''

        # Open the file and return self.
        return self.open_file()

    # * method: __exit__
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        '''
        Exit the runtime context and close the HDF5 file.

        :param exc_type: The exception type, if any.
        :param exc_val: The exception value, if any.
        :param exc_tb: The exception traceback, if any.
        :return: False so exceptions propagate to the caller.
        :rtype: bool
        '''

        # Close the file (flushes internally).
        self.close_file()

        # Propagate exceptions.
        return False

    # * method: node_exists
    def node_exists(self, path: str) -> bool:
        '''
        Check whether a node exists at the given HDF5 path.

        :param path: Absolute HDF5 node path.
        :type path: str
        :return: True if the node exists, otherwise False.
        :rtype: bool
        :raises ServiceError: If the file is not open.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        # Delegate to PyTables node existence check.
        return self.h5file.__contains__(path)

    # * method: ensure_parent_groups
    def ensure_parent_groups(self, parent_path: str) -> None:
        '''
        Create every missing group along an absolute HDF5 path.

        ``'/'`` is a no-op. Each missing segment is created individually
        because ``tables.File.create_group`` requires ``name`` to be a single
        path segment.

        :param parent_path: Absolute HDF5 path whose group chain must exist.
        :type parent_path: str
        :raises ServiceError: If the file is not open, or a PyTables failure
            occurs while creating a missing group.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        # The root group always exists.
        if parent_path in ('', '/'):
            return

        # Walk each non-empty path segment from the root.
        current = ''
        for segment in parent_path.split('/'):
            if not segment:
                continue

            parent = current or '/'
            current = f'{current}/{segment}'

            # Create this segment if it does not already exist.
            if not self.node_exists(current):
                try:
                    self.h5file.create_group(parent, segment)

                except (tables.NodeError, tables.HDF5ExtError, ValueError, OSError) as e:

                    # Wrap driver failures as a dedicated group-creation error.
                    ServiceError.raise_for(
                        self,
                        H5_GROUP_CREATE_FAILED_ID,
                        message=f'Failed to create group at {current}: {e}.',
                        cause=e,
                        original_error=str(e),
                        path=current,
                    )

    # * method: create_group
    def create_group(self,
            path: str,
            title: str = '',
            create_parents: bool = True,
        ) -> Any:
        '''
        Create a group node at the specified path.

        :param path: Absolute HDF5 path for the new group.
        :type path: str
        :param title: Optional human-readable title.
        :type title: str
        :param create_parents: Whether to create intermediate parent groups.
        :type create_parents: bool
        :return: The created PyTables group object.
        :rtype: Any
        :raises ServiceError: If the file is not open or group creation fails.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        # Split the path into parent and group name.
        parent_path, group_name = path.rsplit('/', 1)
        parent_path = parent_path or '/'

        # Create missing parents before the leaf group.
        if create_parents:
            self.ensure_parent_groups(parent_path)

        try:

            # Create and return the group.
            return self.h5file.create_group(parent_path, group_name, title=title)

        except (tables.NodeError, tables.HDF5ExtError, ValueError, OSError) as e:

            # Wrap leaf group creation failures as structured errors.
            ServiceError.raise_for(
                self,
                H5_GROUP_CREATE_FAILED_ID,
                message=f'Failed to create group at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

    # * method: get_group
    def get_group(self, path: str) -> Any:
        '''
        Retrieve the group node at the specified path.

        :param path: Absolute HDF5 path for the group.
        :type path: str
        :return: The PyTables group object.
        :rtype: Any
        :raises ServiceError: If the file is not open or the node is absent.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve and return the group node.
            return self.h5file.get_node(path)

        except tables.NoSuchNodeError as e:

            # Raise a structured error for missing nodes.
            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

    # * method: create_table
    def create_table(self,
            path: str,
            description: type,
            title: str = '',
            **kwargs,
        ) -> Any:
        '''
        Create a table node at the specified path using an ``IsDescription`` schema.

        :param path: Absolute HDF5 path for the new table.
        :type path: str
        :param description: A ``tables.IsDescription`` subclass.
        :type description: type
        :param title: Optional human-readable title.
        :type title: str
        :param kwargs: Additional kwargs forwarded to ``tables.File.create_table``.
        :type kwargs: dict
        :return: The created PyTables table object.
        :rtype: Any
        :raises ServiceError: If the file is not open or table creation fails.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        # Split path into parent group path and table name.
        parent_path, table_name = path.rsplit('/', 1)
        parent_path = parent_path or '/'

        # Create missing parents before the table leaf so a group failure
        # keeps its own error code instead of being wrapped as a table error.
        self.ensure_parent_groups(parent_path)

        try:

            # Resolve the parent group.
            parent = self.h5file.get_node(parent_path)

            # Create and return the table.
            return self.h5file.create_table(
                parent,
                table_name,
                description,
                title=title,
                **kwargs,
            )

        except (tables.NodeError, tables.HDF5ExtError, ValueError, OSError) as e:

            # Wrap driver and node failures as structured errors.
            ServiceError.raise_for(
                self,
                H5_TABLE_CREATE_FAILED_ID,
                message=f'Failed to create table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

    # * method: get_table
    def get_table(self, path: str) -> Any:
        '''
        Retrieve the table node at the specified path.

        :param path: Absolute HDF5 path for the table.
        :type path: str
        :return: The PyTables table object.
        :rtype: Any
        :raises ServiceError: If the file is not open or the node is absent.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve and return the table node.
            return self.h5file.get_node(path)

        except tables.NoSuchNodeError as e:

            # Raise a structured error for missing nodes.
            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

    # * method: get_or_create_table
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

        # Return the existing table if the node already exists.
        if self.node_exists(path):
            return self.get_table(path)

        # Create missing parents, then create and return a new table.
        parent_path = path.rsplit('/', 1)[0]
        self.ensure_parent_groups(parent_path or '/')

        # Create and return the table without recreating an existing one.
        return self.create_table(path, description, title=title, **kwargs)

    # * method: assert_schema
    # >> see: @guides/utils/h5.md#h5client-assert-schema
    def assert_schema(self,
            path: str,
            table_cls: type,
            check_version: bool = True,
        ) -> None:
        '''
        Verify the table at ``path`` against a ``TableObject`` declaration.

        :param path: Absolute HDF5 path for the table.
        :type path: str
        :param table_cls: ``TableObject`` subclass declaring the expected schema.
        :type table_cls: type
        :param check_version: Whether to compare a stored ``schema_version``.
        :type check_version: bool
        :raises ServiceError: If the file is not open, the node is absent, or
            the schema does not match.
        '''

        # Load the table. An unopened client or missing node raises here.
        table = self.get_table(path)

        # Collect column drift. The mapper reports mismatches and does not raise.
        mismatches = table_cls.verify_schema(table)

        # Compare a stored fingerprint only when asked and the attribute exists.
        if check_version and 'schema_version' in table._v_attrs._v_attrnamesuser:
            stored_version = table._v_attrs['schema_version']
            if isinstance(stored_version, bytes):
                stored_version = stored_version.decode('utf-8')
            expected_version = table_cls.schema_fingerprint()
            if stored_version != expected_version:
                mismatches.append(
                    f'schema_version at {path} is "{stored_version}", '
                    f'expected "{expected_version}".'
                )

        # Raise when any column or version mismatch was collected.
        if mismatches:
            ServiceError.raise_for(
                self,
                H5_SCHEMA_MISMATCH_ID,
                message=f'Schema mismatch at {path}: {"; ".join(mismatches)}',
                path=path,
                mismatches=mismatches,
            )

    # * method: append_rows
    def append_rows(self,
            path: str,
            rows: List[Dict[str, Any]],
        ) -> None:
        '''
        Append one or more rows to the table at ``path``.

        String values in each row dict are encoded to bytes automatically.
        ``table.flush()`` is called after all rows are appended.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param rows: List of dicts mapping column names to values.
        :type rows: List[Dict[str, Any]]
        :raises ServiceError: If the file is not open or a write error occurs.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the target table.
            table = self.h5file.get_node(path)
            row = table.row

            # Write each row dict to the table row buffer.
            for row_data in rows:
                for col_name, value in row_data.items():
                    if isinstance(value, str):
                        value = value.encode('utf-8')
                    row[col_name] = value
                row.append()

            # Flush the buffer to disk.
            table.flush()

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except (tables.NodeError, tables.HDF5ExtError, ValueError, OSError) as e:

            ServiceError.raise_for(
                self,
                H5_WRITE_FAILED_ID,
                message=f'Failed to append rows to table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

    # * method: read_rows
    def read_rows(self,
            path: str,
            start: Optional[int] = None,
            stop: Optional[int] = None,
            condition: Optional[str] = None,
        ) -> List[Dict[str, Any]]:
        '''
        Read rows from the table at ``path``, optionally filtered or sliced.

        Returns a list of plain Python dicts.  Bytes are decoded to ``str``;
        NumPy scalars are converted to Python natives.

        :param path: Absolute HDF5 path for the source table.
        :type path: str
        :param start: Optional start row index (inclusive).
        :type start: Optional[int]
        :param stop: Optional stop row index (exclusive).
        :type stop: Optional[int]
        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :return: List of dicts with Python-native values.
        :rtype: List[Dict[str, Any]]
        :raises ServiceError: If the file is not open, the node is absent,
            or a query error occurs.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the target table.
            table = self.h5file.get_node(path)

            # Apply condition query or sliced read.
            if condition:
                records = table.read_where(condition)
            else:
                records = table.read(start=start, stop=stop)

            # Normalize each record into a plain Python dict.
            result = []
            for record in records:
                result.append(normalize_row(table, record))

            # Return the list of normalized dicts.
            return result

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except (tables.NodeError, tables.HDF5ExtError, ValueError, OSError) as e:

            ServiceError.raise_for(
                self,
                H5_QUERY_FAILED_ID,
                message=f'Failed to query table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

    # * method: query
    def query(self,
            path: str,
            condition: str,
            **kwargs,
        ) -> List[Dict[str, Any]]:
        '''
        Execute an in-kernel PyTables condition query against the table at ``path``.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param condition: PyTables condition string.
        :type condition: str
        :param kwargs: Additional kwargs (reserved for future use).
        :type kwargs: dict
        :return: Matching rows as a list of dicts with Python-native values.
        :rtype: List[Dict[str, Any]]
        :raises ServiceError: If the file is not open, the node is absent,
            or the condition string is invalid.
        '''

        # Delegate to read_rows with the condition applied.
        return self.read_rows(path, condition=condition)

    # * method: iter_rows
    def iter_rows(self,
            path: str,
            start: Optional[int] = None,
            stop: Optional[int] = None,
            condition: Optional[str] = None,
        ) -> Iterator[Dict[str, Any]]:
        '''
        Yield rows from the table at ``path`` without building a result list.

        ``condition`` uses the same PyTables condition path as ``read_rows``.
        ``start`` and ``stop`` apply only when ``condition`` is omitted.

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
        :raises ServiceError: If the file is not open, the node is absent,
            or a query error occurs.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the target table without reading its rows.
            table = self.h5file.get_node(path)

            # Select a streaming source.  Do not materialize the result.
            if condition:
                records = table.where(condition)
            else:
                records = table.iterrows(start=start, stop=stop)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except Exception as e:

            ServiceError.raise_for(
                self,
                H5_QUERY_FAILED_ID,
                message=f'Failed to query table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

        # Yield normalized rows one at a time.
        return self.yield_normalized_rows(table, records, path)

    # * method: iter_query
    def iter_query(self,
            path: str,
            condition: str,
            **kwargs,
        ) -> Iterator[Dict[str, Any]]:
        '''
        Yield rows matching an in-kernel PyTables condition.

        Keyword arguments are forwarded to the same ``table.where`` mechanism
        that ``query`` documents.  The iterator is not converted to a list.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param condition: PyTables condition string.
        :type condition: str
        :param kwargs: Additional kwargs forwarded to ``table.where``.
        :type kwargs: dict
        :return: Matching rows as normalized dicts, one at a time.
        :rtype: Iterator[Dict[str, Any]]
        :raises ServiceError: If the file is not open, the node is absent,
            or the condition string is invalid.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the target table without reading its rows.
            table = self.h5file.get_node(path)

            # Open the same condition iterator query forwards kwargs toward.
            records = table.where(condition, **kwargs)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except Exception as e:

            ServiceError.raise_for(
                self,
                H5_QUERY_FAILED_ID,
                message=f'Failed to query table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

        # Yield matching rows one at a time.
        return self.yield_normalized_rows(table, records, path)

    # * method: yield_normalized_rows
    def yield_normalized_rows(self,
            table: Any,
            records: Any,
            path: str,
        ) -> Iterator[Dict[str, Any]]:
        '''
        Yield ``normalize_row`` results from a row iterator.

        Does not call ``list()`` on ``records``.  Failures raised while
        iterating are wrapped as ``ServiceError`` with the query failure id.

        :param table: The open PyTables table.
        :type table: Any
        :param records: A row iterator, not a materialized sequence.
        :type records: Any
        :param path: Absolute HDF5 path, included in error context.
        :type path: str
        :return: Normalized row dicts, one at a time.
        :rtype: Iterator[Dict[str, Any]]
        :raises ServiceError: If iterating the source fails.
        '''

        try:

            # Yield one normalized row at a time.
            for record in records:
                yield normalize_row(table, record)

        except Exception as e:

            ServiceError.raise_for(
                self,
                H5_QUERY_FAILED_ID,
                message=f'Failed to query table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

    # * method: remove_rows
    def remove_rows(self, path: str, condition: str) -> int:
        '''
        Remove all rows matching ``condition`` from the table at ``path``.

        Row indices are collected first then deleted in reverse order to keep
        remaining indices stable throughout the operation.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param condition: PyTables condition string identifying rows to delete.
        :type condition: str
        :return: The number of rows removed.
        :rtype: int
        :raises ServiceError: If the file is not open or the node is absent.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the target table.
            table = self.h5file.get_node(path)

            # Collect matching row indices.
            indices = table.get_where_list(condition)

            # Delete rows in reverse order to preserve index stability.
            for i in sorted(indices, reverse=True):
                table.remove_row(int(i))

            # Flush the table after deletion.
            table.flush()

            # Return the count of removed rows.
            return len(indices)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except (tables.NodeError, tables.HDF5ExtError, ValueError, OSError) as e:

            ServiceError.raise_for(
                self,
                H5_WRITE_FAILED_ID,
                message=f'Failed to remove rows from table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

    # * method: create_array
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
        :raises ServiceError: If the file is not open or creation fails.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        # Split path into parent group path and array name.
        parent_path, array_name = path.rsplit('/', 1)
        parent_path = parent_path or '/'

        # Create missing parents before the array leaf.
        self.ensure_parent_groups(parent_path)

        try:

            # Resolve the parent group.
            parent = self.h5file.get_node(parent_path)

            # Create and return the array node.
            return self.h5file.create_array(parent, array_name, data, title=title)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {parent_path}.',
                cause=e,
                path=parent_path,
            )

        except (tables.NodeError, tables.HDF5ExtError, ValueError, OSError) as e:

            ServiceError.raise_for(
                self,
                H5_WRITE_FAILED_ID,
                message=f'Failed to create array at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

    # * method: get_array
    def get_array(self, path: str) -> Any:
        '''
        Retrieve the array node at the specified path.

        :param path: Absolute HDF5 path for the array.
        :type path: str
        :return: The PyTables array object.
        :rtype: Any
        :raises ServiceError: If the file is not open or the node is absent.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve and return the array node.
            return self.h5file.get_node(path)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

    # * method: set_node_attr
    def set_node_attr(self, path: str, name: str, value: Any) -> None:
        '''
        Set a metadata attribute on the node at ``path``.

        :param path: Absolute HDF5 node path.
        :type path: str
        :param name: Attribute name.
        :type name: str
        :param value: Attribute value.
        :type value: Any
        :raises ServiceError: If the file is not open or the node is absent.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the node and set the attribute.
            node = self.h5file.get_node(path)
            node._v_attrs[name] = value

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

    # * method: get_node_attr
    def get_node_attr(self, path: str, name: str) -> Any:
        '''
        Retrieve a metadata attribute from the node at ``path``.

        :param path: Absolute HDF5 node path.
        :type path: str
        :param name: Attribute name.
        :type name: str
        :return: The attribute value.
        :rtype: Any
        :raises ServiceError: If the file is not open or the node is absent.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the raw attribute value from the node.
            node = self.h5file.get_node(path)
            val = node._v_attrs[name]

            # Normalize bytes and numpy scalars to Python natives.
            if isinstance(val, bytes):
                return val.decode('utf-8')
            if hasattr(val, 'item'):
                return val.item()
            return val

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

    # * method: get_node_attrs
    def get_node_attrs(self, path: str) -> Dict[str, Any]:
        '''
        Retrieve all metadata attributes from the node at ``path`` as a dict.

        Bytes values are decoded to ``str`` and NumPy scalars are converted to
        Python-native types.  The result is suitable for direct use with
        ``NodeObject.from_attrs()``.

        :param path: Absolute HDF5 node path.
        :type path: str
        :return: All node attributes as a plain Python dict.
        :rtype: Dict[str, Any]
        :raises ServiceError: If the file is not open or the node is absent.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the node's attribute set.
            node = self.h5file.get_node(path)
            attrs = node._v_attrs

            # Collect and normalize user-defined attribute names only.
            # _v_attrnamesuser excludes HDF5/PyTables system attributes
            # (CLASS, TITLE, VERSION, etc.) that are managed internally.
            result: Dict[str, Any] = {}
            for name in attrs._v_attrnamesuser:
                val = attrs[name]
                if isinstance(val, bytes):
                    val = val.decode('utf-8')
                elif hasattr(val, 'item'):
                    val = val.item()
                result[name] = val

            # Return the normalized attribute dict.
            return result

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

    # * method: create_index
    def create_index(self, path: str, column: str, **kwargs) -> None:
        '''
        Create a fully sorted CSI index on ``column`` of the table at ``path``.

        Keyword arguments are forwarded to ``Column.create_csindex``.  This
        method does not opt query or removal into index use; those methods keep
        their existing condition evaluation.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param column: Name of the column to index.
        :type column: str
        :param kwargs: Additional kwargs forwarded to the index builder.
        :type kwargs: dict
        :raises ServiceError: If the file is not open, the node is absent,
            or index creation fails.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the target table and column.
            table = self.h5file.get_node(path)
            col = getattr(table.cols, column)

        except tables.NoSuchNodeError as e:

            # Raise a structured error for missing nodes.
            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except AttributeError as e:

            # Raise a structured error when the column is absent.
            ServiceError.raise_for(
                self,
                H5_INDEX_FAILED_ID,
                message=f'Column "{column}" not found on table at {path}.',
                cause=e,
                original_error=str(e),
                path=path,
                column=column,
            )

        try:

            # Create the fully sorted index and forward builder options.
            col.create_csindex(**kwargs)

        except Exception as e:

            # Wrap builder failures, including an already-indexed column.
            ServiceError.raise_for(
                self,
                H5_INDEX_FAILED_ID,
                message=f'Failed to create index on column "{column}" at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
                column=column,
            )

    # * method: is_indexed
    def is_indexed(self, path: str, column: str) -> bool:
        '''
        Return whether ``column`` of the table at ``path`` currently has an index.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param column: Name of the column to check.
        :type column: str
        :return: True if the column is indexed, otherwise False.
        :rtype: bool
        :raises ServiceError: If the file is not open or the node or column
            is absent.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the target table and column.
            table = self.h5file.get_node(path)
            col = getattr(table.cols, column)

        except tables.NoSuchNodeError as e:

            # Raise a structured error for missing nodes.
            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except AttributeError as e:

            # Raise a structured error when the column is absent.
            ServiceError.raise_for(
                self,
                H5_INDEX_FAILED_ID,
                message=f'Column "{column}" not found on table at {path}.',
                cause=e,
                original_error=str(e),
                path=path,
                column=column,
            )

        # Return the column's current indexed state.
        return col.is_indexed

    # * method: reindex
    def reindex(self, path: str, column: Optional[str] = None) -> None:
        '''
        Recompute an existing column index, or every indexed column on the table.

        Reindexing is explicit.  ``append_rows`` and ``flush`` do not call this
        method.  A named column that was never indexed raises rather than
        no-opping.  Omitting ``column`` recomputes only columns that already
        have an index.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param column: Column to reindex.  Omit to reindex every indexed column.
        :type column: Optional[str]
        :raises ServiceError: If the file is not open, the node is absent,
            or the named column is not indexed.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(
                self,
                H5_CONN_NOT_INITIALIZED_ID,
                message=H5_CONN_NOT_INITIALIZED_MESSAGE,
            )

        try:

            # Retrieve the target table.
            table = self.h5file.get_node(path)

        except tables.NoSuchNodeError as e:

            # Raise a structured error for missing nodes.
            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                message=f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        # Recompute one column that must already be indexed.
        if column is not None:
            try:

                # Resolve the named column.
                col = getattr(table.cols, column)

            except AttributeError as e:

                # Raise a structured error when the column is absent.
                ServiceError.raise_for(
                    self,
                    H5_INDEX_FAILED_ID,
                    message=f'Column "{column}" not found on table at {path}.',
                    cause=e,
                    original_error=str(e),
                    path=path,
                    column=column,
                )

            # Do not no-op a column that was never indexed.
            if not col.is_indexed:
                ServiceError.raise_for(
                    self,
                    H5_INDEX_FAILED_ID,
                    message=(
                        f'Column "{column}" at {path} is not indexed; '
                        'call create_index() first.'
                    ),
                    path=path,
                    column=column,
                )

            try:

                # Recompute the existing column index.
                col.reindex()

            except Exception as e:

                # Wrap driver failures while rebuilding the column index.
                ServiceError.raise_for(
                    self,
                    H5_INDEX_FAILED_ID,
                    message=f'Failed to reindex column "{column}" at {path}: {e}.',
                    cause=e,
                    original_error=str(e),
                    path=path,
                    column=column,
                )

            return

        try:

            # Recompute every currently indexed column.  Unindexed columns stay
            # unindexed.
            table.reindex()

        except Exception as e:

            # Wrap driver failures while rebuilding table indexes.
            ServiceError.raise_for(
                self,
                H5_INDEX_FAILED_ID,
                message=f'Failed to reindex table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )
