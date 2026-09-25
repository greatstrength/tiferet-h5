"""tiferet_h5 Mapper Test Harness"""

# *** imports

# ** core
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Optional, Type

# ** infra
import pytest
import tables

# ** app
from tiferet.domain import DomainObject
from tiferet.mappers import Aggregate

from tiferet_h5.mappers.core import NodeObject, TableObject

# *** classes

# ** class: mapper_assertions
class MapperAssertions:
    '''
    Shared field comparisons for mapper harness tests.

    Downstream packages subclass the harness bases instead of rewriting
    round-trip assertions. This mixin compares configured fields and applies
    an optional per-field normalizer to both sides.
    '''

    # * attribute: equality_fields
    equality_fields: ClassVar[List[str]] = []

    # * attribute: field_normalizers
    field_normalizers: ClassVar[Dict[str, Callable]] = {}

    # * method: assert_model_matches
    def assert_model_matches(
        self,
        model: Any,
        sample: Dict[str, Any],
        equality_fields: Optional[List[str]] = None,
        field_normalizers: Optional[Dict[str, Callable]] = None,
    ) -> None:
        '''
        Compare configured model fields that are present in the sample.

        :param model: The model instance to check.
        :type model: Any
        :param sample: The expected values dict.
        :type sample: Dict[str, Any]
        :param equality_fields: Fields to compare. Defaults to ``equality_fields``.
        :type equality_fields: Optional[List[str]]
        :param field_normalizers: Per-field normalizers. Defaults to ``field_normalizers``.
        :type field_normalizers: Optional[Dict[str, Callable]]
        '''

        # Use the class configuration when the caller does not override it.
        if equality_fields is None:
            equality_fields = self.equality_fields
        if field_normalizers is None:
            field_normalizers = self.field_normalizers

        # Compare each configured field that the sample actually provides.
        for field in equality_fields:
            if field not in sample:
                continue

            expected = sample[field]
            actual = getattr(model, field, None)

            # Apply the field normalizer to both sides when one is set.
            normalizer = field_normalizers.get(field)
            if normalizer is not None:
                expected = normalizer(expected)
                actual = normalizer(actual)

            # Fail with the field name, expected value, and actual value.
            assert actual == expected, (
                f"Mismatch on field '{field}': expected {expected!r}, actual {actual!r}"
            )

