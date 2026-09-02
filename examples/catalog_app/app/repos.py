"""Catalog App Repos"""

# *** imports

# ** infra
import tables

# ** app
from tiferet_h5 import H5Repository, NodeRepository, TableRepository

from app.mappers import CatalogItemTableObject, CatalogMetaNodeObject

# *** repos

# ** repo: catalog_items_repository
class CatalogItemsRepository(TableRepository, H5Repository):
    '''
    TableRepository half of the catalog's two-repository composition.

    Sets a repository-level `filters` default (RFP-004/RFP-005) so every
    item written through this repository is compressed automatically,
    without any save() call site needing to pass filters= itself.
    '''

    # * attribute: table_cls
    table_cls = CatalogItemTableObject

    # * attribute: table_path
    table_path = '/catalog/items'

    # * attribute: filters
    filters = tables.Filters(complib='zlib', complevel=5)


# ** repo: catalog_meta_repository
class CatalogMetaRepository(NodeRepository, H5Repository):
    '''
    NodeRepository half of the catalog's two-repository composition.

    Deliberately a *separate* repository instance from CatalogItemsRepository
    rather than a class multiply-inheriting both mixins -- see
    docs/guides/repos.md for why that would silently collide under Python's
    MRO. Both repositories are bound to the same underlying HDF5 file.
    '''

    # * attribute: node_cls
    node_cls = CatalogMetaNodeObject

    # * attribute: node_path
    node_path = '/catalog'
