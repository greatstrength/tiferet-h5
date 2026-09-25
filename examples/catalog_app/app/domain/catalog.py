"""Catalog example domain models."""

# *** imports

# ** infra
from pydantic import Field

# ** app
from tiferet import DomainObject

# *** models

# ** model: catalog_item
class CatalogItem(DomainObject):
    '''
    One sellable row in the catalog.

    The item is a read-only domain fact. Persistence and price changes live
    on the mapper and aggregate, not here.
    '''

    # * attribute: sku
    sku: str = Field(..., description='The stock-keeping unit.')

    # * attribute: name
    name: str = Field(..., description='The display name of the item.')

    # * attribute: price
    price: float = Field(..., description='The current unit price.')

# ** model: catalog_meta
class CatalogMeta(DomainObject):
    '''
    Catalog-wide labels stored once, apart from the item rows.

    Title and currency describe the catalog itself. They are not columns on
    the item table.
    '''

    # * attribute: title
    title: str = Field(..., description='The catalog title.')

    # * attribute: currency
    currency: str = Field(..., description='The ISO currency code for item prices.')
