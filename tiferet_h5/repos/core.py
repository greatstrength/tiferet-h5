"""tiferet_h5 Repos Core"""

# *** imports

# ** core
from typing import ClassVar, Iterator, List, Optional, Type

# ** app
from ..mappers import TableObject

# *** constants

# ** constant: schema_version_attr
SCHEMA_VERSION_ATTR = 'schema_version'

# *** classes

# ** class: table_repository
class TableRepository:
    '''
    Shared open, append, and read sequence for columnar HDF5 repositories.

    Compose this mixin beside ``H5Repository`` and declare ``table_cls`` and
    ``table_path``. Missing-file reads stay empty, and schema checks run only
    when ``verify`` is called. The first create stamps ``schema_version``
    unless ``stamp_schema_version`` is false.
    '''

    # * attribute: table_cls
    table_cls: ClassVar[Type[TableObject]]

    # * attribute: table_path
    table_path: ClassVar[str] = ''

    # * attribute: stamp_schema_version
    stamp_schema_version: ClassVar[bool] = True

    # * method: resolve_table_path
    def resolve_table_path(self, **path_kwargs) -> str:
        '''
        Return the HDF5 path for this repository's table.

        Placeholders in ``table_path`` are formatted only when keyword
        arguments are given. An empty call returns the template unchanged.

        :param path_kwargs: Values for ``table_path`` placeholders.
        :type path_kwargs: dict
        :return: The resolved absolute HDF5 table path.
        :rtype: str
        '''

        # Format only when the caller supplied placeholder values.
        if path_kwargs:
            return self.table_path.format(**path_kwargs)

        # Otherwise leave the template unchanged.
        return self.table_path

    # * method: save
    def save(self, obj: TableObject, **path_kwargs) -> None:
        '''
        Append one table object as a new row.

        Creates the table when the node is absent. On that first create, and
        only when ``stamp_schema_version`` is true, writes ``schema_version``
        from ``table_cls.schema_fingerprint()``. A later save does not rewrite
        it. Does not check the live schema; call ``verify`` for that.

        :param obj: The table object to append.
        :type obj: TableObject
        :param path_kwargs: Values for ``table_path`` placeholders.
        :type path_kwargs: dict
        '''

        # Resolve the table path from class state and caller kwargs.
        path = self.resolve_table_path(**path_kwargs)

        # Create the table when absent, stamp once, append one row, and flush.
        with self.client() as h5:
            # Record whether this save is creating the table.
            created = not h5.node_exists(path)

            # Open the existing table or create it from the declared schema.
            table = h5.get_or_create_table(path, self.table_cls.get_description())

            # Stamp the fingerprint only on the create, and only when enabled.
            if created and self.stamp_schema_version:
                h5.set_node_attr(
                    path,
                    SCHEMA_VERSION_ATTR,
                    self.table_cls.schema_fingerprint(),
                )

            # Append the row and flush the table.
            obj.to_row(table)
            table.flush()

    # * method: get
    def get(self, condition: str, **path_kwargs) -> Optional[TableObject]:
        '''
        Return the first row matching ``condition``, or ``None``.

        A missing file returns ``None`` without opening a client. A missing
        table node also returns ``None``.

        :param condition: PyTables condition string identifying the row.
        :type condition: str
        :param path_kwargs: Values for ``table_path`` placeholders.
        :type path_kwargs: dict
        :return: The first matching table object, or ``None``.
        :rtype: Optional[TableObject]
        '''

        # A missing file must not open or create the HDF5 path.
        if not self.file_exists():
            return None

        # Resolve the table path from class state and caller kwargs.
        path = self.resolve_table_path(**path_kwargs)

        # Read the first match, or nothing when the node is absent.
        with self.client() as h5:
            if not h5.node_exists(path):
                return None

            rows = h5.read_rows(path, condition=condition)

        # Map the first row when the condition matched.
        if not rows:
            return None

        return self.table_cls.from_row(rows[0])

    # * method: list
    def list(self,
            condition: Optional[str] = None,
            **path_kwargs,
        ) -> List[TableObject]:
        '''
        Return rows at the resolved table path, optionally filtered.

        A missing file or table node returns an empty list and does not
        create the file.

        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :param path_kwargs: Values for ``table_path`` placeholders.
        :type path_kwargs: dict
        :return: Matching table objects, or an empty list.
        :rtype: List[TableObject]
        '''

        # A missing file must not open or create the HDF5 path.
        if not self.file_exists():
            return []

        # Resolve the table path from class state and caller kwargs.
        path = self.resolve_table_path(**path_kwargs)

        # Read matching rows, or nothing when the node is absent.
        with self.client() as h5:
            if not h5.node_exists(path):
                return []

            rows = h5.read_rows(path, condition=condition)

        # Map each row dict onto the declared table class.
        return [self.table_cls.from_row(row) for row in rows]

    # * method: iter_list
    def iter_list(self,
            condition: Optional[str] = None,
            **path_kwargs,
        ) -> Iterator[TableObject]:
        '''
        Yield table objects for each matching row.

        A missing file yields nothing and does not open a client. Path and
        node checks may wait until the first iteration. The file stays open
        until the iterator is exhausted or closed.

        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :param path_kwargs: Values for ``table_path`` placeholders.
        :type path_kwargs: dict
        :return: Matching table objects, one at a time.
        :rtype: Iterator[TableObject]
        '''

        # A missing file yields nothing and must not open a client.
        if not self.file_exists():
            return

        # Resolve the table path. The check may wait until iteration starts.
        path = self.resolve_table_path(**path_kwargs)

        # Stream mapped rows while the client stays open.
        with self.client() as h5:
            if not h5.node_exists(path):
                return

            for row in h5.iter_rows(path, condition=condition):
                yield self.table_cls.from_row(row)

    # * method: delete
    def delete(self, condition: str, **path_kwargs) -> int:
        '''
        Remove rows matching ``condition`` and return how many were removed.

        :param condition: PyTables condition string identifying rows to delete.
        :type condition: str
        :param path_kwargs: Values for ``table_path`` placeholders.
        :type path_kwargs: dict
        :return: The number of rows removed.
        :rtype: int
        '''

        # Resolve the table path before opening the file.
        path = self.resolve_table_path(**path_kwargs)

        # Delegate deletion and return the removed-row count.
        with self.client() as h5:
            return h5.remove_rows(path, condition)

    # * method: exists
    def exists(self, condition: str, **path_kwargs) -> bool:
        '''
        Return whether any row matches ``condition``.

        A missing file or table node returns ``False`` without creating the
        file. A missing file does not open a client.

        :param condition: PyTables condition string identifying the row.
        :type condition: str
        :param path_kwargs: Values for ``table_path`` placeholders.
        :type path_kwargs: dict
        :return: True if at least one row matches, otherwise False.
        :rtype: bool
        '''

        # A missing file must not open or create the HDF5 path.
        if not self.file_exists():
            return False

        # Resolve the table path from class state and caller kwargs.
        path = self.resolve_table_path(**path_kwargs)

        # Stop at the first match, or report absence when the node is missing.
        with self.client() as h5:
            if not h5.node_exists(path):
                return False

            for _row in h5.iter_rows(path, condition=condition):
                return True

        return False

    # * method: verify
    def verify(self, **path_kwargs) -> None:
        '''
        Assert that the live table matches ``table_cls``.

        This check is opt-in. ``save``, ``get``, and ``list`` do not call it.

        :param path_kwargs: Values for ``table_path`` placeholders.
        :type path_kwargs: dict
        '''

        # Resolve the table path before opening the file.
        path = self.resolve_table_path(**path_kwargs)

        # Delegate the schema check to the open client.
        with self.client() as h5:
            h5.assert_schema(path, self.table_cls)
