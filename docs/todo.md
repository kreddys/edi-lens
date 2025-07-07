# TODO: EDI Validation Engine with User Overrides

This document outlines the development tasks for implementing a schema-driven EDI validation engine with a user-configurable override layer.

## 📈 Project Status

| Phase                                   | Status      |
| --------------------------------------- | ----------- |
| **Phase 1: Foundational Schema Layer**      | `Not Started` |
| **Phase 2: Core Engine & Data-Driven Validation** | `Not Started` |
| **Phase 3: Partner Override System**   | `Not Started` |
| **Phase 4: API & Orchestration**     | `Not Started` |
| **Phase 5: UI for Rule Management**               | `Not Started` |

---

## ✅ Phase 1: Foundational Schema Layer

*Goal: Create a system for loading and managing the base implementation guide schemas (e.g., the `837.5010.X222.A1.json` file).*

-   [ ] **Create a new storage location for schemas**:
    -   [ ] Create a new directory: `backend/src/edi_schemas`.
    -   [ ] Add the `837.5010.X222.A1.json` file to this directory.

-   [ ] **Develop Pydantic Models for the Schema**:
    -   [ ] Create a new file: `backend/src/core/schemas/edi_guide.py`.
    -   [ ] Define Pydantic models that mirror the JSON schema structure. This ensures type safety when accessing schema properties.
        -   `ElementDefinition`
        -   `SegmentDefinition`
        -   `LoopDefinition`
        -   `ImplementationGuideSchema` (the top-level model).

-   [ ] **Implement the Schema Manager**:
    -   [ ] Create a new file: `backend/src/core/schema_manager.py`.
    -   [ ] Implement a `SchemaManager` class (as a singleton).
        -   [ ] The manager's `__init__` method should automatically discover and load all `.json` files from the `edi_schemas` directory into a dictionary, keyed by their `transactionName` or a sanitized version of it (e.g., `837P_X222A1`).
        -   [ ] The loading process should parse the raw JSON into our new Pydantic models.
        -   [ ] Create a public method: `get_schema(guide_version: str) -> ImplementationGuideSchema | None`.
    -   [ ] Ensure the `SchemaManager` instance is initialized once when the FastAPI application starts up (e.g., in the `lifespan` context manager in `main.py`).

---

## 🚀 **Phase 2 (Revised): Core Engine & Data-Driven Validation**

*Goal: Create a **forgiving parser** and a **strict validator** that work together to produce a comprehensive list of findings.*

