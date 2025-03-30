import React, { useState } from 'react';
import { ProcessedTransactionSchema, SchemaLoopDefinition } from '../ediSchema/schemaTypes';
import SchemaSegmentLinkDisplay from './SchemaSegmentLinkDisplay'; // Use the new component

interface SchemaLoopDisplayProps {
    loopDef: SchemaLoopDefinition; // Prop is the definition itself
    schema: ProcessedTransactionSchema | null; // Pass full schema down
    level: number;
}

const SchemaLoopDisplay: React.FC<SchemaLoopDisplayProps> = ({ loopDef, schema, level }) => {
    // Loops in schema view default to expanded
    const [isOpen, setIsOpen] = useState(true);

    const handleToggle = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsOpen(!isOpen);
    };

    const indentStyle = { paddingLeft: `${level * 1.5}rem` };

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
                        (Usage: {loopDef.usage || '?'}, Repeat: {loopDef.repeat || '?'}, Pos: {loopDef.pos})
                    </span>
                </div>
                <svg
                    className={`w-4 h-4 text-brand-text-secondary transition-transform duration-200 ${isOpen ? 'rotate-90' : ''} flex-shrink-0`}
                    fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                </svg>
            </div>

            {isOpen && (
                <div className="px-2 py-2 pl-4">
                    {loopDef.children.map((child, index) => {
                        if (child.type === 'loop') {
                            return (
                                <SchemaLoopDisplay // Recursive call for nested loops
                                    key={`${child.xid}-${index}`}
                                    loopDef={child} // Pass the nested loop definition
                                    schema={schema}
                                    level={level + 1}
                                />
                            );
                        } else if (child.type === 'segment') {
                            return (
                                <SchemaSegmentLinkDisplay // Use the new component for segment links
                                    key={`${child.xid}-${index}`}
                                    segmentLink={child} // Pass the segment link definition
                                    schema={schema}
                                    level={level + 1}
                                />
                            );
                        }
                        return null;
                    })}
                    {loopDef.children.length === 0 && (
                        <p className="pl-4 py-1 text-xs text-brand-text-muted italic">
                            [No segments or loops defined within this schema loop]
                        </p>
                    )}
                </div>
            )}
        </div>
    );
};

export default SchemaLoopDisplay;