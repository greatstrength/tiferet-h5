"""tiferet_h5 Repos H5 Tests"""

# *** imports

# ** core
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet.interfaces import Service

from ...utils import H5Client
from ..h5 import H5Repository

# *** fixtures

# ** fixture: h5_path
@pytest.fixture
def h5_path(tmp_path: Path) -> str:
    '''
    Return a path string to a temporary HDF5 file (does not yet exist).
    '''
    return str(tmp_path / 'repo_test.h5')


# ** fixture: repo
@pytest.fixture
def repo(h5_path: str) -> H5Repository:
    '''
    Return an H5Repository instance with default mode.
    '''
    return H5Repository(h5_file=h5_path)


# *** tests

# ** test: h5_repository_is_service_subclass
def test_h5_repository_is_service_subclass() -> None:
    '''
    Test that H5Repository is a subclass of tiferet.interfaces.Service.
    '''
    assert issubclass(H5Repository, Service)


# ** test: h5_repository_init_stores_attributes
def test_h5_repository_init_stores_attributes(h5_path: str) -> None:
    '''
    Test that the constructor stores h5_file and mode attributes.
    '''
    repo = H5Repository(h5_file=h5_path, mode='r')

    assert repo.h5_file == h5_path
    assert repo.mode == 'r'


# ** test: h5_repository_default_mode
def test_h5_repository_default_mode(repo: H5Repository) -> None:
    '''
    Test that the default mode is 'a'.
    '''
    assert repo.mode == 'a'


# ** test: client_returns_h5client
def test_client_returns_h5client(repo: H5Repository) -> None:
    '''
    Test that client() returns an H5Client instance.
    '''
    client = repo.client()

    assert isinstance(client, H5Client)


# ** test: client_uses_repo_path_and_mode
def test_client_uses_repo_path_and_mode(repo: H5Repository) -> None:
    '''
    Test that client() configures the H5Client with the repository's path and mode.
    '''
    client = repo.client()

    assert str(client.path) == str(Path(repo.h5_file))
    assert client.mode == repo.mode


# ** test: client_mode_override
def test_client_mode_override(repo: H5Repository) -> None:
    '''
    Test that client(mode='r') overrides the default mode for that call.
    '''
    client = repo.client(mode='r')

    assert client.mode == 'r'


# ** test: client_not_yet_open
def test_client_not_yet_open(repo: H5Repository) -> None:
    '''
    Test that the returned client is not yet open (h5file is None).
    '''
    client = repo.client()

    assert client.h5file is None


# ** test: client_works_as_context_manager
def test_client_works_as_context_manager(repo: H5Repository) -> None:
    '''
    Test that the client returned by client() works as a context manager.
    '''
    with repo.client() as h5:
        assert h5.h5file is not None
        assert h5.node_exists('/')

    assert h5.h5file is None
