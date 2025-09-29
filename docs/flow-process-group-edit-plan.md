# Flow Process Group Edit Plan

> **Status:** Archived planning notes. The current product scope limits flow edits
> to metadata and parameter updates; full definition replacement is not
> implemented.

## Objectives
- Allow flow editors to paste a full NiFi process group JSON in the Flow Edit experience.
- Update the running process group in NiFi with the provided definition while keeping parameter contexts and scheduling rules safe.
- Create a new version in NiFi Registry that captures the updated flow definition alongside the metadata edits we already support.
- Ensure the UI communicates validation errors clearly and provides guardrails against destructive edits.

## Proposed User Workflow
1. Editor opens the existing Flow Edit screen.
2. In addition to name/description fields, a collapsible "Flow Definition" panel exposes a JSON textarea (with optional file upload/import later).
3. Editor pastes a NiFi process group JSON that adheres to our deployment schema (same shape produced by "Download flow definition" on create).
4. On save, the UI sends both metadata changes and (optionally) the JSON snapshot to the backend. If no JSON is provided, the request behaves like today's metadata-only edit.
5. The backend validates the JSON, applies the new definition to the process group in NiFi, uploads the resulting snapshot to Registry as a new version, and finally returns the refreshed flow overview so the UI reflects the latest data.

## Backend Architecture Changes

### API Contract
- Extend `PUT /flows/{id}` to accept an optional `flow_definition` payload (JSON object) alongside `name` and `description`.
- Alternatively expose a dedicated endpoint (`PUT /flows/{id}/definition`) if we want a clearer separation. Both approaches can share the same orchestration code path.
- Response remains the existing flow overview envelope so consumers automatically refresh to the latest state.

### Validation Layer
- Add schema validation that ensures the pasted JSON includes the keys we rely on today (`processors`, `connections`, optional `parameterContexts`, etc.), reusing the structures used by `NiFiFlowDeployment.deploy_flow` for new deployments. 【F:backend/src/services/nifi_flow_deployment.py†L1-L133】
- Verify that the process group ID inside the JSON (if any) matches the target ID, or strip IDs before deployment to let NiFi regenerate them, similar to the initial deploy path.
- Ensure we reject attempts to change the parameter context assignment unless the user explicitly provides parameter context fields.

### Orchestration Flow
1. **Fetch Current State**: Use `WorkflowOrchestrator.get_flow_overview` to capture the current revision numbers, parameter context assignment, and Registry version-control info before we begin. 【F:backend/src/services/workflow_orchestrator.py†L19-L83】
2. **Stop & Quiesce**: Call `NiFiFlowManagement.stop_flow` to ensure the process group is idle before replacing components. We already have this capability exposed via the orchestrator. 【F:backend/src/services/nifi_flow_management.py†L1-L166】
3. **Apply Definition**:
   - Reuse the helper paths in `NiFiFlowDeployment` to tear down and rebuild processors/connections inside the existing process group. We can add a `replace_flow_contents(process_group_id, flow_definition, parameters)` method that wraps the existing `_deploy_processors`, `_deploy_connections`, and `_validate_components` routines but skips creating a new process group. 【F:backend/src/services/nifi_flow_deployment.py†L34-L133】
   - Preserve and reapply the current parameter context using the metadata we already fetch during deployment. 【F:backend/src/services/workflow_orchestrator.py†L258-L307】
   - On failure, perform the same cleanup and logging strategy used in initial deployments so partially applied updates roll back gracefully.
4. **Registry Versioning**:
   - Use the version-control data retrieved earlier to determine the `bucket_id`/`flow_id`.
   - Call `RegistryVersionManagement.create_flow_version` with the snapshot NiFi returns after the update, similar to what `IntegrationBridge.upload_flow_to_registry` does during create. 【F:backend/src/services/registry_version_management.py†L1-L69】
   - Include a default comment (e.g., "Updated via flow edit") and surface the new version number in the response.
5. **Metadata Update**:
   - Reuse the existing `update_flow_metadata` workflow for name/description changes so we do not duplicate Registry metadata logic. 【F:backend/src/services/workflow_orchestrator.py†L258-L307】
6. **Return Overview**:
   - Call `_build_flow_response` (recently added helper) so the UI always receives the latest NiFi status, comments, and Registry data in a single shape. 【F:backend/src/api/v1/flows/flows.py†L332-L427】

### Error Handling & Auditing
- If JSON validation fails, return a 422 with specific guidance (missing processors, invalid schema, etc.).
- If NiFi rejects the update mid-flight, attempt to roll back to the previously captured snapshot (future enhancement) or at minimum bubble up a descriptive failure while leaving the old components intact.
- Emit structured logs for each step (stop, replace, version upload, metadata update) so operational teams can trace edit attempts.

## Frontend Updates
- Extend the Flow Edit form (`FlowEdit.tsx`) to include the JSON textarea with syntax highlighting (Monaco or a basic CodeMirror integration). Provide character counts and validation feedback before submission.
- Disable the save button while validation fails or an update is running, and surface backend error messages inline.
- After a successful save, refresh the show page via existing hooks so users immediately see the updated description, status, and new Registry version badge.

## Testing Strategy
- **Unit Tests**: Cover JSON validation, orchestration branching (metadata-only vs. metadata+definition), and error paths for NiFi or Registry failures.
- **Integration Tests**: Extend the API tests to submit a small mocked flow definition and assert NiFi client calls receive the correct payloads, using fixtures to simulate NiFi/Registry interactions.
- **End-to-End (Playwright)**: Expand the lifecycle scenario to paste a modified flow definition, save, and verify that the UI displays the new processor layout indicators (where feasible) plus the updated Registry version number.
- **Contract Tests**: Consider capturing a real NiFi snapshot to use as a golden fixture for validation to prevent regressions in the schema expectations.

## Reuse of Existing Work
- The metadata update path we recently added (`WorkflowOrchestrator.update_flow_metadata` and `NiFiFlowManagement.update_flow_metadata`) already handles name/description propagation and parameter context preservation, so we will call into it after deploying new contents rather than duplicating logic. 【F:backend/src/services/workflow_orchestrator.py†L258-L307】【F:backend/src/services/nifi_flow_management.py†L148-L166】
- The deployment helpers (`NiFiFlowDeployment`) provide robust processor/connection creation, validation, and cleanup routines that we can adapt for in-place replacements instead of rewriting NiFi API interactions. 【F:backend/src/services/nifi_flow_deployment.py†L34-L133】
- Registry version creation utilities (`RegistryVersionManagement.create_flow_version`) already handle parameter context serialization and version increments, ensuring our new version uploads match initial deployments. 【F:backend/src/services/registry_version_management.py†L20-L69】

## Open Questions
- Do we need to support partial updates (only processors without connections), or should the editor always supply a full snapshot? Enforcing a full snapshot simplifies validation and rollback.
- Should we automatically create a new Registry flow version even when the process group is not currently version-controlled? We could prompt users to enable version control first.
- How do we handle long-running updates? Consider background jobs or WebSocket notifications if deployments take significant time.

By following this plan we can let editors safely replace entire flow definitions while leveraging the orchestration, metadata, and Registry integrations we already built for the initial deploy and edit experiences.
