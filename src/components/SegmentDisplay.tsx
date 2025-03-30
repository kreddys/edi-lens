import React, { useState } from 'react';
import { EdiSegment } from '../ediParser/ediTypes';
// Remove SchemaSegmentDefinition as it's not directly used
import { ProcessedTransactionSchema, SchemaLoopDefinition, SchemaSegmentLink } from '../ediSchema/schemaTypes';
import { getSegmentDefinition, getElementDefinition } from '../ediSchema/schemaParser';
import ElementDisplay from './ElementDisplay';

interface SegmentDisplayProps {
    segment: EdiSegment;
    schema: ProcessedTransactionSchema | null;
    level: number;
    parentLoopSchemaDef?: SchemaLoopDefinition;
}

const SegmentDisplay: React.FC<SegmentDisplayProps> = ({ segment, schema, level, parentLoopSchemaDef }) => {
    // <<< CHANGE: Initialize isOpen to false so all segments are minimized by default >>>
    const [isOpen, setIsOpen] = useState(false);

    let segmentDisplayName = `Segment ${segment.id}`;

    if (parentLoopSchemaDef) {
        const segmentLink = parentLoopSchemaDef.children.find(
            (child) => child.type === 'segment' && child.xid === segment.id
        ) as SchemaSegmentLink | undefined;

        if (segmentLink?.name) {
            segmentDisplayName = segmentLink.name;
        } else {
            const genericSegmentDef = getSegmentDefinition(schema, segment.id);
            if (genericSegmentDef?.name) {
                segmentDisplayName = genericSegmentDef.name;
            }
            console.warn(`Segment ${segment.id} not found as SchemaSegmentLink in parent loop ${parentLoopSchemaDef.xid}. Using generic name.`);
        }
    } else {
        const genericSegmentDef = getSegmentDefinition(schema, segment.id);
        if (genericSegmentDef?.name) {
            segmentDisplayName = genericSegmentDef.name;
        }
    }

    const displaySegmentNameString = (segment.id === segmentDisplayName || segmentDisplayName === `Segment ${segment.id}`)
        ? ''
        : `- ${segmentDisplayName}`;

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
                    <span className="text-[10px] text-brand-text-muted font-mono w-5 text-right">{segment.lineNumber}</span>
                    <span className="font-semibold text-base text-brand-segment-id">{segment.id}</span>
                    <span className="text-xs text-brand-text-secondary">{displaySegmentNameString}</span>
                </div>
                <svg
                    className={`w-4 h-4 text-brand-text-secondary transition-transform duration-200 ${isOpen ? 'rotate-90' : ''} flex-shrink-0`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                </svg>
            </div>
            {isOpen && (
                <div className="py-2">
                    <div className="pl-6 pr-2">
                        {segment.elements.length === 0 && (
                            <p className="py-1 text-xs text-brand-text-muted italic">[No elements in segment]</p>
                        )}
                        {segment.elements.map((element, index) => {
                            const genericSegmentDef = getSegmentDefinition(schema, segment.id);
                            const elementDef = getElementDefinition(genericSegmentDef, index);
                            return (
                                <ElementDisplay
                                    key={`${segment.id}-${index}`}
                                    element={element}
                                    definition={elementDef}
                                    segmentId={segment.id}
                                    elementIndex={index}
                                />
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default SegmentDisplay;