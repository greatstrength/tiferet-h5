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

from ..settings import NodeObject, TableObject

# *** classes

# ** class: mapper_assertions
class MapperAssertions:
    '''
    Shared assertion helpers for TableObject/NodeObject harness tests.

    Mirrors core Tiferet's own ``MapperAssertions`` mixin
    (``tiferet.testing.mappers.MapperAssertions``) so ``TableObjectTestBase``
    and ``NodeObjectTestBase`` compare field values the same way
    ``AggregateTestBase``/``TransferObjectTestBase`` do.
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
        Compare model attributes against a sample data dict.

        :param model: The model instance to check.
        :type model: Any
        :param sample: The expected values dict.
        :type sample: Dict[str, Any]
        :param equality_fields: Fields to compare (defaults to self.equality_fields).
        :type equality_fields: Optional[List[str]]
        :param field_normalizers: Per-field normalizers (defaults to self.field_normalizers).
        :type field_normalizers: Optional[Dict[str, Callable]]
        '''

        # Use configured defaults when not explicitly provided.
        equality_fields = equality_fields or self.equality_fields
        field_normalizers = field_normalizers or self.field_normalizers

        # Compare each configured field, applying its normalizer if any.
        for field in equality_fields:
            if field not in sample:
                continue

            expected = sample[field]
            actual = getattr(model, field, None)

            normalizer = field_normalizers.get(field)
            if normalizer:
                expected = normalizer(expected)
                actual = normalizer(actual)

            assert actual == expected, (
                f"Mismatch on field '{field}':\n"
                f"  expected: {expected!r}\n"
                f"  actual:   {actual!r}"
            )


# ** class: table_object_test_base
class TableObjectTestBase(MapperAssertions):
    '''
    Base class for testing TableObject subclasses.

    Subclasses define:
    - table_cls              -- the TableObject class under test
    - aggregate_cls          -- the target Aggregate class for map() tests
    - sample_data            -- dict of field values for constructing the table object
    - aggregate_sample_data  -- dict of expected aggregate field values
    - equality_fields        -- fields to compare
    - field_normalizers      -- optional per-field normalizers
    - domain_cls             -- optional DomainObject class for from_model() tests
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
        Open a temporary HDF5 file and yield a live table built from
        table_cls.get_description(). Closes the file after the test.
        '''

        # Skip if no table class is defined.
        if not self.table_cls:
            pytest.skip('table_cls not defined')

        # Open a temp file and create the table from the declared description.
        h5_path = tmp_path / 'harness.h5'
        h5file = tables.open_file(str(h5_path), mode='w')
        table = h5file.create_table('/', 'harness', self.table_cls.get_description())

        # Yield the live table for the test, then close the file.
        yield table
        h5file.close()

    # * method: test_to_row_from_row_round_trip
    def test_to_row_from_row_round_trip(self, h5_table) -> None:
        '''
        Verify to_row() followed by from_row() preserves field values.
        '''

        # Construct, write, and flush the table object.
        obj = self.table_cls(**self.sample_data)
        obj.to_row(h5_table)
        h5_table.flush()

        # Read the row back and reconstruct.
        rows = list(h5_table.iterrows())
        restored = self.table_cls.from_row(rows[0])

        # Assert the restored fields match the original sample data.
        self.assert_model_matches(restored, self.sample_data)

    # * method: test_map
    def test_map(self) -> None:
        '''
        Verify TableObject construction -> map() produces a valid aggregate.
        '''

        # Skip if no aggregate class is defined.
        if not self.aggregate_cls:
            pytest.skip('aggregate_cls not defined')

        # Construct the table object and map it to an aggregate.
        obj = self.table_cls(**self.sample_data)
        mapped = obj.map(self.aggregate_cls)

        # Assert the mapped aggregate is the correct type and matches expected data.
        assert isinstance(mapped, self.aggregate_cls)
        self.assert_model_matches(mapped, self.aggregate_sample_data)

    # * method: test_from_model
    def test_from_model(self) -> None:
        '''
        Verify DomainObject -> TableObject conversion via from_model().
        '''

        # Skip if no domain class is defined.
        if not self.domain_cls:
            pytest.skip('domain_cls not defined')

        # Construct the domain object and convert it.
        domain_obj = self.domain_cls(**self.sample_data)
        table_obj = self.table_cls.from_model(domain_obj)

        # Assert the result is the correct type.
        assert isinstance(table_obj, self.table_cls)

    # * method: test_to_primitive
    def test_to_primitive(self) -> None:
        '''
        Verify to_primitive() returns canonical field names, not aliases.
        '''

        # Construct the table object and serialize it.
        obj = self.table_cls(**self.sample_data)
        data = obj.to_primitive()

        # Assert every configured equality field is present under its canonical name.
        for field in self.equality_fields:
            assert field in data

    # * method: test_verify_schema
    def test_verify_schema(self, h5_table) -> None:
        '''
        Verify verify_schema() returns an empty list for a matching table.
        '''

        # Run schema verification and assert full consistency.
        mismatches = self.table_cls.verify_schema(h5_table)
        assert mismatches == []