# ** class: table_object_test_base
class TableObjectTestBase(MapperAssertions):
    '''
    Base class for testing a ``TableObject`` subclass.

    A subclass sets ``table_cls``, ``sample_data``, and ``equality_fields``.
    ``aggregate_cls``, ``aggregate_sample_data``, ``domain_cls``, and
    ``field_normalizers`` are optional. The row round trip opens a real
    temporary HDF5 file.
    '''

    # * attribute: table_cls
    table_cls: ClassVar[Optional[Type[TableObject]]] = None

    # * attribute: aggregate_cls
    aggregate_cls: ClassVar[Optional[Type[Aggregate]]] = None

    # * attribute: sample_data
    sample_data: ClassVar[Dict[str, Any]] = {}

    # * attribute: aggregate_sample_data
    aggregate_sample_data: ClassVar[Dict[str, Any]] = {}

    # * attribute: domain_cls
    domain_cls: ClassVar[Optional[Type[DomainObject]]] = None

    # * fixture: h5_table
    @pytest.fixture
    def h5_table(self, tmp_path: Path):
        '''
        Open ``tmp_path / 'harness.h5'`` in mode ``'w'`` and yield ``/harness``.

        The table is created from ``table_cls.get_description()``. The file is
        closed after the test.

        :param tmp_path: The pytest temporary directory.
        :type tmp_path: Path
        :return: A live PyTables table at ``/harness``.
        :rtype: tables.Table
        '''

        # Skip when the subclass has not declared a table class.
        if not self.table_cls:
            pytest.skip('table_cls not defined')

        # Open a temporary file and create /harness from the declared description.
        h5_path = tmp_path / 'harness.h5'
        h5file = tables.open_file(str(h5_path), mode='w')
        try:
            table = h5file.create_table('/', 'harness', self.table_cls.get_description())

            # Yield the live table, then close the file.
            yield table
        finally:
            h5file.close()

    # * test: to_row_from_row_round_trip
    def test_to_row_from_row_round_trip(self, h5_table) -> None:
        '''
        Verify ``to_row`` then ``from_row`` matches ``sample_data``.

        :param h5_table: The live ``/harness`` table.
        :type h5_table: tables.Table
        '''

        # Construct, write, and flush the table object.
        obj = self.table_cls(**self.sample_data)
        obj.to_row(h5_table)
        h5_table.flush()

        # Read the row back and reconstruct it.
        rows = list(h5_table.iterrows())
        restored = self.table_cls.from_row(rows[0])

        # Assert the restored fields match the original sample data.
        self.assert_model_matches(restored, self.sample_data)

    # * test: map
    def test_map(self) -> None:
        '''
        Verify ``map`` produces ``aggregate_cls`` when that class is set.
        '''

        # Skip when the optional aggregate class is unset.
        if not self.aggregate_cls:
            pytest.skip('aggregate_cls not defined')

        # Construct the table object and map it to an aggregate.
        obj = self.table_cls(**self.sample_data)
        mapped = obj.map(self.aggregate_cls)

        # Assert the mapped type and the aggregate sample fields.
        assert isinstance(mapped, self.aggregate_cls)
        self.assert_model_matches(mapped, self.aggregate_sample_data)

    # * test: from_model
    def test_from_model(self) -> None:
        '''
        Verify ``from_model`` returns ``table_cls`` when ``domain_cls`` is set.
        '''

        # Skip when the optional domain class is unset.
        if not self.domain_cls:
            pytest.skip('domain_cls not defined')

        # Construct the domain object and convert it.
        domain_obj = self.domain_cls(**self.sample_data)
        table_obj = self.table_cls.from_model(domain_obj)

        # Assert the result type is the table class under test.
        assert isinstance(table_obj, self.table_cls)

    # * test: to_primitive
    def test_to_primitive(self) -> None:
        '''
        Verify every equality field is a key in ``to_primitive()``.
        '''

        # Construct the table object and serialize it.
        obj = self.table_cls(**self.sample_data)
        data = obj.to_primitive()

        # Assert every configured equality field is present under its canonical name.
        for field in self.equality_fields:
            assert field in data

# ** class: node_object_test_base
class NodeObjectTestBase(MapperAssertions):
    '''
    Base class for testing a ``NodeObject`` subclass.

    A subclass sets ``node_cls``, ``sample_data``, and ``equality_fields``.
    Attribute round trips stay in memory; they do not open an HDF5 file.
    '''

    # * attribute: node_cls
    node_cls: ClassVar[Optional[Type[NodeObject]]] = None

    # * attribute: sample_data
    sample_data: ClassVar[Dict[str, Any]] = {}

    # * test: to_attrs_from_attrs_round_trip
    def test_to_attrs_from_attrs_round_trip(self) -> None:
        '''
        Verify ``to_attrs`` then ``from_attrs`` matches ``sample_data``.
        '''

        # Construct the node object and round-trip it through attribute dicts.
        obj = self.node_cls(**self.sample_data)
        restored = self.node_cls.from_attrs(obj.to_attrs())

        # Assert the restored equality fields match the sample data.
        self.assert_model_matches(restored, self.sample_data)

    # * test: to_primitive
    def test_to_primitive(self) -> None:
        '''
        Verify canonical equality field names are present in ``to_primitive()``.
        '''

        # Construct the node object and serialize it with canonical names.
        obj = self.node_cls(**self.sample_data)
        data = obj.to_primitive()

        # Assert every configured equality field is present.
        for field in self.equality_fields:
            assert field in data
