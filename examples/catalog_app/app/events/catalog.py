"""Catalog App Events"""

# *** imports

# ** core
from typing import List, Optional

# ** app
from tiferet.events import DomainEvent

from app.interfaces.catalog import CatalogItemService, CatalogMetaService
from app.mappers.catalog import CatalogItemAggregate, CatalogItemTableObject, CatalogMetaNodeObject

# *** events

# ** event: add_catalog_item
class AddCatalogItem(DomainEvent):
    '''
    A domain event to add a new catalog item.
    '''

    # * init
    def __init__(self, catalog_item_service: CatalogItemService) -> None:
        '''
        Initialize the event with its service dependency.

        :param catalog_item_service: The catalog item service.
        :type catalog_item_service: CatalogItemService
        '''

        # Store the injected service dependency.
        self.catalog_item_service = catalog_item_service

    # * method: execute
    @DomainEvent.parameters_required(['sku', 'name'])
    def execute(self, sku: str, name: str, price: float = 0.0, **kwargs) -> CatalogItemTableObject:
        '''
        Execute the add-catalog-item event.

        :param sku: The stock-keeping unit identifier.
        :type sku: str
        :param name: The item display name.
        :type name: str
        :param price: The item price in dollars.
        :type price: float
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The newly saved catalog item.
        :rtype: CatalogItemTableObject
        '''

        # Verify the SKU is not already taken.
        self.verify(
            not self.catalog_item_service.exists(f'sku == b"{sku}"'),
            'CATALOG_ITEM_ALREADY_EXISTS',
            f'A catalog item with sku {sku} already exists.',
            sku=sku,
        )

        # Verify the price is non-negative.
        self.verify(
            price >= 0,
            'INVALID_PRICE',
            f'Price must be non-negative, got {price}.',
            price=price,
        )

        # Build and save the new catalog item.
        item = CatalogItemTableObject(sku=sku, name=name, price=price)
        self.catalog_item_service.save(item)

        # Return the newly saved item.
        return item

# ** event: list_catalog_items
class ListCatalogItems(DomainEvent):
    '''
    A domain event to list every catalog item.

    Kept as a thin passthrough, deliberately with no extra validation --
    not every event needs to enforce a domain rule (mirrors calc.history).
    '''

    # * init
    def __init__(self, catalog_item_service: CatalogItemService) -> None:
        '''
        Initialize the event with its service dependency.

        :param catalog_item_service: The catalog item service.
        :type catalog_item_service: CatalogItemService
        '''

        # Store the injected service dependency.
        self.catalog_item_service = catalog_item_service

    # * method: execute
    def execute(self, **kwargs) -> List[CatalogItemTableObject]:
        '''
        Execute the list-catalog-items event.

        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: Every persisted catalog item.
        :rtype: List[CatalogItemTableObject]
        '''

        # Return every persisted catalog item.
        return self.catalog_item_service.list()

# ** event: apply_item_discount
class ApplyItemDiscount(DomainEvent):
    '''
    A domain event to apply a percentage discount to an existing catalog item.
    '''

    # * init
    def __init__(self, catalog_item_service: CatalogItemService) -> None:
        '''
        Initialize the event with its service dependency.

        :param catalog_item_service: The catalog item service.
        :type catalog_item_service: CatalogItemService
        '''

        # Store the injected service dependency.
        self.catalog_item_service = catalog_item_service

    # * method: execute
    @DomainEvent.parameters_required(['sku'])
    def execute(self, sku: str, percent: float = 0.0, **kwargs) -> CatalogItemAggregate:
        '''
        Execute the apply-item-discount event.

        HDF5 table rows are append-only -- there is no in-place row update --
        so this event demonstrates the real pattern such storage requires:
        read the row, mutate it as an Aggregate, delete the stale row, then
        save a fresh row built from the mutated aggregate.

        :param sku: The stock-keeping unit identifier of the item to discount.
        :type sku: str
        :param percent: The discount percentage (e.g. 10 for 10%).
        :type percent: float
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The discounted item as an Aggregate.
        :rtype: CatalogItemAggregate
        '''

        # Verify the item exists.
        item = self.catalog_item_service.get(f'sku == b"{sku}"')
        self.verify(
            item is not None,
            'CATALOG_ITEM_NOT_FOUND',
            f'No catalog item found with sku {sku}.',
            sku=sku,
        )

        # Verify the discount percentage is within bounds.
        self.verify(
            0 <= percent <= 100,
            'INVALID_DISCOUNT_PERCENT',
            f'Discount percent must be between 0 and 100, got {percent}.',
            percent=percent,
        )

        # Map the row to a mutable aggregate and apply the discount.
        aggregate = item.map(CatalogItemAggregate)
        aggregate.apply_discount(percent)

        # Replace the stale row with a fresh one built from the aggregate.
        self.catalog_item_service.delete(f'sku == b"{sku}"')
        self.catalog_item_service.save(CatalogItemTableObject.from_model(aggregate))

        # Return the discounted aggregate.
        return aggregate

