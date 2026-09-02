"""tiferet_h5 — HDF5 Infrastructure Extension for the Tiferet Framework"""

# *** exports

# ** app
# Wrap runtime imports in a try/except so that build tools can import
# __version__ without requiring the full dependency tree to be installed.
try:
    from .domain import H5Column, H5TableSchema, H5Node
    from .interfaces import H5Service
    from .mappers import TableObject, NodeObject
    from .utils import H5Client, H5Client as H5
    from .repos import H5Repository
except Exception as e:
    import os, sys
    if not os.getenv('TIFERET_H5_SILENT_IMPORTS'):
        print(f'Warning: Failed to import tiferet_h5 modules: {e}', file=sys.stderr)

# *** version

__version__ = '1.0.0a4'
