# UALF Example Dataset Datasheet

This package contains one synthetic software-maintenance trajectory for
format and pipeline testing. It is not representative training inventory.

## Collection and labels

The fixture is generated locally by `build_example.py`. Test evidence and
stubbed replay evidence are self-contained artifacts. No personal, client,
or production data is included.

## Limitations

The evaluator evidence is not externally signed, and replay does not
reexecute tools. The single trace is not representative training inventory
and should be used only as a format and integration fixture.
