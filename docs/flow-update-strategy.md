# Flow Update Strategy

The flow update surface now routes metadata and parameter changes through a
single workflow so NiFi and Registry stay in sync.

## Why a Unified Workflow?

NiFi stores flow state across multiple subsystems:

- **Process group metadata** (name and comments) live directly in NiFi and must be
  updated using the process-group revision so we do not sever the attached
  parameter context.
- **Parameter contexts** are independent NiFi objects and are **not** versioned in
  the Registry. Updating parameters requires submitting an asynchronous update
  request and polling until completion.
- **Registry metadata** mirrors the process group name/comments when the flow is
  under version control, so the Registry must be updated after NiFi to keep audit
  history consistent.

Previously these concerns were exposed through separate API calls which made it
unclear how to perform partial versus full updates. The orchestrator now exposes
`update_flow(...)` which fan-outs to the relevant operations while ensuring a
single error surface for the API layer.

## Parameter Context Behaviour

- Parameter contexts are stored only in NiFi and are not automatically uploaded to
  the Registry when new flow versions are created. The Registry only tracks flow
  structure and component metadata.
- NiFi does not keep multiple versions of a parameter context. A context may be
  updated in place or replaced entirely, but version history is not retained.
- When the update workflow receives parameter changes it normalises both the
  "dict" payload used by the edit form and the structured list used by the
  parameter API so the backend always issues a single NiFi update request.

## Flow Definition Updates

Full flow definition replacement is currently out of scope for the edit surface.
Structural changes should continue to use the deploy/import workflow while the
edit endpoint focuses on metadata and parameter context maintenance.
