# Simple File Processing End-to-End Test

This test validates that the deployment-first workflow can move real files through NiFi using the modern backend services.

## Workflow Summary
1. Stage sample EDI payloads into a shared `/e2e_test_files` volume that is writable by both the backend and NiFi.
2. Deploy a three-processor flow (`GetFile → UpdateAttribute → PutFile`) through the `WorkflowOrchestrator`, including parameter context management and NiFi Registry registration.
3. Start the flow and wait for all staged files to be consumed and written to the output directory with a `processed_` filename prefix.
4. Stop and delete the flow, remove the Registry bucket, and clean up all temporary directories to keep the environment tidy.

## Expected Results
- Each sample file from `backend/tests/e2e/testdata/` is consumed from the input directory.
- Corresponding files appear in the output directory with identical content and the `processed_` prefix.
- The NiFi process group reports a running status during execution and a stopped status after shutdown.
- All deployed artifacts (process group, parameter context, Registry bucket) are removed during test cleanup.
