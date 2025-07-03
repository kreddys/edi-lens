import React from 'react';
import { EdiElement } from '../ediParser/ediTypes';
import { SchemaElementAttribute, SchemaCompositeAttribute } from '../ediSchema/schemaTypes';

interface ElementDisplayProps {
    element: EdiElement;
    definition: SchemaElementAttribute | SchemaCompositeAttribute | undefined;
    segmentId: string;
    elementIndex: number; // 0-based
}

const ElementDisplay: React.FC<ElementDisplayProps> = ({ element, definition, segmentId, elementIndex }) => {
    const elementPos = (elementIndex + 1).toString().padStart(2, '0');
    const elementId = `${segmentId}${elementPos}`;

    const name = definition?.name || `Element ${elementPos}`;
    const description = definition?.data_ele ? `(DE ${definition.data_ele})` : '';
    const usage = definition?.usage?.toUpperCase() || '?';
    const isComposite = definition && 'elements' in definition && definition.elements.length > 0;

    const validCodes = (definition && 'valid_codes' in definition)
        ? definition.valid_codes?.code
        : undefined;

    const getUsageColor = (usageChar: string): string => {
        switch (usageChar) {
            case 'R': return 'text-brand-usage-r';
            case 'S': return 'text-brand-usage-s';
            case 'N': return 'text-brand-usage-n';
            default: return 'text-brand-text-muted';
        }
    };

    const usageText = (u: string) => {
        switch (u) {
            case 'R': return 'Required';
            case 'S': return 'Situational';
            case 'N': return 'Not Used';
            default: return 'Unknown Usage';
        }
    }

    // This function should still work correctly with the new type
    const formatValidCodes = (codes: string | number | (string | number)[] | undefined): string => {
        if (codes === undefined) return '';
        if (Array.isArray(codes)) {
            return codes.map(String).join(' | ');
        }
        return String(codes);
    }

    return (
        <div className="py-1.5 border-b border-brand-border-subtle last:border-b-0">
            {/* ... (rest of JSX is identical to previous correct version) ... */}
            {/* Row 1: Usage, Name, ID, Description */}
            <div className="flex justify-between items-start flex-wrap gap-x-2 mb-1">
                <div className="flex items-center space-x-2 flex-grow">
                    <span
                        className={`text-xs font-semibold w-3 text-center ${getUsageColor(usage)}`}
                        title={usageText(usage)}
                    >
                        {usage}
                    </span>
                    <span className="text-sm font-medium text-brand-text-primary">{name}</span>
                    <span className="text-xs text-brand-text-muted">{description} {isComposite ? ' (Composite)' : ''}</span>
                </div>
                <span className="text-[10px] text-brand-text-muted font-mono pt-0.5">{elementId}</span>
            </div>

            {/* Row 2: Value */}
            <div className="pl-5 mb-1">
                <span className="text-xs font-mono bg-brand-code-bg px-1.5 py-0.5 rounded break-all text-brand-text-primary">
                    {element.value || <span className="italic text-brand-text-muted">[Empty]</span>}
                </span>
            </div>

            {/* Row 3: Valid Codes (Optional) */}
            {validCodes && (!Array.isArray(validCodes) || validCodes.length > 0) && (
                <div className="pl-5 mt-1">
                    <span className="text-[10px] text-brand-text-secondary mr-1">Codes:</span>
                    <span className="text-[10px] font-mono text-brand-text-secondary break-words">
                        {formatValidCodes(validCodes)}
                    </span>
                </div>
            )}

            {/* Row 4: Composite Definition (Optional) */}
            {isComposite && 'elements' in definition && definition.elements && (
                <div className="mt-1.5 ml-5 pl-3 border-l border-dashed border-brand-border">
                    <span className="text-[10px] text-brand-text-secondary italic block mb-0.5">Composite Definition:</span>
                    {definition.elements.map((subEl) => (
                        <div key={subEl.xid} className="text-[10px] text-brand-text-secondary mb-0.5 ml-1">
                            {subEl.seq}: {subEl.name} ({subEl.data_ele}) <span className={`font-medium ${getUsageColor(subEl.usage)}`}>({subEl.usage})</span>
                            {/* Optionally display sub-element valid codes here if needed */}
                        </div>
                    ))}
                    <span className="text-[10px] text-amber-400 italic block mt-0.5 ml-1">[Note: Basic parser displays raw composite value above.]</span>
                </div>
            )}
        </div>
    );
};

export default ElementDisplay;