'''
Deliberate pytest failure for the hybrid-gate self-check.

This module is outside pyproject testpaths. The required pytest step must
not collect it. The self-check runs it explicitly from this directory and
accepts only a failed case.
'''


def test_gate_self_check_rejects_failing_case():
    '''Fail on purpose so the pytest step of the gate self-check is red.'''

    # The self-check requires this assertion to fail.
    assert False, 'gate self-check fixture must fail'
