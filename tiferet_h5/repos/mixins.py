"""tiferet_h5 Repos Mixins"""

# *** imports

# ** core
from typing import ClassVar, Iterator, List, Optional, Type

# ** infra
import tables

# ** app
from ..mappers.settings import NodeObject, TableObject

# *** constants

# ** constant: schema_version_attr
SCHEMA_VERSION_ATTR = 'schema_version'

# *** repos

# ** repo: table_repository
class TableRepository:
    '''
    Reusable CRUD mixin for a declared TableObject class bound to an HDF5
    table path, so a concrete repository stops hand-rolling the same
    get_or_create_table() -> to_row()/from_row() -> flush() dance on every
    new table-backed domain concept.

    Intended to be composed alongside H5Repository (or any class providing
    a compatible client() method), e.g. ``class MyRepo(TableRepository,
    H5Repository): ...`` -- this mixin declares no __init__ of its own.

    Do not also mix in NodeRepository on the same class: both mixins share
    the save()/get()/exists() method names, and Python's MRO would
    silently resolve them to whichever mixin is listed first, shadowing
    the other entirely rather than raising. A repository that needs both
    a table and a node persisted in the same file should instantiate one
    of each (e.g. ``self.items = ItemTableRepo(h5_file)`` alongside
    ``self.meta = ItemMetaNodeRepo(h5_file)``), not multiply inherit both.
    '''

    # * attribute: table_cls
    table_cls: ClassVar[Type[TableObject]]

    # * attribute: table_path
    table_path: ClassVar[str] = ''

    # * attribute: filters
    filters: ClassVar[Optional[tables.Filters]] = None

    # * attribute: stamp_schema_version
    stamp_schema_version: ClassVar[bool] = True

    # * method: resolve_table_path
    def resolve_table_path(self, **path_kwargs) -> str:
        '''
        Resolve the absolute HDF5 path for this repository's table.

        Formats table_path with path_kwargs when any are given, so a
        template like '/kb/documents/{key}/steps' resolves per call.
        Fixed-path repositories need no override and no kwargs at all.

        :param path_kwargs: Values to interpolate into table_path.
        :type path_kwargs: dict
        :return: The resolved absolute HDF5 table path.
        :rtype: str
        '''

        # Format only when kwargs are given, so a fixed path needs no braces.
        if path_kwargs:
            return self.table_path.format(**path_kwargs)

        return self.table_path

    # * method: save
    def save(self, obj: TableObject, **path_kwargs) -> None:
        '''
        Append obj as a new row to this repository's table, creating the
        table (and stamping a schema_version attribute) on first write.

        The repository-level filters default is forwarded automatically so
        a concrete repository can set a house compression policy once
        rather than repeating tables.Filters(...) on every call site.

        :param obj: The TableObject instance to persist as a new row.
        :type obj: TableObject
        :param path_kwargs: Values to interpolate into table_path.
        :type path_kwargs: dict
        '''

        path = self.resolve_table_path(**path_kwargs)

        with self.client() as h5:

            # Detect first-write so the schema_version attribute is stamped
            # once at creation time only, never on every subsequent save.
            is_new = not h5.node_exists(path)
            table = h5.get_or_create_table(
                path,
                self.table_cls.get_description(),
                filters=self.filters,
            )

            if is_new and self.stamp_schema_version:
                h5.set_node_attr(path, SCHEMA_VERSION_ATTR, self.table_cls.schema_fingerprint())

            # Append the row and flush the write.
            obj.to_row(table)
            table.flush()

    # * method: get
    def get(self, condition: str, **path_kwargs) -> Optional[TableObject]:
        '''
        Return the first row matching condition, or None if no row matches
        or the table has not been created yet.

        Uses the repository's default client mode (never `'r'`) so a
        query against a not-yet-created file does not raise
        H5_FILE_NOT_FOUND -- "nothing here yet" is this method's normal,
        non-exceptional result, not a caller error.

        :param condition: A PyTables condition string identifying one row.
        :type condition: str
        :param path_kwargs: Values to interpolate into table_path.
        :type path_kwargs: dict
        :return: The matching TableObject, or None if not found.
        :rtype: Optional[TableObject]
        '''

        path = self.resolve_table_path(**path_kwargs)

        with self.client() as h5:
            if not h5.node_exists(path):
                return None

            rows = h5.read_rows(path, condition=condition)

        # Return None rather than raising -- exists() is the separate,
        # explicit way to distinguish "not found" from an error.
        if not rows:
            return None

        return self.table_cls.from_row(rows[0])

    # * method: list
    def list(self, condition: Optional[str] = None, **path_kwargs) -> List[TableObject]:
        '''
        Return every row matching condition (or every row, when omitted)
        as a list of TableObject instances. Returns an empty list, rather
        than raising, when the table has not been created yet.

        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :param path_kwargs: Values to interpolate into table_path.
        :type path_kwargs: dict
        :return: A list of TableObject instances.
        :rtype: List[TableObject]
        '''

        path = self.resolve_table_path(**path_kwargs)

        with self.client() as h5:
            if not h5.node_exists(path):
                return []

            rows = h5.read_rows(path, condition=condition)

        return [self.table_cls.from_row(row) for row in rows]

    # * method: iter_list
    def iter_list(self, condition: Optional[str] = None, **path_kwargs) -> Iterator[TableObject]:
        '''
        Lazily stream rows matching condition (or every row, when omitted)
        as TableObject instances, without materializing the full result
        set in memory -- the mixin-level counterpart to H5Client.iter_rows().

        Unlike H5Client.iter_rows(), path resolution and table access are
        deferred to first iteration rather than validated eagerly, since
        this method must keep the underlying client's file handle open for
        the caller's full iteration and therefore cannot use a `with`
        block that closes before returning. Callers who need failures to
        surface immediately should use list() instead. Yields nothing,
        rather than raising, when the table has not been created yet.

        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :param path_kwargs: Values to interpolate into table_path.
        :type path_kwargs: dict
        :return: A generator of TableObject instances.
        :rtype: Iterator[TableObject]
        '''

        path = self.resolve_table_path(**path_kwargs)

        with self.client() as h5:
            if not h5.node_exists(path):
                return

            for row in h5.iter_rows(path, condition=condition):
                yield self.table_cls.from_row(row)

    # * method: delete
    def delete(self, condition: str, **path_kwargs) -> int:
        '''
        Remove every row matching condition from this repository's table.

        :param condition: A PyTables condition string identifying rows to delete.
        :type condition: str
        :param path_kwargs: Values to interpolate into table_path.
        :type path_kwargs: dict
        :return: The number of rows removed.
        :rtype: int
        '''

        path = self.resolve_table_path(**path_kwargs)

        with self.client() as h5:
            return h5.remove_rows(path, condition)

    # * method: exists
    def exists(self, condition: str, **path_kwargs) -> bool:
        '''
        Check whether any row matches condition. Returns False, rather
        than raising, when the table has not been created yet.

        :param condition: A PyTables condition string.
        :type condition: str
        :param path_kwargs: Values to interpolate into table_path.
        :type path_kwargs: dict
        :return: True if at least one row matches, otherwise False.
        :rtype: bool
        '''

        path = self.resolve_table_path(**path_kwargs)

        with self.client() as h5:
            if not h5.node_exists(path):
                return False

            return len(h5.read_rows(path, condition=condition)) > 0

    # * method: verify
    def verify(self, **path_kwargs) -> None:
        '''
        Explicitly assert that this repository's table still matches
        table_cls's declared schema, raising a structured error on drift.

        Never called automatically by save()/get()/list() -- schema
        enforcement stays opt-in, matching H5Client.assert_schema()'s own
        opt-in design.

        :param path_kwargs: Values to interpolate into table_path.
        :type path_kwargs: dict
        '''

        path = self.resolve_table_path(**path_kwargs)

        with self.client() as h5:
            h5.assert_schema(path, self.table_cls)


