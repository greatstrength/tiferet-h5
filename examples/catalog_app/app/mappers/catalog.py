"""Catalog App Mappers"""

# *** imports

# ** core
from typing import Any, ClassVar, Dict

# ** infra
import tables
from pydantic import AliasChoices, Field

# ** app
from tiferet.mappers import Aggregate
from tiferet_h5 import NodeObject, TableObject

from app.domain.catalog import CatalogItem, CatalogMeta

# *** mappers

# ** mapper: catalog_item_table_object
class CatalogItemTableObject(CatalogItem, TableObject):
    '''
    Row-oriented HDF5 mapper for CatalogItem. Inherits sku/name/price from
    CatalogItem rather than redeclaring them, mirroring how core tiferet's
    FormulaConfigObject(Formula, TransferObject) reuses its domain object's
    field declarations.
    '''

    # * attribute: _H5_TYPES
    _H5_TYPES: ClassVar[Dict[str, Any]] = {
        'sku':   tables.StringCol(32),
        'name':  tables.StringCol(128),
        'price': tables.Float64Col(),
    }

# ** mapper: catalog_meta_node_object
class CatalogMetaNodeObject(CatalogMeta, NodeObject):
    '''
    Attribute-oriented HDF5 mapper for the catalog's own group-level metadata.
    Inherits catalog_name/currency from CatalogMeta, overriding catalog_name's
    alias so it is stored as "name" in HDF5.
    '''

    # * attribute: catalog_name
    catalog_name: str = Field(
        default='',
        serialization_alias='name',
        validation_alias=AliasChoices('name', 'catalog_name'),
        description='Catalog display name; stored as "name" in HDF5.',
    )

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_h5.attrs': {'by_alias': True, 'exclude_none': True},
    }

# ** mapper: catalog_item_aggregate
class CatalogItemAggregate(CatalogItem, Aggregate):
    '''
    Mutable aggregate counterpart to CatalogItem. Inherits sku/name/price
    from CatalogItem rather than redeclaring them, mirroring core tiferet's
    FormulaAggregate(Formula, Aggregate).
    '''

    # * method: apply_discount
    def apply_discount(self, percent: float) -> None:
        '''
        Reduce this item's price by percent, rounded to two decimal places.

        :param percent: Discount percentage (e.g. 10 for 10%).
        :type percent: float
        '''

        # Apply the discount and round to a sensible currency precision.
        self.set_attribute('price', round(self.price * (1 - percent / 100), 2))