# ** event: remove_catalog_item
class RemoveCatalogItem(DomainEvent):
    '''
    A domain event to remove an existing catalog item.
    '''

    # * init
    def __init__(self, catalog_item_service: CatalogItemService) -> None:
        '''
        Initialize the event with its service dependency.

        :param catalog_item_service: The catalog item service.
        :type catalog_item_service: CatalogItemService
        '''

        # Store the injected service dependency.
        self.catalog_item_service = catalog_item_service

    # * method: execute
    @DomainEvent.parameters_required(['sku'])
    def execute(self, sku: str, **kwargs) -> int:
        '''
        Execute the remove-catalog-item event.

        Verifies the item exists first, for a friendlier not-found error
        than the underlying repository's own silent idempotent delete().

        :param sku: The stock-keeping unit identifier of the item to remove.
        :type sku: str
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The number of items removed.
        :rtype: int
        '''

        # Verify the item exists before removing it.
        self.verify(
            self.catalog_item_service.exists(f'sku == b"{sku}"'),
            'CATALOG_ITEM_NOT_FOUND',
            f'No catalog item found with sku {sku}.',
            sku=sku,
        )

        # Remove the item and return the number of rows removed.
        return self.catalog_item_service.delete(f'sku == b"{sku}"')

# ** event: verify_and_compact_catalog
class VerifyAndCompactCatalog(DomainEvent):
    '''
    A domain event that asserts schema integrity and reclaims freed space.

    Wraps two direct H5Client primitives -- verify() (RFP-002, opt-in schema
    enforcement) and a raw compact() call via the service's own client()
    (RFP-004) -- behind an event boundary, so the client script exercises
    the events layer even for these lower-level, whole-file operations.
    '''

    # * init
    def __init__(self, catalog_item_service: CatalogItemService) -> None:
        '''
        Initialize the event with its service dependency.

        :param catalog_item_service: The catalog item service.
        :type catalog_item_service: CatalogItemService
        '''

        # Store the injected service dependency.
        self.catalog_item_service = catalog_item_service

    # * method: execute
    def execute(self, **kwargs) -> None:
        '''
        Execute the verify-and-compact-catalog event.

        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: None
        :rtype: None
        '''

        # Assert the persisted table still matches the declared schema.
        self.catalog_item_service.verify()

        # Reclaim space freed by any prior deletions.
        with self.catalog_item_service.client() as h5:
            h5.compact()

# ** event: save_catalog_meta
class SaveCatalogMeta(DomainEvent):
    '''
    A domain event to save the catalog's own group-level metadata.
    '''

    # * init
    def __init__(self, catalog_meta_service: CatalogMetaService) -> None:
        '''
        Initialize the event with its service dependency.

        :param catalog_meta_service: The catalog meta service.
        :type catalog_meta_service: CatalogMetaService
        '''

        # Store the injected service dependency.
        self.catalog_meta_service = catalog_meta_service

    # * method: execute
    @DomainEvent.parameters_required(['catalog_name'])
    def execute(self, catalog_name: str, currency: str = 'USD', **kwargs) -> CatalogMetaNodeObject:
        '''
        Execute the save-catalog-meta event.

        :param catalog_name: The catalog display name.
        :type catalog_name: str
        :param currency: The currency code for item prices.
        :type currency: str
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The saved catalog metadata.
        :rtype: CatalogMetaNodeObject
        '''

        # Verify the currency code looks like a real 3-letter code.
        self.verify(
            len(currency) == 3,
            'INVALID_CURRENCY_CODE',
            f'Currency code must be exactly 3 letters, got "{currency}".',
            currency=currency,
        )

        # Build and save the catalog metadata.
        meta = CatalogMetaNodeObject(catalog_name=catalog_name, currency=currency)
        self.catalog_meta_service.save(meta)

        # Return the saved metadata.
        return meta

# ** event: get_catalog_meta
class GetCatalogMeta(DomainEvent):
    '''
    A domain event to retrieve the catalog's own group-level metadata.
    '''

    # * init
    def __init__(self, catalog_meta_service: CatalogMetaService) -> None:
        '''
        Initialize the event with its service dependency.

        :param catalog_meta_service: The catalog meta service.
        :type catalog_meta_service: CatalogMetaService
        '''

        # Store the injected service dependency.
        self.catalog_meta_service = catalog_meta_service

    # * method: execute
    def execute(self, **kwargs) -> Optional[CatalogMetaNodeObject]:
        '''
        Execute the get-catalog-meta event.

        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The catalog metadata.
        :rtype: Optional[CatalogMetaNodeObject]
        '''

        # Verify the catalog metadata has already been saved.
        meta = self.catalog_meta_service.get()
        self.verify(
            meta is not None,
            'CATALOG_META_NOT_FOUND',
            'Catalog metadata has not been saved yet.',
        )

        # Return the catalog metadata.
        return meta
