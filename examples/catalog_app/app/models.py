"""Catalog App Models"""

# *** imports

# ** infra
from pydantic import Field

# ** app
from tiferet.domain import DomainObject
from tiferet.mappers import Aggregate

# *** models

# ** model: catalog_item
class CatalogItem(DomainObject):
    '''Read-only domain representation of a single catalog item.'''

    # * attribute: sku
    sku: str = Field(default='', description='Stock-keeping unit identifier.')

    # * attribute: name
    name: str = Field(default='', description='Item display name.')

    # * attribute: price
    price: float = Field(default=0.0, description='Item price in dollars.')


# *** classes

# ** class: catalog_item_aggregate
class CatalogItemAggregate(Aggregate):
    '''Mutable aggregate counterpart to CatalogItem.'''

    # * attribute: sku
    sku: str = Field(default='', description='Stock-keeping unit identifier.')

    # * attribute: name
    name: str = Field(default='', description='Item display name.')

    # * attribute: price
    price: float = Field(default=0.0, description='Item price in dollars.')

    # * method: apply_discount
    def apply_discount(self, percent: float) -> None:
        '''
        Reduce this item's price by percent, rounded to two decimal places.

        :param percent: Discount percentage (e.g. 10 for 10%).
        :type percent: float
        '''

        # Apply the discount and round to a sensible currency precision.
        self.set_attribute('price', round(self.price * (1 - percent / 100), 2))
