# Historical publication-repair inputs

These are byte-for-byte files from commit
`5e2aa4763d79bcba782e19bc84c18ad4975092ad`, the source commit recorded by the
immutable official-grid seal. The manifest records each source path and SHA-256,
plus registry paths absent from that historical tree. The snapshot contains
the coherent calendar, repair-era rounds, accuracy report, circuit history and
preserved forecast mapping used by the historical repair assertions.

The round-17 hash is
`79f96e5bd8f148dadc4839fe5e8f17e7e0e6147922e9a9397b8e7a50c4dc881c`;
the season hash is
`1b0fccec6c44df09692ac38a306ee8a156e4ccfd40c4b164321690fabdd16110`.
Both match the existing seal's input hashes. Round 17 also matches the immutable
UI `singapore-no-result.json` fixture exactly. No current result was removed to
construct this snapshot.

Temporal grid/ridge tests copy these exact pre-race inputs into disposable
directories while preserving their deadline, source-mutation and outcome
assertions. The history database and production modules remain unchanged.
The historical repair test still verifies the original archive's hashes.
A separate held-forecast test uses the provenance-recorded result-available UI
snapshot and requires legitimate actuals to remain while predictions and the
accuracy grade stay excluded.
