"""Catalog example repositories."""

# *** imports

# ** core
from typing import ClassVar, Optional

# ** infra
import tables

# ** app
from tiferet_h5 import H5Repository, NodeRepository, TableRepository

from ..interfaces.catalog import CatalogItemService, CatalogMetaService
from ..mappers.catalog import CatalogItemTableObject, CatalogMetaNodeObject

# *** constants

# ** constant: catalog_items_path
CATALOG_ITEMS_PATH = '/catalog/items'

# ** constant: catalog_meta_path
CATALOG_META_PATH = '/catalog'

# *** repos

# ** repo: catalog_items_repository
class CatalogItemsRepository(TableRepository, CatalogItemService, H5Repository):
    '''
    Table-backed store for catalog items.

    This class is only a table repository. It does not also inherit
    ``NodeRepository``. ``TableRepository`` is listed before the service
    interface so the mixin implementation is the one that runs.
    '''

    # * attribute: table_cls
    table_cls: ClassVar[type] = CatalogItemTableObject

    # * attribute: table_path
    table_path: ClassVar[str] = CATALOG_ITEMS_PATH

    # * attribute: filters
    filters: ClassVar[Optional[tables.Filters]] = tables.Filters(complevel=1)

# ** repo: catalog_meta_repository
class CatalogMetaRepository(NodeRepository, CatalogMetaService, H5Repository):
    '''
    Attribute-backed store for catalog labels.

    This is a second repository class on the same HDF5 file, not a second
    mixin on ``CatalogItemsRepository``. ``save``, ``get``, and ``exists``
    would collide if both mixins were composed on one class.
    '''

    # * attribute: node_cls
    node_cls: ClassVar[type] = CatalogMetaNodeObject

    # * attribute: node_path
    node_path: ClassVar[str] = CATALOG_META_PATH
