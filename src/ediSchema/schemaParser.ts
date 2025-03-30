// src/ediSchema/schemaParser.ts
// Contains helpers to retrieve definitions from a loaded ProcessedTransactionSchema.

import {
    SchemaSegmentDefinition,
    SchemaElementAttribute,
    SchemaCompositeAttribute,
    ProcessedTransactionSchema,
    // Removed: ProcessedSchema, SchemaLoopDefinition, SchemaSegmentLink
} from './schemaTypes';

// <<< REMOVED: ensureArray function >>>
// <<< REMOVED: allSegmentDefinitions variable >>>
// <<< REMOVED: parseAndStoreSegmentDefinition function >>>
// <<< REMOVED: buildLoopStructure function >>>
// <<< REMOVED: parseAndProcessSchema function (was already commented out) >>>


// Helper to get the generic segment definition (elements, composites)
// This function IS USED by SegmentDisplay and SchemaSegmentLinkDisplay
// to get element details based on the loaded JSON schema.
export const getSegmentDefinition = (
    schema: ProcessedTransactionSchema | null, // Simplified type, ProcessedSchema removed
    segmentId: string
): SchemaSegmentDefinition | undefined => {
    if (!schema || !segmentId) return undefined;
    // Access segment definitions directly from the ProcessedTransactionSchema structure
    // Assumes the schema object passed is always ProcessedTransactionSchema now
    if (schema.segmentDefinitions && typeof schema.segmentDefinitions === 'object') {
        return schema.segmentDefinitions[segmentId];
    }
    return undefined;
};

// Helper to get element definition (operates on SchemaSegmentDefinition)
// This function IS USED by SegmentDisplay via getSegmentDefinition.
export const getElementDefinition = (
    segmentDef: SchemaSegmentDefinition | undefined,
    elementIndex: number // 0-based index
): SchemaElementAttribute | SchemaCompositeAttribute | undefined => {
    if (!segmentDef || !segmentDef.elements || segmentDef.elements.length === 0) {
        return undefined;
    }
    // Convert 0-based index to 1-based sequence number string (e.g., 0 -> "01", 1 -> "02")
    const targetSeq = (elementIndex + 1).toString().padStart(2, '0');
    // Find the element definition whose sequence number matches
    return segmentDef.elements.find(el => String(el.seq) === targetSeq);
};