# ** repo: node_repository
class NodeRepository:
    '''
    Reusable CRUD mixin for a declared NodeObject class bound to an HDF5
    node path, so a concrete repository stops hand-rolling the same
    to_attrs()/from_attrs() orchestration against set_node_attr()/
    get_node_attrs() on every new attribute-backed domain concept.

    Ships get/save/exists only -- H5Service has no generic node-removal
    primitive (only remove_rows(), which is table-row-specific), and
    adding one is out of scope for this mixin layer. A delete() is a
    natural candidate for a future RFP once a node-removal primitive
    exists on H5Client, not an oversight here.

    Intended to be composed alongside H5Repository (or any class providing
    a compatible client() method), e.g. ``class MyRepo(NodeRepository,
    H5Repository): ...``. Do not also mix in TableRepository on the same
    class -- see TableRepository's docstring for why (shared save()/get()/
    exists() method names would collide under Python's MRO).
    '''

    # * attribute: node_cls
    node_cls: ClassVar[Type[NodeObject]]

    # * attribute: node_path
    node_path: ClassVar[str] = ''

    # * method: resolve_node_path
    def resolve_node_path(self, **path_kwargs) -> str:
        '''
        Resolve the absolute HDF5 path for this repository's node.

        :param path_kwargs: Values to interpolate into node_path.
        :type path_kwargs: dict
        :return: The resolved absolute HDF5 node path.
        :rtype: str
        '''

        # Format only when kwargs are given, so a fixed path needs no braces.
        if path_kwargs:
            return self.node_path.format(**path_kwargs)

        return self.node_path

    # * method: save
    def save(self, obj: NodeObject, **path_kwargs) -> None:
        '''
        Persist obj's attributes onto this repository's node, creating the
        group first if it does not yet exist.

        :param obj: The NodeObject instance to persist.
        :type obj: NodeObject
        :param path_kwargs: Values to interpolate into node_path.
        :type path_kwargs: dict
        '''

        path = self.resolve_node_path(**path_kwargs)

        with self.client() as h5:

            # Create the group on first write; existing nodes are left alone.
            if not h5.node_exists(path):
                h5.create_group(path)

            # Set each serialized attribute individually.
            for name, value in obj.to_attrs().items():
                h5.set_node_attr(path, name, value)

    # * method: get
    def get(self, **path_kwargs) -> Optional[NodeObject]:
        '''
        Return this repository's node as a NodeObject, or None if the
        node (or the underlying file itself) does not exist yet.

        Uses the repository's default client mode (never `'r'`) so a read
        against a not-yet-created file does not raise H5_FILE_NOT_FOUND --
        "nothing here yet" is this method's normal, non-exceptional result.

        :param path_kwargs: Values to interpolate into node_path.
        :type path_kwargs: dict
        :return: The NodeObject instance, or None if not found.
        :rtype: Optional[NodeObject]
        '''

        path = self.resolve_node_path(**path_kwargs)

        with self.client() as h5:
            if not h5.node_exists(path):
                return None

            attrs = h5.get_node_attrs(path)

        return self.node_cls.from_attrs(attrs)

    # * method: exists
    def exists(self, **path_kwargs) -> bool:
        '''
        Check whether this repository's node currently exists. Returns
        False, rather than raising, when the underlying file itself does
        not exist yet.

        :param path_kwargs: Values to interpolate into node_path.
        :type path_kwargs: dict
        :return: True if the node exists, otherwise False.
        :rtype: bool
        '''

        path = self.resolve_node_path(**path_kwargs)

        with self.client() as h5:
            return h5.node_exists(path)
