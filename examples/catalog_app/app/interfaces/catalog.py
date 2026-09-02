"""Catalog App Interfaces"""

# *** imports

# ** core
from abc import abstractmethod
from typing import List, Optional

# ** app
from tiferet.interfaces import Service

from app.mappers.catalog import CatalogItemTableObject, CatalogMetaNodeObject

# *** interfaces

# ** interface: catalog_item_service
class CatalogItemService(Service):
    '''
    Service interface for managing catalog items.
    '''

    # * method: exists
    @abstractmethod
    def exists(self, condition: str) -> bool:
        '''
        Check if any catalog item matches condition.

        :param condition: A PyTables condition string.
        :type condition: str
        :return: True if at least one item matches, otherwise False.
        :rtype: bool
        '''
        raise NotImplementedError('exists method is required for CatalogItemService.')

    # * method: get
    @abstractmethod
    def get(self, condition: str) -> Optional[CatalogItemTableObject]:
        '''
        Retrieve the first catalog item matching condition.

        :param condition: A PyTables condition string identifying one item.
        :type condition: str
        :return: The matching catalog item, or None if not found.
        :rtype: Optional[CatalogItemTableObject]
        '''
        raise NotImplementedError('get method is required for CatalogItemService.')

    # * method: list
    @abstractmethod
    def list(self, condition: Optional[str] = None) -> List[CatalogItemTableObject]:
        '''
        List all catalog items, optionally filtered by condition.

        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :return: A list of catalog items.
        :rtype: List[CatalogItemTableObject]
        '''
        raise NotImplementedError('list method is required for CatalogItemService.')

    # * method: save
    @abstractmethod
    def save(self, item: CatalogItemTableObject) -> None:
        '''
        Persist a catalog item as a new row.

        :param item: The catalog item to persist.
        :type item: CatalogItemTableObject
        :return: None
        :rtype: None
        '''
        raise NotImplementedError('save method is required for CatalogItemService.')

    # * method: delete
    @abstractmethod
    def delete(self, condition: str) -> int:
        '''
        Remove every catalog item matching condition. Idempotent.

        :param condition: A PyTables condition string identifying items to remove.
        :type condition: str
        :return: The number of items removed.
        :rtype: int
        '''
        raise NotImplementedError('delete method is required for CatalogItemService.')

    # * method: verify
    @abstractmethod
    def verify(self) -> None:
        '''
        Assert that the persisted table still matches the declared schema.

        :return: None
        :rtype: None
        '''
        raise NotImplementedError('verify method is required for CatalogItemService.')

# ** interface: catalog_meta_service
class CatalogMetaService(Service):
    '''
    Service interface for managing the catalog's own group-level metadata.
    '''

    # * method: get
    @abstractmethod
    def get(self) -> Optional[CatalogMetaNodeObject]:
        '''
        Retrieve the catalog's metadata.

        :return: The catalog metadata, or None if not yet saved.
        :rtype: Optional[CatalogMetaNodeObject]
        '''
        raise NotImplementedError('get method is required for CatalogMetaService.')

    # * method: save
    @abstractmethod
    def save(self, meta: CatalogMetaNodeObject) -> None:
        '''
        Persist the catalog's metadata.

        :param meta: The catalog metadata to persist.
        :type meta: CatalogMetaNodeObject
        :return: None
        :rtype: None
        '''
        raise NotImplementedError('save method is required for CatalogMetaService.')
