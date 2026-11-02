# LocalAICompany

Read docs/PROGRESS.md and docs/SECURITY.md before changing behavior.
Work only in this repository. Runtime inference must use loopback Ollama, never cloud AI.
Do not download or move models. Generated code is untrusted; subprocess is NOT a sandbox.
Never execute generated code without a specific user approval bound to its file hashes.
Keep queue transitions deterministic, persisted and bounded. One worker and one LLM request.
Tests: .venv/Scripts/python.exe -m pytest. Frontend: npm.cmd run build and npm.cmd test.
Do not remove failing tests to claim success. Update docs/PROGRESS.md with actual verification.
No external publishing, payments or messaging in this MVP.
