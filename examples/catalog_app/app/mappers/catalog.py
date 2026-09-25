"""Catalog example mappers."""

# *** imports

# ** core
from typing import Any, ClassVar, Dict

# ** infra
import tables

# ** app
from tiferet.mappers import Aggregate
from tiferet_h5 import NodeObject, TableObject

from ..domain.catalog import CatalogItem, CatalogMeta

# *** mappers

# ** mapper: catalog_item_table_object
class CatalogItemTableObject(CatalogItem, TableObject):
    '''
    Row mapping for a catalog item.

    Fields come from ``CatalogItem``. ``_H5_TYPES`` names the HDF5 columns
    those fields occupy. This object does not redeclare the domain fields.
    '''

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'sku': tables.StringCol(64),
        'name': tables.StringCol(128),
        'price': tables.Float64Col(),
    }

# ** mapper: catalog_meta_node_object
class CatalogMetaNodeObject(CatalogMeta, NodeObject):
    '''
    Attribute mapping for catalog labels.

    ``to_attrs`` writes ``title`` and ``currency`` onto the group node.
    Fields are inherited from ``CatalogMeta``.
    '''

# ** mapper: catalog_item_aggregate
class CatalogItemAggregate(CatalogItem, Aggregate):
    '''
    Mutable catalog item.

    Price changes go through ``set_attribute`` on this aggregate. The domain
    object stays the read-only fact, and the table object stays the row mapping.
    '''
