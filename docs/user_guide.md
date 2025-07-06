# EDI Lens - User Guide

This guide explains the core concepts behind configuring Trading Partners in EDI Lens and how the system uses this configuration to process incoming EDI files.

## Goal: How an EDI File is Matched to a Profile

The primary goal of the Trading Partner configuration is to create a set of rules that allow EDI Lens to answer the question: **"When a new EDI file arrives, which set of validation rules should I apply to it?"**

The system does this by matching the incoming file against the **Criteria** defined within a **Profile**, which belongs to a **Trading Partner**.

---

## Core Concepts

### 1. Trading Partner

-   **What it is**: The highest-level entity. It represents an external organization you exchange EDI documents with, such as a specific payer, provider, or clearinghouse.
-   **Example**: "United Healthcare", "Regional Hospital System", "Acme Clearinghouse".

### 2. Profile

-   **What it is**: A specific configuration *within* a Trading Partner. A single partner might have multiple profiles to handle different types of transactions or different business units. Each profile is associated with a specific **Implementation Guide** (e.g., 837P, 835, 270/271).
-   **Priority**: Each profile has a priority number. If an incoming file happens to match the criteria for multiple profiles, the one with the **lowest priority number** will be chosen. (e.g., Priority `10` wins over Priority `20`).
-   **Example**: The "United Healthcare" Trading Partner might have two separate profiles:
    -   `UHC Professional Claims (837P)`
    -   `UHC Institutional Claims (837I)`

### 3. Criterion

-   **What it is**: A specific rule used to match a file to a profile. A profile can have one or more criteria.
-   **Matching Logic**: For a file to match a profile, it must satisfy **ALL** of the criteria defined for that profile (an "AND" condition).

Each criterion has four parts:

-   **Source**: Where in the incoming data to look.
    -   `ISA`: Look in the Interchange Control Header segment.
    -   `GS`: Look in the Functional Group Header segment.
    -   `FILENAME`: Look at the name of the uploaded file.
-   **Identifier**: Which specific data element to check within the source.
    -   For `ISA`, this would be an element position like `06` (Sender ID) or `08` (Receiver ID).
    -   For `GS`, this would be `02` (Sender Code) or `03` (Receiver Code).
-   **Operator**: The type of comparison to perform.
    -   `EQUALS`: The data must exactly match the value.
    -   `STARTS_WITH`: The data must begin with the value.
    -   `CONTAINS`: The data must contain the value somewhere within it.
-   **Value**: The string to compare against.

---

## Configuration Examples

### Scenario 1: Standard Partner Identification by Sender ID

You want to process all files from "Payer ABC" and you identify them by their ISA Sender ID, which is always `PAYER_ABC_12345`.

-   **Trading Partner**:
    -   Name: `Payer ABC`
-   **Profile**:
    -   Name: `Payer ABC - All Transactions`
    -   Implementation Guide: `005010X222A1` (for 837P claims, as an example)
-   **Criterion**:
    -   Source: `ISA`
    -   Identifier: `06: Sender ID`
    -   Operator: `EQUALS`
    -   Value: `PAYER_ABC_12345`

**Result**: Any file that arrives with `ISA*...*PAYER_ABC_12345*...~` will be matched to this profile.

### Scenario 2: Identifying by Transaction Type and Receiver

A large clearinghouse sends you files for many different clients. You want to isolate only the 835 Remittance Advice files that are intended for your "General Hospital" client.

-   **Trading Partner**:
    -   Name: `Major Clearinghouse`
-   **Profile**:
    -   Name: `General Hospital - 835 Remittances`
    -   Implementation Guide: `005010X221A1` (for 835s)
-   **Criterion 1 (Identifies the transaction type)**:
    -   Source: `GS`
    -   Identifier: `01: Functional ID Code`
    -   Operator: `EQUALS`
    -   Value: `HP` (The code for 835 Remittance Advice)
-   **Criterion 2 (Identifies the intended recipient)**:
    -   Source: `GS`
    -   Identifier: `03: Receiver Code`
    -   Operator: `EQUALS`
    -   Value: `GENERAL_HOSP_ID`

**Result**: A file will only match this profile if its GS segment contains **both** `GS*HP*...*GENERAL_HOSP_ID~`.