"""tiferet_h5 Utils H5"""

# *** imports

# ** core
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

# ** infra
import tables

# ** app
from tiferet.utils import FileLoader
from tiferet.interfaces import ServiceError

from ..interfaces import H5Service
from ..mappers.settings import TableObject

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

# ** constant: h5_schema_mismatch_id
H5_SCHEMA_MISMATCH_ID = 'H5_SCHEMA_MISMATCH'

# ** constant: h5_index_failed_id
H5_INDEX_FAILED_ID = 'H5_INDEX_FAILED'

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
                f'Invalid H5 mode: {self.mode}. '
                f'Supported modes: {", ".join(VALID_H5_MODES)}.',
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
                    f'Invalid HDF5 file extension: {path}. Expected .h5 or .hdf5.',
                    path=str(path),
                )
            if not path.exists():
                ServiceError.raise_for(
                    H5Client,
                    H5_FILE_NOT_FOUND_ID,
                    f'File not found: {path}.',
                    path=str(path),
                )

        # For write / append modes verify the parent directory exists.
        else:
            if not path.parent.exists():
                ServiceError.raise_for(
                    H5Client,
                    H5_FILE_NOT_FOUND_ID,
                    f'Parent directory not found for: {path}.',
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
                f'H5 file is already open: {self.path}.',
                path=str(self.path),
            )

        # Validate the open mode.
        self.verify_mode()

        # Validate path and existence for the requested mode.
        self.verify_file(self.path, self.mode)

        try:

            # Open the HDF5 file via PyTables.
            self.h5file = tables.open_file(str(self.path), mode=self.mode)

        except tables.HDF5ExtError as e:

            # Wrap PyTables open failures as structured errors.
            ServiceError.raise_for(
                self,
                H5_FILE_NOT_FOUND_ID,
                f'Failed to open HDF5 file at {self.path}: {e}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        # Delegate to PyTables node existence check.
        return self.h5file.__contains__(path)

    # * method: _ensure_parent_groups
    def _ensure_parent_groups(self, parent_path: str) -> None:
        '''
        Ensure every intermediate group node down to ``parent_path`` exists,
        creating any that are missing one path segment at a time.

        ``tables.File.create_group`` requires ``name`` to be a single path
        segment even when ``createparents=True`` (that flag only covers
        parents of ``where``), so a multi-segment ``parent_path`` cannot be
        created in one call. This walks the path from the root, creating each
        missing segment individually.

        :param parent_path: Absolute HDF5 path whose group chain must exist.
        :type parent_path: str
        :raises ServiceError: If a PyTables error occurs while creating a
            missing intermediate group.
        '''

        # Walk each non-empty path segment from the root.
        current = ''
        for segment in parent_path.split('/'):
            if not segment:
                continue
            parent = current or '/'
            current = f'{current}/{segment}'

            # Create this segment's group if it does not already exist.
            if not self.node_exists(current):
                try:
                    self.h5file.create_group(parent, segment)

                except (tables.NodeError, tables.HDF5ExtError) as e:

                    # Wrap intermediate group creation failures as structured errors.
                    ServiceError.raise_for(
                        self,
                        H5_GROUP_CREATE_FAILED_ID,
                        f'Failed to create intermediate group at {current}: {e}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        # Split the path into parent and group name.
        parent_path, group_name = path.rsplit('/', 1)
        parent_path = parent_path or '/'

        # Create intermediate parents if requested and absent.
        if create_parents and not self.node_exists(parent_path):
            self._ensure_parent_groups(parent_path)

        try:

            # Create and return the group.
            return self.h5file.create_group(parent_path, group_name, title=title)

        except (tables.NodeError, tables.HDF5ExtError) as e:

            # Wrap group creation failures as structured errors.
            ServiceError.raise_for(
                self,
                H5_GROUP_CREATE_FAILED_ID,
                f'Failed to create group at {path}: {e}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        try:

            # Retrieve and return the group node.
            return self.h5file.get_node(path)

        except tables.NoSuchNodeError as e:

            # Raise a structured error for missing nodes.
            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {path}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        # Split path into parent group path and table name.
        parent_path, table_name = path.rsplit('/', 1)
        parent_path = parent_path or '/'

        # Resolve the parent group, creating it if absent. Left outside the
        # try block below so its own ServiceError (via _ensure_parent_groups)
        # propagates with its own error code instead of being re-wrapped.
        if not self.node_exists(parent_path):
            self._ensure_parent_groups(parent_path)

        try:

            parent = self.h5file.get_node(parent_path)

            # Create and return the table.
            return self.h5file.create_table(
                parent,
                table_name,
                description,
                title=title,
                **kwargs,
            )

        except (tables.NodeError, tables.HDF5ExtError) as e:

            # Wrap table creation failures as structured errors.
            ServiceError.raise_for(
                self,
                H5_TABLE_CREATE_FAILED_ID,
                f'Failed to create table at {path}: {e}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        try:

            # Retrieve and return the table node.
            return self.h5file.get_node(path)

        except tables.NoSuchNodeError as e:

            # Raise a structured error for missing nodes.
            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {path}.',
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

        # Otherwise create and return a new table.
        return self.create_table(path, description, title=title, **kwargs)

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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

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
                f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except (KeyError, ValueError, tables.HDF5ExtError) as e:

            ServiceError.raise_for(
                self,
                H5_WRITE_FAILED_ID,
                f'Failed to append rows to table at {path}: {e}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        try:

            # Retrieve the target table.
            table = self.h5file.get_node(path)

            # Apply condition query or sliced read.
            if condition:
                records = table.read_where(condition)
            else:
                records = table.read(start=start, stop=stop)

            # Normalize each record into a plain Python dict.
            result = [self._normalize_row(table, record) for record in records]

            # Return the list of normalized dicts.
            return result

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except (SyntaxError, NameError, tables.HDF5ExtError) as e:

            ServiceError.raise_for(
                self,
                H5_QUERY_FAILED_ID,
                f'Failed to query table at {path}: {e}.',
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

    # * method: _normalize_row
    def _normalize_row(self, table: Any, record: Any) -> Dict[str, Any]:
        '''
        Normalize a single PyTables record (a ``tables.Row`` instance or a
        NumPy structured record, both of which support column-name item
        access) into a plain Python dict.

        Shared by ``read_rows`` (eager, list-returning) and ``iter_rows``
        (lazy, generator-returning) so both normalize identically.

        :param table: The source PyTables table (for ``colnames``).
        :type table: Any
        :param record: A single row record.
        :type record: Any
        :return: A dict mapping column names to Python-native values.
        :rtype: Dict[str, Any]
        '''

        # Decode bytes and convert numpy scalars to Python natives per column.
        row_dict = {}
        for col in table.colnames:
            val = record[col]
            if isinstance(val, bytes):
                val = val.decode('utf-8')
            elif hasattr(val, 'item'):
                val = val.item()
            row_dict[col] = val
        return row_dict

    # * method: iter_rows
    def iter_rows(self,
            path: str,
            start: Optional[int] = None,
            stop: Optional[int] = None,
            condition: Optional[str] = None,
        ) -> Iterator[Dict[str, Any]]:
        '''
        Lazily stream rows from the table at ``path`` one at a time, without
        materializing the full result set in memory.

        Wraps ``table.iterrows()`` (unconditioned) or ``table.where()``
        (conditioned) -- both are true PyTables generators that read
        chunk-by-chunk from disk, unlike ``read_rows()``'s ``table.read()`` /
        ``table.read_where()``, which build a full in-memory result array
        up front. Node resolution and condition compilation happen eagerly
        (before this method returns) so failures surface immediately rather
        than on first iteration; per-row normalization happens lazily.

        :param path: Absolute HDF5 path for the source table.
        :type path: str
        :param start: Optional start row index (inclusive).
        :type start: Optional[int]
        :param stop: Optional stop row index (exclusive).
        :type stop: Optional[int]
        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :return: A generator of dicts with Python-native values.
        :rtype: Iterator[Dict[str, Any]]
        :raises ServiceError: If the file is not open, the node is absent,
            or the condition string is invalid.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        try:

            # Retrieve the target table and build the lazy row iterator.
            table = self.h5file.get_node(path)
            iterator = table.where(condition, start=start, stop=stop) if condition \
                else table.iterrows(start=start, stop=stop)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except (SyntaxError, NameError, tables.HDF5ExtError) as e:

            ServiceError.raise_for(
                self,
                H5_QUERY_FAILED_ID,
                f'Failed to query table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

        # Delegate the lazy per-row normalization to a generator helper, so
        # the eager validation above still raises synchronously.
        return self._stream_rows(table, iterator, path)

    # * method: _stream_rows
    def _stream_rows(self, table: Any, iterator: Any, path: str) -> Iterator[Dict[str, Any]]:
        '''
        Yield normalized row dicts from a PyTables row iterator, wrapping any
        error that only manifests mid-iteration as a structured ``ServiceError``.

        :param table: The source PyTables table (for ``colnames``).
        :type table: Any
        :param iterator: A ``table.iterrows()`` or ``table.where()`` iterator.
        :type iterator: Any
        :param path: Absolute HDF5 path for the source table (for error context).
        :type path: str
        :return: A generator of dicts with Python-native values.
        :rtype: Iterator[Dict[str, Any]]
        :raises ServiceError: If a query error occurs during iteration.
        '''

        try:

            # Normalize and yield each row one at a time.
            for record in iterator:
                yield self._normalize_row(table, record)

        except (SyntaxError, NameError, tables.HDF5ExtError) as e:

            ServiceError.raise_for(
                self,
                H5_QUERY_FAILED_ID,
                f'Failed to query table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

    # * method: iter_query
    def iter_query(self,
            path: str,
            condition: str,
            **kwargs,
        ) -> Iterator[Dict[str, Any]]:
        '''
        Lazily stream rows matching an in-kernel PyTables condition query.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param condition: PyTables condition string.
        :type condition: str
        :param kwargs: Additional kwargs (reserved for future use).
        :type kwargs: dict
        :return: A generator of matching rows as dicts with Python-native values.
        :rtype: Iterator[Dict[str, Any]]
        :raises ServiceError: If the file is not open, the node is absent,
            or the condition string is invalid.
        '''

        # Delegate to iter_rows with the condition applied.
        return self.iter_rows(path, condition=condition)

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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

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
                f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except (SyntaxError, NameError, IndexError, tables.HDF5ExtError) as e:

            ServiceError.raise_for(
                self,
                H5_WRITE_FAILED_ID,
                f'Failed to remove rows from table at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
            )

    # * method: create_index
    def create_index(self, path: str, column: str, **kwargs) -> None:
        '''
        Create a fully sorted (CSI) index on ``column`` of the table at ``path``,
        so condition-based ``query``/``read_rows``/``remove_rows`` calls against
        it are resolved by index lookup rather than a full-table scan.

        Index use by those methods is inherited PyTables condition-evaluator
        behavior once an index exists -- ``create_index`` has no other API
        surface to opt into it.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param column: Name of the column to index.
        :type column: str
        :param kwargs: Additional kwargs forwarded to ``Column.create_csindex``.
        :type kwargs: dict
        :raises ServiceError: If the file is not open, the node or column is
            absent, or the column is already indexed.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        try:

            # Retrieve the target table and column accessor.
            table = self.h5file.get_node(path)
            col = getattr(table.cols, column)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except AttributeError as e:

            ServiceError.raise_for(
                self,
                H5_INDEX_FAILED_ID,
                f'Column "{column}" not found on table at {path}.',
                cause=e,
                original_error=str(e),
                path=path,
                column=column,
            )

        try:

            # Create the fully sorted index.
            col.create_csindex(**kwargs)

        except (ValueError, tables.HDF5ExtError) as e:

            # Raised e.g. when the column is already indexed (PyTables'
            # own message points the caller at reindex() in that case).
            ServiceError.raise_for(
                self,
                H5_INDEX_FAILED_ID,
                f'Failed to create index on column "{column}" at {path}: {e}.',
                cause=e,
                original_error=str(e),
                path=path,
                column=column,
            )

    # * method: is_indexed
    def is_indexed(self, path: str, column: str) -> bool:
        '''
        Check whether ``column`` of the table at ``path`` currently has an index.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param column: Name of the column to check.
        :type column: str
        :return: True if the column is indexed, otherwise False.
        :rtype: bool
        :raises ServiceError: If the file is not open or the node or column is absent.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        try:

            # Retrieve the target table and column accessor.
            table = self.h5file.get_node(path)
            col = getattr(table.cols, column)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        except AttributeError as e:

            ServiceError.raise_for(
                self,
                H5_INDEX_FAILED_ID,
                f'Column "{column}" not found on table at {path}.',
                cause=e,
                original_error=str(e),
                path=path,
                column=column,
            )

        # Return the column's indexed state.
        return bool(col.is_indexed)

    # * method: reindex
    def reindex(self, path: str, column: Optional[str] = None) -> None:
        '''
        Recompute an existing index (or every existing index on the table)
        after a batch of writes has invalidated it.

        Re-indexing is always an explicit caller responsibility -- it is
        never invoked automatically by ``append_rows`` or ``flush``, since
        that would add unconditional cost to every write regardless of
        whether the table has any indexed columns at all.

        :param path: Absolute HDF5 path for the target table.
        :type path: str
        :param column: Name of a single column to re-index. When omitted,
            every currently indexed column on the table is re-indexed.
        :type column: Optional[str]
        :raises ServiceError: If the file is not open, the node or column is
            absent, or ``column`` is given but is not currently indexed.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        try:

            # Retrieve the target table.
            table = self.h5file.get_node(path)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

        # Re-index a single named column.
        if column is not None:
            try:
                col = getattr(table.cols, column)

            except AttributeError as e:

                ServiceError.raise_for(
                    self,
                    H5_INDEX_FAILED_ID,
                    f'Column "{column}" not found on table at {path}.',
                    cause=e,
                    original_error=str(e),
                    path=path,
                    column=column,
                )

            # PyTables' own Column.reindex() silently no-ops on a column
            # that was never indexed rather than raising -- fail loudly here
            # instead, so a caller typo or bad assumption is not masked.
            if not col.is_indexed:
                ServiceError.raise_for(
                    self,
                    H5_INDEX_FAILED_ID,
                    f'Column "{column}" at {path} is not indexed; call create_index() first.',
                    path=path,
                    column=column,
                )

            try:
                col.reindex()

            except (ValueError, tables.HDF5ExtError) as e:

                ServiceError.raise_for(
                    self,
                    H5_INDEX_FAILED_ID,
                    f'Failed to reindex column "{column}" at {path}: {e}.',
                    cause=e,
                    original_error=str(e),
                    path=path,
                    column=column,
                )

        # No column given: re-index every currently indexed column.
        else:
            try:
                for indexed_name in table.indexedcolpathnames:
                    getattr(table.cols, indexed_name).reindex()

            except (ValueError, tables.HDF5ExtError) as e:

                ServiceError.raise_for(
                    self,
                    H5_INDEX_FAILED_ID,
                    f'Failed to reindex table at {path}: {e}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        # Split path into parent group path and array name.
        parent_path, array_name = path.rsplit('/', 1)
        parent_path = parent_path or '/'

        try:

            # Resolve the parent group.
            parent = self.h5file.get_node(parent_path)

            # Create and return the array node.
            return self.h5file.create_array(parent, array_name, data, title=title)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {parent_path}.',
                cause=e,
                path=parent_path,
            )

        except (tables.NodeError, ValueError, tables.HDF5ExtError) as e:

            ServiceError.raise_for(
                self,
                H5_WRITE_FAILED_ID,
                f'Failed to create array at {path}: {e}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        try:

            # Retrieve and return the array node.
            return self.h5file.get_node(path)

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {path}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        try:

            # Retrieve the node and set the attribute.
            node = self.h5file.get_node(path)
            node._v_attrs[name] = value

        except tables.NoSuchNodeError as e:

            ServiceError.raise_for(
                self,
                H5_NODE_NOT_FOUND_ID,
                f'Node not found at path: {path}.',
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

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
                f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )

    # * method: assert_schema
    def assert_schema(self,
            path: str,
            table_cls: type[TableObject],
            check_version: bool = True,
        ) -> None:
        '''
        Verify the table at ``path`` matches ``table_cls``'s declared schema,
        raising a structured error on any detected drift.

        Enforcement is opt-in: this method is never called automatically by
        ``get_table`` or ``get_or_create_table``, so existing callers are
        unaffected unless they explicitly ask for the check. Column-level
        drift detection is delegated to ``table_cls.verify_schema()`` (which
        cannot raise itself -- the mapper layer never imports ``ServiceError``).
        When ``check_version`` is True and a ``schema_version`` node attribute
        is present on the table, it is additionally compared against
        ``table_cls.schema_fingerprint()``.

        :param path: Absolute HDF5 path for the table to verify.
        :type path: str
        :param table_cls: The ``TableObject`` subclass declaring the expected schema.
        :type table_cls: type[TableObject]
        :param check_version: Whether to additionally compare a stored
            ``schema_version`` node attribute against the current fingerprint.
        :type check_version: bool
        :raises ServiceError: If the file is not open, the node is absent, or
            a schema mismatch is detected.
        '''

        # Guard against an uninitialised file handle.
        if self.h5file is None:
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

        # Retrieve the target table (raises H5_NODE_NOT_FOUND if absent).
        table = self.get_table(path)

        # Collect column-level mismatches from the mapper's own detector.
        mismatches = table_cls.verify_schema(table)

        # Additionally compare the stored schema version, when present.
        if check_version:
            attrs = table._v_attrs
            if 'schema_version' in attrs._v_attrnamesuser:
                stored_version = attrs['schema_version']
                if isinstance(stored_version, bytes):
                    stored_version = stored_version.decode('utf-8')
                expected_version = table_cls.schema_fingerprint()
                if stored_version != expected_version:
                    mismatches.append(
                        f'Schema version mismatch at {path}: '
                        f'stored "{stored_version}", expected "{expected_version}".'
                    )

        # Raise a structured error if any mismatches were detected.
        if mismatches:
            ServiceError.raise_for(
                self,
                H5_SCHEMA_MISMATCH_ID,
                f'Schema mismatch at {path}: {"; ".join(mismatches)}.',
                path=path,
                mismatches=mismatches,
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
            ServiceError.raise_for(self, H5_CONN_NOT_INITIALIZED_ID, H5_CONN_NOT_INITIALIZED_MESSAGE)

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
                f'Node not found at path: {path}.',
                cause=e,
                path=path,
            )
