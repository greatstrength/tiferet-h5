"""Catalog App Domain"""

# *** imports

# ** infra
from pydantic import Field

# ** app
from tiferet.domain import DomainObject

# *** models

# ** model: catalog_item
class CatalogItem(DomainObject):
    '''
    Read-only domain representation of a single catalog item.
    '''

    # * attribute: sku
    sku: str = Field(default='', description='Stock-keeping unit identifier.')

    # * attribute: name
    name: str = Field(default='', description='Item display name.')

    # * attribute: price
    price: float = Field(default=0.0, description='Item price in dollars.')

# ** model: catalog_meta
class CatalogMeta(DomainObject):
    '''
    Read-only domain representation of the catalog's own group-level metadata.
    '''

    # * attribute: catalog_name
    catalog_name: str = Field(default='', description='Catalog display name.')

    # * attribute: currency
    currency: str = Field(default='USD', description='Currency code for item prices.')
