import React, { useState } from 'react';
// <<< FIX: Removed SchemaSegmentDefinition import >>>
import { SchemaSegmentLink, ProcessedTransactionSchema } from '../ediSchema/schemaTypes';
// <<< FIX: Removed getElementDefinition import >>>
import { getSegmentDefinition } from '../ediSchema/schemaParser';
import ElementDisplay from './ElementDisplay'; // Reuse ElementDisplay

interface SchemaSegmentLinkDisplayProps {
    segmentLink: SchemaSegmentLink;
    schema: ProcessedTransactionSchema | null; // Need full schema to look up definition
    level: number;
}

const SchemaSegmentLinkDisplay: React.FC<SchemaSegmentLinkDisplayProps> = ({ segmentLink, schema, level }) => {
    // Segments in schema view default to collapsed, but can be expanded to see elements
    const [isOpen, setIsOpen] = useState(false);

    const segmentDef = getSegmentDefinition(schema, segmentLink.xid);
    const definitionName = segmentDef?.name || `Segment ${segmentLink.xid}`; // Generic name from definition
    const contextualName = segmentLink.name; // Name specific to this position in schema

    // Determine if the names are different enough to show both
    const displaySegmentNameString = (contextualName && contextualName !== definitionName)
        ? `- ${contextualName}`
        : '';

    const usageText = (u: string) => {
        switch (u) {
            case 'R': return 'Required';
            case 'S': return 'Situational';
            case 'N': return 'Not Used';
            default: return 'Unknown Usage';
        }
    };

    const getUsageColor = (usageChar: string): string => {
        switch (usageChar) {
            case 'R': return 'text-brand-usage-r';
            case 'S': return 'text-brand-usage-s';
            case 'N': return 'text-brand-usage-n';
            default: return 'text-brand-text-muted';
        }
    };

    const indentStyle = { paddingLeft: `${level * 1.5}rem` };

    const handleToggle = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsOpen(!isOpen);
    };

    return (
        <div className="border-b border-brand-border-subtle last:border-b-0" style={indentStyle}>
            <div
                className="flex items-center justify-between p-1.5 hover:bg-brand-surface-alt/40 rounded-t transition-colors cursor-pointer"
                onClick={handleToggle}
            >
                <div className="flex items-center gap-2 flex-wrap">
                    {/* Schema-specific info */}
                    <span className={`text-xs font-semibold w-3 text-center ${getUsageColor(segmentLink.usage)}`} title={usageText(segmentLink.usage)}>
                        {segmentLink.usage}
                    </span>
                    <span className="font-semibold text-base text-brand-segment-id">{segmentLink.xid}</span>
                    <span className="text-xs text-brand-text-secondary">{displaySegmentNameString}</span>
                    <span className="text-[10px] text-brand-text-muted">(Max Use: {segmentLink.max_use || '?'}, Pos: {segmentLink.pos})</span>
                    {!segmentDef && <span className="text-[10px] text-brand-error">(Def Missing!)</span>}
                </div>
                <svg
                    className={`w-4 h-4 text-brand-text-secondary transition-transform duration-200 ${isOpen ? 'rotate-90' : ''} flex-shrink-0`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                </svg>
            </div>
            {isOpen && segmentDef && (
                <div className="py-2">
                    <div className="pl-6 pr-2">
                        {/* Display Generic Definition Name if different */}
                        {contextualName && contextualName !== definitionName && (
                            <p className="text-[10px] text-brand-text-muted italic mb-1">Definition: {definitionName}</p>
                        )}
                        {segmentDef.elements.length === 0 && (
                            <p className="py-1 text-xs text-brand-text-muted italic">[No elements defined in schema]</p>
                        )}
                        {/* Use ElementDisplay to show element definitions */}
                        {segmentDef.elements.map((elementDef, index) => (
                            <ElementDisplay
                                key={`${segmentLink.xid}-def-${index}`}
                                // Provide a dummy element structure for ElementDisplay
                                element={{ value: '[Schema Definition]' }}
                                definition={elementDef} // Pass the actual definition
                                segmentId={segmentLink.xid}
                                elementIndex={index}
                            />
                        ))}
                    </div>
                </div>
            )}
            {isOpen && !segmentDef && (
                <p className="pl-8 py-1 text-xs text-brand-error italic">[Segment definition not found in schema file]</p>
            )}
        </div>
    );
};

export default SchemaSegmentLinkDisplay;