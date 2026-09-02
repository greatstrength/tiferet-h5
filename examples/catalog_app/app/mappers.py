"""Catalog App Mappers"""

# *** imports

# ** core
from typing import Any, ClassVar, Dict

# ** infra
import tables
from pydantic import AliasChoices, Field

# ** app
from tiferet_h5 import NodeObject, TableObject

# *** mappers

# ** mapper: catalog_item_table_object
class CatalogItemTableObject(TableObject):
    '''Row-oriented HDF5 mapper for CatalogItem/CatalogItemAggregate.'''

    # * attribute: sku
    sku: str = Field(default='', description='Stock-keeping unit identifier.')

    # * attribute: name
    name: str = Field(default='', description='Item display name.')

    # * attribute: price
    price: float = Field(default=0.0, description='Item price in dollars.')

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'sku':   tables.StringCol(32),
        'name':  tables.StringCol(128),
        'price': tables.Float64Col(),
    }


# ** mapper: catalog_meta_node_object
class CatalogMetaNodeObject(NodeObject):
    '''Attribute-oriented HDF5 mapper for the catalog's own group-level metadata.'''

    # * attribute: catalog_name
    catalog_name: str = Field(
        default='',
        serialization_alias='name',
        validation_alias=AliasChoices('name', 'catalog_name'),
        description='Catalog display name; stored as "name" in HDF5.',
    )

    # * attribute: currency
    currency: str = Field(default='USD', description='Currency code for item prices.')

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }
