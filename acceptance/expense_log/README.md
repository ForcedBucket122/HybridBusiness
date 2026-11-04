# Independent expense-log acceptance tests

Source of truth: data/autonomy-e2e2-20261104.json, request field.
Product: e445de53b00c45a48732137b4d402d28, final Release main.py.
These tests do not import or reuse the generated test_main.py.

Eight mandatory methods: malformed JSON preservation for add/list/total;
zero/negative/noninteger amounts; blank categories (including whitespace);
required --file. Empty storage is not malformed JSON: here b'' means an
existing empty file, not a missing file or a valid JSON []. Error assertions
require nonzero integer exit and nonempty stderr, without exact wording.

Two advisory methods (disabled by default): reject syntactically valid JSON
with invalid schema and preserve its bytes; reject incomplete add operands
cleanly and preserve valid data on rejected input. The schema is specified for
stored records, but recovery/error behavior for externally corrupted schemas
is not specified. These results must not block release as mandatory failures
without agreeing the extra contract. No exact diagnostic wording is imposed.

Execution has NOT been approved. Previous one-shot product approvals are spent.
Do not run this file against the working product. A fresh approval must cover
an immutable snapshot containing reviewed main.py and this test_acceptance.py,
all file hashes, the exact command, timeout and host-execution warning. Use the
existing approval/snapshot workflow; do not alter the existing product or ZIP.
The environment guard is only protection against accidental execution, NOT an
approval mechanism. Product hash is checked before its import. No product import
occurs during collection. All test data writes are in TemporaryDirectory.

Proposed execution after approval: project Python -I -B -m unittest discover
-s . -p test_acceptance.py -v, timeout 120 s, cwd approved snapshot.
The runner must explicitly supply EXPENSE_APPROVED_SNAPSHOT=1; optional advisory
execution additionally requires EXPENSE_ADVISORY_CASES=1 and its scope in the
approval. If the current runner strips these variables, prepare a reviewed
execution adapter and bind its hash before requesting consent; do not bypass it.
Never interpret skipped guarded tests as successful product validation.

## Prepared execution (2026-11-04)

No backend/runner change was needed. approved_adapter.py becomes the sole
snapshot test_acceptance.py; the independent suite becomes acceptance_cases.py
(UTF-8 without BOM, LF; test assertions unchanged). main.py is an unchanged
copy of Release 6ff64f6d. The adapter uses unittest load_tests, enables the
accidental-execution guard inside the already approved child process and
forcibly disables advisory cases. It never grants engine approval.

Dedicated acceptance project: b5e63a23e87543519ca2d89fbdaff4d0.
QA task: f2476b1bd502455381d9a723f06434cf.
Fresh approval: 79077d28f33a4d9b8bf5e21883867b40 (PENDING when prepared).
All three snapshot file hashes and the fixed runner command are in
logs/expense-independent-acceptance-prepared-20261104.json and Approval.details.
This pending registration records an engineering static review, not model QA.
Actual snapshot creation, rehash, execution and consumption remain controlled
by the existing Service.decision / Orchestrator.execute_tests path.

Three infrastructure regressions passed, including the real ApprovedHostRunner
with eight trusted stub passes and two advisory skips. No generated product ran.
