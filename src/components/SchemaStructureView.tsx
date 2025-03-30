import React from 'react';
import { ProcessedTransactionSchema, SchemaLoopDefinition, SchemaSegmentLink } from '../ediSchema/schemaTypes';
import SchemaLoopDisplay from './SchemaLoopDisplay';
import SchemaSegmentLinkDisplay from './SchemaSegmentLinkDisplay';

interface SchemaStructureViewProps {
    schema: ProcessedTransactionSchema | null;
    // isLoading and error props could be added if schema loading needs specific handling here
}

const SchemaStructureView: React.FC<SchemaStructureViewProps> = ({ schema }) => {

    const renderSchemaNode = (node: SchemaLoopDefinition | SchemaSegmentLink, index: number) => {
        if (node.type === 'loop') {
            return (
                <SchemaLoopDisplay
                    key={`${node.xid}-${index}`}
                    loopDef={node}
                    schema={schema}
                    level={0}
                />
            );
        } else if (node.type === 'segment') {
            return (
                <SchemaSegmentLinkDisplay
                    key={`${node.xid}-${index}`}
                    segmentLink={node}
                    schema={schema}
                    level={0}
                />
            );
        }
        // <<< FIX: Removed console.warn as this path is unreachable based on types >>>
        // console.warn(`[SchemaStructureView] Unexpected node type encountered: ${node.type}`);
        return null; // Fallback return
    };

    if (!schema) {
        return <p className="text-brand-text-muted italic text-center pt-10">Schema not loaded or is invalid.</p>;
    }

    if (!schema.structure || schema.structure.length === 0) {
        return <p className="text-brand-text-muted italic text-center pt-10">Schema loaded, but no structure defined.</p>;
    }

    return (
        <div className="space-y-1">
            {schema.structure.map(renderSchemaNode)}
        </div>
    );
};

export default SchemaStructureView;