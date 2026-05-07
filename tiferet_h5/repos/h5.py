"""tiferet_h5 Repos H5"""

# *** imports

# ** core
from pathlib import Path

# ** app
from tiferet.interfaces import Service

from ..utils import H5Client

# *** repos

# ** repo: h5_repository
class H5Repository(Service):
    '''
    Generic base repository for HDF5-backed domain stores.

    Provides a common initialiser and a ``client`` factory method that
    concrete repositories use to obtain a short-lived ``H5Client`` context
    manager for each operation.  The default open mode is ``'a'`` (append /
    read-write; creates the file if absent) which is safe for both read and
    write operations without truncating existing data.

    Concrete repositories extend this class, inject ``h5_file`` via the
    constructor, and implement the ``Service`` interface methods appropriate
    to their domain (e.g. ``get``, ``save``, ``delete``, ``exists``, ``list``).
    '''

    # * attribute: h5_file
    h5_file: str

    # * attribute: mode
    mode: str

    # * init
    def __init__(self,
            h5_file: str,
            mode: str = 'a',
        ) -> None:
        '''
        Initialize the H5Repository.

        :param h5_file: Path to the HDF5 file this repository operates on.
        :type h5_file: str
        :param mode: Default PyTables open mode for write operations.
            Defaults to ``'a'`` (append / create-if-absent).
        :type mode: str
        '''

        # Store the file path and default mode.
        self.h5_file = h5_file
        self.mode = mode

    # * method: client
    def client(self, mode: str = None) -> H5Client:
        '''
        Return a new ``H5Client`` instance configured for this repository.

        The client is intended to be used as a context manager so that the
        HDF5 file is opened and closed (with flush) around each operation::

            with self.client() as h5:
                table = h5.get_or_create_table('/my/table', MyDescription)
                ...

        :param mode: Override the default open mode for this call.
            When ``None`` the repository's default ``mode`` is used.
        :type mode: str
        :return: A configured ``H5Client`` instance (not yet open).
        :rtype: H5Client
        '''

        # Return a new client targeting the repository file and mode.
        return H5Client(
            path=Path(self.h5_file),
            mode=mode or self.mode,
        )
