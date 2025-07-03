import React, { useState } from 'react';
import { ProcessedTransactionSchema, SchemaLoopDefinition } from '../ediSchema/schemaTypes';
import SegmentDisplay from './SegmentDisplay';
import { HierarchicalEdiLoop, HierarchicalEdiNode } from '../ediUtils/structureBuilder';

interface LoopDisplayProps {
    loopNode: HierarchicalEdiLoop; // Prop is correctly typed as the loop type
    schema: ProcessedTransactionSchema | null;
    level: number;
}

const LoopDisplay: React.FC<LoopDisplayProps> = ({ loopNode, schema, level }) => {
    const [isOpen, setIsOpen] = useState(true); // Default to expanded

    const handleToggle = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsOpen(!isOpen);
    };

    // Access properties correctly via loopNode interface
    const loopDef: SchemaLoopDefinition = loopNode.definition;
    const indentStyle = { paddingLeft: `${level * 1.5}rem` };

    // <<< NEW: Calculate child count >>>
    const childCount = loopNode.children.length;

    return (
        <div className="border-l border-b border-brand-border-subtle">
            <div
                className="flex items-center justify-between p-1.5 hover:bg-brand-surface-alt/40 rounded-t transition-colors cursor-pointer"
                style={indentStyle}
                onClick={handleToggle}
            >
                <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-brand-accent">{loopDef.xid}</span>
                    <span className="text-xs text-brand-text-secondary">- {loopDef.name}</span>
                    <span className="text-[10px] text-brand-text-muted">
                        (Usage: {loopDef.usage || '?'}, Repeat: {loopDef.repeat || '?'})
                    </span>
                    {loopNode.instanceNumber > 1 && (
                        <span className="text-[10px] text-brand-text-muted">
                            [Instance: {loopNode.instanceNumber}]
                        </span>
                    )}
                    {/* <<< NEW: Show child count when collapsed >>> */}
                    {!isOpen && childCount > 0 && (
                        <span className="text-[10px] text-brand-text-muted bg-brand-surface px-1 py-0.5 rounded">
                            {childCount} {childCount === 1 ? 'item' : 'items'}
                        </span>
                    )}
                </div>
                <svg
                    className={`w-4 h-4 text-brand-text-secondary transition-transform duration-200 ${isOpen ? 'rotate-90' : ''} flex-shrink-0`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                </svg>
            </div>

            {isOpen && (
                <div className="px-2 py-2 pl-4">
                    {loopNode.children.map((child: HierarchicalEdiNode, index: number) => {
                        // Use the type discriminator
                        if (child.type === 'loop') {
                            return (
                                <LoopDisplay
                                    // Access loopId safely BECAUSE child.type === 'loop'
                                    key={`${child.loopId}-${index}`}
                                    loopNode={child} // TS knows child is HierarchicalEdiLoop here
                                    schema={schema}
                                    level={level + 1}
                                />
                            );
                        } else if (child.type === 'segment') {
                            // child is known to be EdiSegment here
                            return (
                                <SegmentDisplay
                                    key={`${child.id}-${index}-${child.lineNumber}`}
                                    segment={child}
                                    schema={schema}
                                    level={level + 1}
                                    parentLoopSchemaDef={loopDef}
                                />
                            );
                        }
                        return null; // Should not happen if types are correct
                    })}
                    {loopNode.children.length === 0 && (
                        <p className="pl-4 py-1 text-xs text-brand-text-muted italic">
                            [No segments found in this loop instance]
                        </p>
                    )}
                </div>
            )}
        </div>
    );
};

export default LoopDisplay;