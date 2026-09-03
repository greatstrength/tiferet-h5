"""tiferet_h5 Mapper Tests Conftest"""

# *** functions

# ** function: pytest_generate_tests
def pytest_generate_tests(metafunc):
    '''
    Reserved hook for future TableObjectTestBase/NodeObjectTestBase
    parametrization (e.g. a set_attribute-style test), mirroring the
    registration point core Tiferet's own conftest hooks use.

    :param metafunc: The pytest metafunc object.
    :type metafunc: object
    '''

    # No parametrized tests are registered yet; reserved for future harness growth.
    pass
