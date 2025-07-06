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

## 🚀 Phase 2: Core Engine & Data-Driven Validation

*Goal: Upgrade the parser to be schema-aware and build a validation engine that can execute schema-defined rules.*

-   [ ] **Enhance the EDI Parser**:
    -   [ ] Create `src/core/cdm.py` to define the Canonical Data Model (CDM) Pydantic models. The CDM should be a tree-like structure representing the loops and segments of the parsed EDI file.
    -   [ ] Refactor `src/core/edi_parser.py`:
        -   [ ] The main parsing function should now accept an `ImplementationGuideSchema` object.
        -   [ ] The parser will use the `structure` definition from the schema to intelligently build the hierarchical CDM object, correctly identifying loops and their nesting.
        -   [ ] The parser must also perform **SNIP Level 3 (Balancing)** checks (e.g., `IEA` count vs. `GS` count, `SE` count vs. segment count).

-   [ ] **Develop the Validation Engine**:
    -   [ ] Create a new file: `backend/src/core/validator.py`.
    -   [ ] Implement the `ValidationEngine` class.
    -   [ ] Implement the `execute_schema_validation(cdm: CDM, schema: ImplementationGuideSchema)` method. This method will:
        -   [ ] **Traverse the CDM**: Walk through each loop, segment, and element.
        -   [ ] **Perform SNIP 1 (Integrity)**: Verify that the segments appear in an order allowed by the schema's `structure`.
        -   [ ] **Perform SNIP 2 (Requirement)**: For each loop/segment definition in the schema, check the CDM to ensure that required nodes (`usage: "R"`) exist and that `max_use` is not exceeded.
        -   [ ] **Perform SNIP 4 (Code Sets)**: For each element in the CDM, check its value against the `valid_codes` array in its schema definition.
        -   [ ] **Perform SNIP 5 (Syntax)**: Implement logic to interpret and validate rules from the `syntax` array in segment definitions (e.g., `P0809` -> if element 8 exists, element 9 must also exist).
    -   [ ] Define a `ValidationFinding` schema in `src/api/schemas.py` to hold detailed error information (rule ID, severity, message, location path like `2000B/2300/CLM[1]/CLM02`).

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

## 🔌 Phase 4: API & Orchestration

*Goal: Tie all the new components together in the main validation API endpoint.*

-   [ ] **Refactor the `/validate` Endpoint** (`src/api/endpoints/validation.py`):
    -   [ ] The endpoint should now orchestrate the entire process:
        1.  Get the raw EDI data from the request.
        2.  Determine the implementation guide version (e.g., from `GS08`).
        3.  Call `SchemaManager.get_schema()` to load the appropriate guide.
        4.  Call the enhanced `edi_parser` with the EDI data and the schema to get the CDM. Handle parsing errors and potential TA1 generation.
        5.  Identify the `PartnerProfile` using existing logic.
        6.  Instantiate the `ValidationEngine`.
        7.  Execute validation to get a list of findings.
        8.  (From previous plan) Call `AcknowledgementGenerator` to create the 999 response.
        9.  Return the full `ValidationResponse`, including findings and the 999.

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