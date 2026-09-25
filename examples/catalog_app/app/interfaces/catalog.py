"""Catalog example service interfaces."""

# *** imports

# ** core
from abc import abstractmethod
from typing import List, Optional

# ** app
from tiferet.interfaces import Service

from ..domain.catalog import CatalogItem, CatalogMeta

# *** interfaces

# ** interface: catalog_item_service
class CatalogItemService(Service):
    '''
    Contract for storing catalog items as table rows.

    Events depend on this interface. They do not import the repository class
    that implements it.
    '''

    # * method: save
    @abstractmethod
    def save(self, item: CatalogItem, **path_kwargs) -> None:
        '''
        Append one catalog item.

        :param item: The item to append. Callers pass a table object.
        :type item: CatalogItem
        :param path_kwargs: Optional table-path placeholder values.
        :type path_kwargs: dict
        '''

        raise NotImplementedError('save method is required for CatalogItemService.')

    # * method: get
    @abstractmethod
    def get(self, condition: str, **path_kwargs) -> Optional[CatalogItem]:
        '''
        Return the first item matching a PyTables condition, or None.

        :param condition: PyTables condition string identifying the row.
        :type condition: str
        :param path_kwargs: Optional table-path placeholder values.
        :type path_kwargs: dict
        :return: The matching item, or None.
        :rtype: Optional[CatalogItem]
        '''

        raise NotImplementedError('get method is required for CatalogItemService.')

    # * method: list
    @abstractmethod
    def list(self, condition: Optional[str] = None, **path_kwargs) -> List[CatalogItem]:
        '''
        Return the current item rows, optionally filtered.

        :param condition: Optional PyTables condition string.
        :type condition: Optional[str]
        :param path_kwargs: Optional table-path placeholder values.
        :type path_kwargs: dict
        :return: The matching items.
        :rtype: List[CatalogItem]
        '''

        raise NotImplementedError('list method is required for CatalogItemService.')

    # * method: delete
    @abstractmethod
    def delete(self, condition: str, **path_kwargs) -> int:
        '''
        Remove items matching a PyTables condition.

        :param condition: PyTables condition string identifying rows to delete.
        :type condition: str
        :param path_kwargs: Optional table-path placeholder values.
        :type path_kwargs: dict
        :return: The number of rows removed.
        :rtype: int
        '''

        raise NotImplementedError('delete method is required for CatalogItemService.')

# ** interface: catalog_meta_service
class CatalogMetaService(Service):
    '''
    Contract for storing catalog labels as node attributes.

    This is a separate service from the item table. One class does not
    implement both storage shapes.
    '''

    # * method: save
    @abstractmethod
    def save(self, meta: CatalogMeta, **path_kwargs) -> None:
        '''
        Write catalog labels onto the meta node.

        :param meta: The labels to store. Callers pass a node object.
        :type meta: CatalogMeta
        :param path_kwargs: Optional node-path placeholder values.
        :type path_kwargs: dict
        '''

        raise NotImplementedError('save method is required for CatalogMetaService.')

    # * method: get
    @abstractmethod
    def get(self, **path_kwargs) -> Optional[CatalogMeta]:
        '''
        Return the stored catalog labels, or None when the node is absent.

        :param path_kwargs: Optional node-path placeholder values.
        :type path_kwargs: dict
        :return: The stored labels, or None.
        :rtype: Optional[CatalogMeta]
        '''

        raise NotImplementedError('get method is required for CatalogMetaService.')
