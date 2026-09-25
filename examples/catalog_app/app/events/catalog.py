"""Catalog example domain events."""

# *** imports

# ** app
from tiferet.events import DomainEvent

from ..interfaces.catalog import CatalogItemService, CatalogMetaService
from ..mappers.catalog import (
    CatalogItemAggregate,
    CatalogItemTableObject,
    CatalogMetaNodeObject,
)

# *** constants

# ** constant: catalog_item_exists_id
CATALOG_ITEM_EXISTS_ID = 'CATALOG_ITEM_EXISTS'

# ** constant: catalog_item_not_found_id
CATALOG_ITEM_NOT_FOUND_ID = 'CATALOG_ITEM_NOT_FOUND'

# ** constant: catalog_item_price_invalid_id
CATALOG_ITEM_PRICE_INVALID_ID = 'CATALOG_ITEM_PRICE_INVALID'

# ** constant: catalog_discount_invalid_id
CATALOG_DISCOUNT_INVALID_ID = 'CATALOG_DISCOUNT_INVALID'

# ** constant: catalog_meta_currency_empty_id
CATALOG_META_CURRENCY_EMPTY_ID = 'CATALOG_META_CURRENCY_EMPTY'

# ** constant: catalog_meta_not_found_id
CATALOG_META_NOT_FOUND_ID = 'CATALOG_META_NOT_FOUND'

# *** functions

# ** function: sku_condition
def sku_condition(sku: str) -> str:
    '''
    Build a PyTables condition that matches one sku.

    String columns compare against bytes literals, not Python strings.

    :param sku: The stock-keeping unit to match.
    :type sku: str
    :return: A condition string for the sku column.
    :rtype: str
    '''

    # Escape quotes so a sku cannot break out of the bytes literal.
    escaped = sku.replace('\\', '\\\\').replace('"', '\\"')

    # Return the in-kernel comparison.
    return f'sku == b"{escaped}"'
# *** events

# ** event: catalog_item_event
class CatalogItemEvent(DomainEvent):
    '''
    Shared item-service dependency for catalog item events.

    Concrete events take the service interface, not the repository class.
    '''

    # * attribute: catalog_item_service
    catalog_item_service: CatalogItemService

    # * init
    def __init__(self, catalog_item_service: CatalogItemService) -> None:
        '''
        Initialize the event with the item service.

        :param catalog_item_service: The item service.
        :type catalog_item_service: CatalogItemService
        '''

        # Store the injected item service.
        self.catalog_item_service = catalog_item_service

# ** event: catalog_meta_event
class CatalogMetaEvent(DomainEvent):
    '''
    Shared meta-service dependency for catalog label events.
    '''

    # * attribute: catalog_meta_service
    catalog_meta_service: CatalogMetaService

    # * init
    def __init__(self, catalog_meta_service: CatalogMetaService) -> None:
        '''
        Initialize the event with the meta service.

        :param catalog_meta_service: The meta service.
        :type catalog_meta_service: CatalogMetaService
        '''

        # Store the injected meta service.
        self.catalog_meta_service = catalog_meta_service

# ** event: add_catalog_item
class AddCatalogItem(CatalogItemEvent):
    '''
    Append a catalog item when its sku is not already stored.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['sku', 'name', 'price'])
    def execute(self, sku: str, name: str, price: float, **kwargs) -> CatalogItemTableObject:
        '''
        Reject a duplicate sku and append the item.

        :param sku: The stock-keeping unit.
        :type sku: str
        :param name: The display name.
        :type name: str
        :param price: The unit price.
        :type price: float
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The stored table object.
        :rtype: CatalogItemTableObject
        '''

        # Reject a sku that already has a row.
        existing = self.catalog_item_service.get(sku_condition(sku))
        self.verify(
            existing is None,
            CATALOG_ITEM_EXISTS_ID,
            f'Catalog item already exists: {sku}',
            sku=sku,
        )

        # Map the new item and append it.
        item = CatalogItemAggregate(sku=sku, name=name, price=price)
        stored = CatalogItemTableObject.from_model(item)
        self.catalog_item_service.save(stored)

        # Return the stored row.
        return stored

# ** event: list_catalog_items
class ListCatalogItems(CatalogItemEvent):
    '''
    Return the current catalog item rows.
    '''

    # * method: execute
    def execute(self, **kwargs) -> list:
        '''
        Return every stored item row.

        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The current rows.
        :rtype: list
        '''

        # Return the rows the item service currently holds.
        return self.catalog_item_service.list()

# ** event: apply_item_discount
class ApplyItemDiscount(CatalogItemEvent):
    '''
    Replace an item row with a discounted price.

    The table mixin appends. A price change therefore deletes the old row
    and saves the new one.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['sku', 'discount'])
    def execute(self, sku: str, discount: float, **kwargs) -> CatalogItemAggregate:
        '''
        Reject a missing item, a non-positive price, or a discount outside 0 to 1.

        :param sku: The stock-keeping unit to discount.
        :type sku: str
        :param discount: The fraction to remove, from 0 through 1.
        :type discount: float
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The discounted item.
        :rtype: CatalogItemAggregate
        '''

        # Load the current row and reject a missing sku.
        item = self.catalog_item_service.get(sku_condition(sku))
        self.verify(
            item is not None,
            CATALOG_ITEM_NOT_FOUND_ID,
            f'Catalog item not found: {sku}',
            sku=sku,
        )

        # Reject a price that cannot be discounted.
        self.verify(
            item.price > 0,
            CATALOG_ITEM_PRICE_INVALID_ID,
            f'Catalog item price must be positive: {sku}',
            sku=sku,
            price=item.price,
        )

        # Reject a discount outside the closed unit interval.
        self.verify(
            0 <= discount <= 1,
            CATALOG_DISCOUNT_INVALID_ID,
            f'Discount must be from 0 to 1: {discount}',
            sku=sku,
            discount=discount,
        )

        # Apply the discount on the mutable item.
        discounted = item.map(CatalogItemAggregate)
        discounted.set_attribute('price', item.price * (1.0 - discount))

        # Delete the old row, then append the new price.
        removed = self.catalog_item_service.delete(sku_condition(sku))
        self.verify(
            removed == 1,
            CATALOG_ITEM_NOT_FOUND_ID,
            f'Catalog item not found: {sku}',
            sku=sku,
        )
        self.catalog_item_service.save(CatalogItemTableObject.from_model(discounted))

        # Return the discounted item.
        return discounted

