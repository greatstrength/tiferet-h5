# Catalog App

A small consumer of `tiferet-h5`. It stores items in a table and catalog labels on a group node, then runs those operations through Tiferet's `App.run` path.

## Two repositories, one file

`CatalogItemsRepository` and `CatalogMetaRepository` are separate classes. Both are pointed at `catalog.h5`.

- The item repository composes `TableRepository`. Rows live at `/catalog/items`.
- The meta repository composes `NodeRepository`. `title` and `currency` are attributes on `/catalog`.

Do not inherit both mixins on one class. `save`, `get`, and `exists` collide under the method resolution order, so one implementation would hide the other. Two instances on one file keep each storage shape intact.

`catalog_client.py` does not construct either repository. `App('catalog_client')` loads `config.yml`, and each feature resolves the service it needs.

## Run

From this directory, with `tiferet` and `tiferet-h5` installed:

```bash
python catalog_client.py
```

The script calls `app.run` for each catalog feature: add, list, discount, save meta, get meta, verify and compact, then remove. The last step deletes the row, so a later run starts from an empty table. Generated `catalog.h5` is not committed.