-   [ ] **Refactor the EDI Parser (`src/core/edi_parser.py`)**:
    -   [ ] **Change the Goal**: The parser's primary goal is now to build a *best-effort* CDM, not to enforce schema rules.
    -   [ ] **Remove Strict Checks**:
        -   [x] Remove the `if consumed_count != len(transaction_segments): raise ValueError(...)` check. The parser should simply return the CDM it built and the number of segments it was able to place.
        -   The parser should continue processing even if a segment or loop doesn't match the schema, leaving un-placed segments for the validator to report.
    -   [ ] The parser should only fail on truly unrecoverable errors (e.g., can't find ST/SE, invalid delimiters).

-   [ ] **Develop the Validation Engine (`src/core/validator.py`)**:
    -   [ ] Implement the `ValidationEngine` class.
    -   [ ] Implement the `execute_schema_validation(cdm: CDM, total_segments: int, consumed_segments: int, schema: ImplementationGuideSchema)` method. This method will:
        -   [ ] **Check for Unconsumed Segments**: The very first check should be `if total_segments != consumed_segments`, which would generate a specific "Unexpected structure" or "Trailing segments" error. This replaces the `ValueError` from the old parser.
        -   [ ] **Traverse the CDM**: Walk through the generated CDM tree.
        -   [ ] **Perform SNIP 1 (Integrity)**, **SNIP 2 (Requirement)**, **SNIP 4 (Code Sets)**, and **SNIP 5 (Syntax)** checks against the schema.
        -   [ ] For every violation found, it should create and append a `ValidationFinding` object to a list.
    -   [ ] The engine should **return the complete list of findings**, not stop on the first error.

-   [ ] **Develop the Acknowledgement Generator (`src/core/ack_generator.py`)**:
    -   [ ] Create a new `AcknowledgementGenerator` class.
    -   [ ] Implement a `create_999(findings: List[ValidationFinding], original_gs: CdmSegment, original_st: CdmSegment)` method. This method will:
        -   [ ] Analyze the `findings` list to determine the overall status for `AK901` (`A`, `E`, or `R`).
        -   [ ] Iterate through the findings to build the necessary `IK3`, `IK4` (for segment-level issues), and `IK5` (for transaction set-level issues) segments.
        -   [ ] Use the `original_gs` and `original_st` segments to correctly populate the envelope of the 999.
        -   [ ] Return the complete 999 as a raw EDI string.

---

## 🔧 Phase 3: Partner Override System

*Goal: Enable users to relax or modify the base schema rules on a per-partner basis.*

-   [ ] **Update Database Models**:
    -   [ ] Review the `Rule` model (`src/models/rule.py`). We will use this to store the **overrides** and any **custom (SNIP 6-7) rules**.
    -   [ ] Define a clear, consistent format for `rule_code` that uniquely identifies every possible check from the JSON schema (e.g., `837P_X222A1:2010AA.NM1.NM103.required`).

-   [ ] **Update the Validation Engine**:
    -   [ ] The `ValidationEngine`'s main `validate` method should now accept a `PartnerProfile` in addition to the CDM and schema.
    -   [ ] Implement the "Layered Validation" logic:
        1.  Generate an in-memory "master rule set" from the JSON schema.
        2.  Query the database for all `ProfileRuleAssociation` entries for the given profile.
        3.  Iterate through the database overrides and modify the master rule set (e.g., disable a rule, change its severity).
        4.  Execute the final, consolidated set of rules against the CDM.

---

## 🔌 Phase 4 (Revised): API & Orchestration

*Goal: Update the `/validate` endpoint to use the new, decoupled components.*

-   [ ] **Refactor the `/validate` Endpoint** (`src/api/endpoints/validation.py`):
    -   [ ] The endpoint's new orchestration will be:
        1.  Get raw EDI data.
        2.  Call `SchemaManager` to get the correct schema.
        3.  Call `EdiParser.parse()` to get the best-effort **CDM** and the **consumed segment count**.
        4.  Instantiate `ValidationEngine`.
        5.  Call `ValidationEngine.execute_schema_validation(...)` to get the list of **findings**.
        6.  Instantiate `AcknowledgementGenerator`.
        7.  Call `AcknowledgementGenerator.create_999(...)` to get the **999 string**.
        8.  Return a `ValidationResponse` containing the findings and the generated 999 acknowledgement.

By adopting this revised plan, your application will be able to correctly handle structurally invalid files, provide detailed feedback to the user, and generate the compliant 999 acknowledgement required for proper EDI communication.

---

## 🎨 Phase 5: UI for Rule Management

*Goal: Create an interface for users to view and manage validation rule overrides for their trading partner profiles.*

-   [ ] **Create a New UI Page for Rule Configuration**:
    -   [ ] This page will be part of the `TradingPartnerEdit` view, perhaps in a new "Validation Rules" tab.
    -   [ ] On page load, the UI will:
        -   Fetch the `TradingPartner` and `PartnerProfile` data.
        -   Make a new API call to an endpoint like `/api/v1/implementation-guides/{guide_version}/rules` to get a structured list of all default rules from the JSON schema.
        -   The existing `profile.rules` (or similar) will contain the user's saved overrides.

-   [ ] **Develop the Rule Override Component**:
    -   [ ] Design a component (e.g., a tree-table) that displays all rules from the schema, grouped by loop and segment.
    -   [ ] For each rule, display its default severity and status (enabled/disabled).
    -   [ ] Provide UI controls (toggle switch, dropdown) to let the user change the `is_enabled` status or `override_severity`.
    -   [ ] Highlight rules that have been changed from their default state.
    -   [ ] When the user saves the profile, the frontend will send only the list of overrides (the "deltas") to the backend `PUT /trading-partners/{id}` endpoint.

-   [ ] **Backend API Support**:
    -   [ ] Create the new endpoint (`/api/v1/implementation-guides/{guide_version}/rules`) that reads a JSON schema file and returns its rule set to the UI.
    -   [ ] Update the `TradingPartnerRepository.update` method to correctly process the incoming list of rule overrides and save them to the `profile_rule_association` table.