# ** event: remove_catalog_item
class RemoveCatalogItem(CatalogItemEvent):
    '''
    Remove a catalog item by sku.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['sku'])
    def execute(self, sku: str, **kwargs) -> int:
        '''
        Reject a missing sku and delete the matching row.

        :param sku: The stock-keeping unit to remove.
        :type sku: str
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The number of rows removed.
        :rtype: int
        '''

        # Reject a sku that is not stored.
        existing = self.catalog_item_service.get(sku_condition(sku))
        self.verify(
            existing is not None,
            CATALOG_ITEM_NOT_FOUND_ID,
            f'Catalog item not found: {sku}',
            sku=sku,
        )

        # Delete the matching row.
        return self.catalog_item_service.delete(sku_condition(sku))

# ** event: save_catalog_meta
class SaveCatalogMeta(CatalogMetaEvent):
    '''
    Store catalog title and currency on the meta node.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['title'])
    def execute(self, title: str, currency: str = None, **kwargs) -> CatalogMetaNodeObject:
        '''
        Reject an empty currency and write the labels.

        Currency is checked here rather than by ``parameters_required`` so a
        blank value raises the catalog error code.

        :param title: The catalog title.
        :type title: str
        :param currency: The currency code. Blank values are rejected.
        :type currency: str
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The stored node object.
        :rtype: CatalogMetaNodeObject
        '''

        # Reject a missing or blank currency.
        self.verify(
            isinstance(currency, str) and currency.strip() != '',
            CATALOG_META_CURRENCY_EMPTY_ID,
            'Catalog currency must not be empty.',
            currency=currency,
        )

        # Write the labels through the node object.
        meta = CatalogMetaNodeObject(title=title, currency=currency)
        self.catalog_meta_service.save(meta)

        # Return the stored labels.
        return meta

# ** event: get_catalog_meta
class GetCatalogMeta(CatalogMetaEvent):
    '''
    Return the stored catalog labels.
    '''

    # * method: execute
    def execute(self, **kwargs) -> CatalogMetaNodeObject:
        '''
        Return the meta node, or raise not-found.

        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The stored labels.
        :rtype: CatalogMetaNodeObject
        '''

        # Load the node and reject a missing catalog.
        meta = self.catalog_meta_service.get()
        self.verify(
            meta is not None,
            CATALOG_META_NOT_FOUND_ID,
            'Catalog meta was not found.',
        )

        # Return the stored labels.
        return meta

# ** event: verify_and_compact_catalog
class VerifyAndCompactCatalog(CatalogItemEvent):
    '''
    Check the item table schema, then rewrite the file.

    Schema assertion is opt-in. Ordinary saves do not call it. Compaction
    reclaims rows deleted by a discount or a removal.
    '''

    # * method: execute
    def execute(self, **kwargs) -> None:
        '''
        Call ``assert_schema`` for the item table, then ``compact``.

        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        '''

        # Resolve the item table path from the service.
        path = self.catalog_item_service.resolve_table_path()

        # Assert the live schema, then rewrite the open file.
        with self.catalog_item_service.client() as h5:
            h5.assert_schema(path, self.catalog_item_service.table_cls)
            h5.compact()
