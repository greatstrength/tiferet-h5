# tiferet-h5 Testing

## Overview

Pytest remains the required gate for file-backed and mock-heavy coverage. This note records one teardown rule that is easy to get wrong and expensive to rediscover: a monkeypatch of a method on a live `tables.File` must be undone before that file is closed.

## Ubiquitous Language

- **Live file** — an open `tables.File` instance, typically `H5Client.h5file`.
- **Undo** — pytest restoring a monkeypatched attribute when the patch scope ends. A function-scoped `monkeypatch` undoes after the test function returns.

## Live file monkeypatches

<a id="live-file-monkeypatch"></a>

Any monkeypatch of a method on a live `tables.File` must be undone before `File.close()`. `close()` clears the instance `__dict__`. If the undo runs afterward, pytest's `delattr` raises `AttributeError` during teardown, and a passing assertion is reported as an error.

Do not leave the patch on the function-scoped `monkeypatch` fixture. That fixture undoes after the test returns, which is after a `with H5Client(...)` block has already closed the file. Scope the patch with `monkeypatch.context()` inside the open block so the context exits, and the undo runs, before `close()`:

```python
with H5Client(path, mode='a') as h5:
    def fail_copy(*args, **kwargs):
        raise tables.HDF5ExtError('boom')

    # Undo before File.close() clears the instance __dict__.
    with monkeypatch.context() as mp:
        mp.setattr(h5.h5file, 'copy_children', fail_copy)

        h5.compact()
```

The worked case is `test_compact_copy_failure_raises` in `tiferet_h5/utils/tests/test_h5.py`. Patching a module attribute, such as `os.replace`, is not this rule: that undo does not touch the cleared `File` instance.

If the patched method itself closes the live file, the `monkeypatch.context()` block must still exit before that `close()`. Nesting the context inside the open block is not enough when the call under test closes the same instance before the context ends.

## Boundaries

**Inside this note:** how a pytest monkeypatch of a live `tables.File` method is scoped so teardown does not run after `File.close()`.
**Outside this note:** production `H5Client` behavior ([H5Client](utils/h5.md)); YAML cases under `tiferet_tests/` and their docstring-only stubs under `tests/`; CI workflow gates.

## Related Documentation

- [H5Client](utils/h5.md) — file lifecycle, including `close_file()` and `compact()`
- `tiferet_h5/utils/tests/test_h5.py` — `test_compact_copy_failure_raises`
