# Qhaway MVP Implementation Concerns

Date: 2026-06-20

This note records implementation concerns and spec/test ambiguities encountered
while building the MVP.

## Timestamp backup format

The main MVP design requires microsecond-resolution backup names with a `-NN`
collision suffix. The test-assumptions document gives a second-resolution example.
The implementation follows the stricter main spec: `MEMORY-YYYYMMDDTHHMMSSffffff.md`,
with `-NN` added only if that exact name already exists.

## Footer reservation scope

The main projection rule first describes a fixed footer set of `project`,
`reference`, and `superseded`, while the later pinned footer format and tests
expect `user` and `feedback` omissions to be declared too. The implementation
declares omissions for all schema content types: `user`, `feedback`, `project`,
and `reference`, plus superseded tombstones.

## Check overflow semantics

`--check` is specified to report whether the corpus would overflow the budget.
Because projection is designed to fit the budget, the implementation interprets
this as "the complete unabridged projection exceeds the configured budget" and
returns non-zero when it does. This is stricter than checking whether the derived
slice can be made to fit.
