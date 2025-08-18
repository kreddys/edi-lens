import type { TreeDataNode as AntdTreeDataNode } from "antd";

export interface SchemaNode {
    type: "loop" | "segment";
    xid: string;
    name: string;
    key?: string;
    segmentDefinitionId: string;
    contextDefinitionId?: string;
    children?: SchemaNode[];
    [key: string]: any;
}

export interface SchemaTreeDataNode extends AntdTreeDataNode {
    key: React.Key;
    data: SchemaNode;
    children?: SchemaTreeDataNode[];
}

export interface SchemaFile {
    transactionName: string;
    version: string;
    segmentDefinitions: Record<string, any>;
    contextualDefinitions: Record<string, any>;
    structure: SchemaNode[];
}

export interface SchemaListResponse {
    base_schemas: string[];
    specialized_schemas: string[];
}

export interface CodeDefinition {
    code: string | number;
    description?: string;
}

export interface BaseElement {
    xid: string;
    name: string;
    usage: 'R' | 'S' | 'N';
    seq: number;
    is_identifier?: boolean;
    valid_codes?: CodeDefinition[];
}

export interface SegmentDefinition {
    id: string;
    name: string;
    elements: BaseElement[];
    rules?: any[];
}

export interface ContextualDefinition {
    id: string;
    name: string;
    elements?: { [elementXid: string]: Partial<BaseElement> };
}