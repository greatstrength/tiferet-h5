"""tiferet_h5 Repos H5 Tests"""

# *** imports

# ** core
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet.interfaces import Service, ServiceError

from ...utils import H5Client
from ...utils.h5 import H5_FILE_NOT_FOUND_ID
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

# ** test: file_exists_missing_path
def test_file_exists_missing_path(repo: H5Repository, h5_path: str) -> None:
    '''
    Test that file_exists() is False for a missing path and does not create it.
    '''
    assert repo.file_exists() is False
    assert Path(h5_path).exists() is False

# ** test: file_exists_existing_file_does_not_open
def test_file_exists_existing_file_does_not_open(
        repo: H5Repository,
        h5_path: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
    '''
    Test that file_exists() is True for an on-disk path and does not open it.
    '''

    # Place a non-HDF5 payload so an open would fail.
    Path(h5_path).write_bytes(b'not an hdf5 file')

    # Fail the test if file_exists constructs a client.
    def fail_client(*args, **kwargs):
        raise AssertionError('file_exists must not open an H5Client.')

    monkeypatch.setattr('tiferet_h5.repos.h5.H5Client', fail_client)

    # Stat the path without opening it.
    assert repo.file_exists() is True
    assert Path(h5_path).read_bytes() == b'not an hdf5 file'

# ** test: file_exists_ignores_extension
def test_file_exists_ignores_extension(tmp_path: Path) -> None:
    '''
    Test that file_exists() does not require a .h5 extension.
    '''
    path = tmp_path / 'notes.txt'
    path.write_text('present')
    repo = H5Repository(h5_file=str(path))

    assert repo.file_exists() is True

# ** test: h5client_read_missing_raises_file_not_found
def test_h5client_read_missing_raises_file_not_found(h5_path: str) -> None:
    '''
    Test that read mode against a missing path still raises H5_FILE_NOT_FOUND.
    '''
    with pytest.raises(ServiceError) as exc_info:
        with H5Client(path=h5_path, mode='r'):
            pass

    assert exc_info.value.error_code == H5_FILE_NOT_FOUND_ID
    assert exc_info.value.error_code == 'H5_FILE_NOT_FOUND'
    assert Path(h5_path).exists() is False
