export interface SchemaElementAttribute {
    xid: string;
    data_ele: string;
    name: string;
    usage: 'R' | 'S' | 'N' | string;
    seq: string;
    // <<< FIX: Use a more precise union type >>>
    valid_codes?: { code: string | number | (string | number)[] };
    regex?: string;
    repeat?: string | number;
}

// ... rest of the file remains the same ...
export interface SchemaCompositeAttribute extends Omit<SchemaElementAttribute, 'data_ele' | 'valid_codes' | 'regex'> {
    data_ele: string;
    elements: SchemaElementAttribute[];
}

export interface SchemaSegmentDefinition {
    name: string;
    usage: 'R' | 'S' | 'N' | string;
    pos: string;
    max_use: string | number;
    syntax?: string | string[];
    elements: (SchemaElementAttribute | SchemaCompositeAttribute)[];
    elementsByXid?: Record<string, SchemaElementAttribute | SchemaCompositeAttribute>;
}

export interface SchemaSegmentLink {
    type: 'segment';
    xid: string;
    pos: string;
    usage: 'R' | 'S' | 'N' | string;
    max_use: string | number;
    name: string;
}

export interface SchemaLoopDefinition {
    type: 'loop';
    xid: string;
    name: string;
    usage: 'R' | 'S' | 'N' | string;
    pos: string;
    repeat: string | number;
    children: (SchemaSegmentLink | SchemaLoopDefinition)[];
}

export interface ProcessedTransactionSchema {
    transactionName: string;
    segmentDefinitions: Record<string, SchemaSegmentDefinition>;
    structure: (SchemaLoopDefinition | SchemaSegmentLink)[];
}

export type ProcessedSchema = Record<string, SchemaSegmentDefinition>;