# ** class: node_object_test_base
class NodeObjectTestBase(MapperAssertions):
    '''
    Base class for testing NodeObject subclasses.

    Subclasses define:
    - node_cls               -- the NodeObject class under test
    - aggregate_cls          -- the target Aggregate class
    - sample_data            -- dict of field values
    - aggregate_sample_data  -- dict of expected aggregate values
    - equality_fields        -- fields to compare
    - field_normalizers      -- optional per-field normalizers
    - attrs_exclude_fields   -- optional fields expected to be excluded from to_attrs()
    '''

    # * attribute: node_cls
    node_cls: ClassVar[Optional[Type[NodeObject]]] = None

    # * attribute: aggregate_cls
    aggregate_cls: ClassVar[Optional[Type[Aggregate]]] = None

    # * attribute: sample_data
    sample_data: ClassVar[Dict[str, Any]] = {}

    # * attribute: aggregate_sample_data
    aggregate_sample_data: ClassVar[Dict[str, Any]] = {}

    # * attribute: attrs_exclude_fields
    attrs_exclude_fields: ClassVar[List[str]] = []

    # * method: make_aggregate
    def make_aggregate(self, data: Optional[Dict[str, Any]] = None) -> Aggregate:
        '''
        Create an aggregate instance for from_model()/round-trip tests.
        Override for custom constructor signatures.

        :param data: The data to construct from (defaults to aggregate_sample_data).
        :type data: Optional[Dict[str, Any]]
        :return: A new aggregate instance.
        :rtype: Aggregate
        '''

        # Construct using the standard Pydantic constructor.
        return self.aggregate_cls(**(data or self.aggregate_sample_data))

    # * fixture: aggregate
    @pytest.fixture
    def aggregate(self):
        '''
        Fixture providing an aggregate instance from aggregate_sample_data.
        '''

        # Skip if no aggregate class is defined.
        if not self.aggregate_cls:
            pytest.skip('aggregate_cls not defined')

        # Create and return the aggregate.
        return self.make_aggregate()

    # * method: test_map
    def test_map(self) -> None:
        '''
        Verify NodeObject construction -> map() produces a valid aggregate.
        '''

        # Skip if no aggregate class is defined.
        if not self.aggregate_cls:
            pytest.skip('aggregate_cls not defined')

        # Construct the node object via model_validate and map it.
        node_obj = self.node_cls.model_validate(self.sample_data)
        mapped = node_obj.map(self.aggregate_cls)

        # Assert the mapped aggregate is the correct type and matches expected data.
        assert isinstance(mapped, self.aggregate_cls)
        self.assert_model_matches(mapped, self.aggregate_sample_data)

    # * method: test_from_model
    def test_from_model(self, aggregate) -> None:
        '''
        Verify Aggregate -> NodeObject conversion via from_model().
        '''

        # Convert the aggregate to a node object using the classmethod.
        node_obj = self.node_cls.from_model(aggregate)

        # Assert the result is the correct type.
        assert isinstance(node_obj, self.node_cls)

    # * method: test_to_attrs_excludes_fields
    def test_to_attrs_excludes_fields(self) -> None:
        '''
        Verify configured fields are absent from to_attrs() output.
        '''

        # Skip if no fields are configured for exclusion.
        if not self.attrs_exclude_fields:
            pytest.skip('attrs_exclude_fields not defined')

        # Construct the node object and serialize to attrs.
        node_obj = self.node_cls.model_validate(self.sample_data)
        attrs = node_obj.to_attrs()

        # Assert each configured field is absent.
        for field in self.attrs_exclude_fields:
            assert field not in attrs

    # * method: test_round_trip
    def test_round_trip(self, aggregate) -> None:
        '''
        Verify Aggregate -> NodeObject -> Aggregate round-trip.
        '''

        # Convert aggregate to node object and back.
        node_obj = self.node_cls.from_model(aggregate)
        round_tripped = node_obj.map(self.aggregate_cls)

        # Assert the round-tripped aggregate matches expected data.
        assert isinstance(round_tripped, self.aggregate_cls)
        self.assert_model_matches(round_tripped, self.aggregate_sample_data)

    # * method: test_from_attrs_decodes_bytes
    def test_from_attrs_decodes_bytes(self) -> None:
        '''
        Verify from_attrs() decodes bytes-valued attrs to str.
        '''

        # Build a bytes-valued attrs dict from the string-valued sample data.
        raw = {
            k: v.encode('utf-8') if isinstance(v, str) else v
            for k, v in self.sample_data.items()
        }

        # Construct from the bytes-valued attrs.
        node_obj = self.node_cls.from_attrs(raw)

        # Assert every str-valued field was decoded back to str.
        for field, value in self.sample_data.items():
            if isinstance(value, str):
                assert getattr(node_obj, field) == value
