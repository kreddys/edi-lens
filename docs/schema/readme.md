# EDI Schema Template for LLM Context

This document provides a simplified template of the EDI implementation guide schema (e.g., `837.5010.X222.A1.json`). The goal is to explain the structure and relationships within the schema without including the full, verbose content.

## 1. Top-Level Structure

The entire schema is a single JSON object with three main keys:

```json
{
  "transactionName": "HIPAA Health Care Claim: Professional X222A1-837",
  "segmentDefinitions": { ... },
  "structure": [ ... ]
}
```

-   `transactionName`: A human-readable name for the implementation guide.
-   `segmentDefinitions`: A dictionary containing the full definition for every possible segment (like `CLM`, `NM1`, `REF`, etc.).
-   `structure`: An array that defines the hierarchical order and nesting of loops and segments for the transaction.

---

## 2. The `segmentDefinitions` Dictionary

This is a master library of all segments. The key is the segment ID (e.g., "NM1"), and the value is an object describing its properties and elements.

### Example: A single `SegmentDefinition` for "NM1"

```json
{
  "segmentDefinitions": {
    "NM1": {
      "name": "Billing Provider Name",
      "usage": "R",
      "pos": "200",
      "max_use": 1,
      "elements": [
        {
          "xid": "NM101",
          "data_ele": 98,
          "name": "Entity Identifier Code",
          "usage": "R",
          "seq": "01",
          "valid_codes": { "code": [ "85" ] }
        },
        {
          "xid": "NM102",
          "data_ele": 1065,
          "name": "Entity Type Qualifier",
          "usage": "R",
          "seq": "02",
          "valid_codes": { "code": [ 1, 2 ] }
        },
        { "...": "more elements" }
      ],
      "elementsByXid": {
        "NM101": { "...element definition..." },
        "NM102": { "...element definition..." }
      }
    },
    "CLM": { "...": "definition for the CLM segment" },
    "...": "more segment definitions"
  }
}
```

-   `elements`: An array defining each data element within the segment in order.
-   `elementsByXid`: A dictionary providing quick lookup of an element by its ID (e.g., "NM101").

---

## 3. The `structure` Array

This array is the blueprint for the transaction's hierarchy. It contains two types of objects: `loop` and `segment`.

-   **`loop`**: Represents a repeating hierarchical block (e.g., `2000A`). It contains a `children` array with its own nested loops and segments.
-   **`segment`**: Represents a specific instance of a segment at a certain position in the hierarchy. Its `xid` property links it back to its full definition in the `segmentDefinitions` dictionary.

### Example: A snippet of the `structure` array

This shows the `2000A` (Billing Provider) loop, which contains a segment (`HL`) and a nested loop (`2010AA`).

```json
[
  {
    "type": "loop",
    "xid": "ISA_LOOP",
    "name": "Interchange Control Header",
    "repeat": ">1",
    "children": [
      {
        "type": "segment",
        "xid": "ISA",
        "name": "Interchange Control Header",
        "...": "other properties"
      },
      {
        "type": "loop",
        "xid": "GS_LOOP",
        "name": "Functional Group Header",
        "children": [
          {
            "type": "loop",
            "xid": "ST_LOOP",
            "name": "Transaction Set Header",
            "children": [
              {
                "type": "segment",
                "xid": "ST",
                "name": "Transaction Set Header"
              },
              {
                "type": "loop",
                "xid": "HEADER",
                "name": "Table 1 - Header",
                "children": [
                    { "...": "BHT segment, 1000A loop, etc." }
                ]
              },
              {
                "type": "loop",
                "xid": "DETAIL",
                "name": "Table 2 - Detail",
                "children": [
                  {
                    "type": "loop",
                    "xid": "2000A",
                    "name": "Billing Provider Hierarchical Level",
                    "usage": "R",
                    "pos": "10",
                    "repeat": ">1",
                    "children": [
                      {
                        "type": "segment",
                        "xid": "HL",
                        "name": "Billing Provider Hierarchical Level",
                        "usage": "R",
                        "max_use": 1
                      },
                      {
                        "type": "loop",
                        "xid": "2010AA",
                        "name": "Billing Provider Name",
                        "repeat": 1,
                        "children": [
                          {
                            "type": "segment",
                            "xid": "NM1",
                            "name": "Billing Provider Name",
                            "usage": "R",
                            "max_use": 1,
                            "definitionId": "NM1_some_specialized_id"
                          },
                          { "...": "more segments in 2010AA loop" }
                        ]
                      },
                      { "...": "more loops/segments in 2000A loop" }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  }
]
```

-   The `definitionId` field in a `segment` is an optional override. If it exists, the parser uses that ID to look up the definition in `segmentDefinitions`. If not, it uses the segment's `xid`. This allows for specialized versions of common segments.