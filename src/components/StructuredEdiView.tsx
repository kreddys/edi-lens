import React from 'react';
import { ParsedEdiData } from '../ediParser/ediTypes';
import { ProcessedTransactionSchema } from '../ediSchema/schemaTypes';
import SegmentDisplay from './SegmentDisplay';
import LoopDisplay from './LoopDisplay';
import { HierarchicalEdiNode } from '../ediUtils/structureBuilder';
import SchemaStructureView from './SchemaStructureView';

interface StructuredEdiViewProps {
    parsedData: ParsedEdiData | null;
    schema: ProcessedTransactionSchema | null;
    isLoading: boolean;
    error: string | null;
    hierarchicalNodes: HierarchicalEdiNode[];
    activeView: 'data' | 'schema';
    onViewChange: (view: 'data' | 'schema') => void;
}

// formatDelimiter implementation remains the same
const formatDelimiter = (char: string | undefined): string => {
    if (char === undefined) return '[N/A]';
    if (char === '\n') return '\\n';
    if (char === '\t') return '\\t';
    if (char === '\r') return '\\r';
    if (char === ' ') return '[space]';
    const nonPrintableMap: Record<string, string> = { '^': '^' }; // Add others if needed
    return nonPrintableMap[char] || char;
};


const StructuredEdiView: React.FC<StructuredEdiViewProps> = ({
    parsedData,
    schema,
    isLoading,
    error,
    hierarchicalNodes,
    activeView,
    onViewChange
}) => {

    const renderNode = (node: HierarchicalEdiNode, index: number) => {
        if (node.type === 'loop') {
            return (
                <LoopDisplay
                    key={`${node.loopId}-${index}`}
                    loopNode={node}
                    schema={schema}
                    level={0}
                />
            );
        } else if (node.type === 'segment') {
            // Segments at the top level shouldn't typically exist if hierarchy build worked
            // But render them if they do (e.g., orphans, simple files)
            return (
                <SegmentDisplay
                    key={`${node.id}-${index}-${node.lineNumber}`}
                    segment={node}
                    schema={schema}
                    level={0}
                />
            );
        }
        console.warn(`[StructuredEdiView] Unexpected node encountered in renderNode: ${JSON.stringify(node)}`);
        return null;
    };

    // Determine if the result is just a flat list (fallback when schema is missing/invalid or build fails)
    const isFlatList = hierarchicalNodes.length > 0 && hierarchicalNodes.every(node => node.type === 'segment');

    return (
        <div className="h-full flex flex-col bg-brand-surface border border-brand-border rounded-md">
            {/* Header with Tabs */}
            <div className="flex-shrink-0 flex items-center justify-between px-2 pt-1.5 pb-1 border-b border-brand-border-subtle">
                {/* <<< Label kept uppercase for consistency >>> */}
                <label className="text-xs font-medium text-brand-text-secondary uppercase tracking-wider">Structured View</label>
                <div className="flex space-x-1">
                    <button
                        onClick={() => onViewChange('data')}
                        disabled={isLoading}
                        className={`px-2.5 py-0.5 text-xs rounded transition-colors duration-200 ${activeView === 'data'
                                ? 'bg-brand-accent/90 text-white font-semibold shadow-sm' // Slightly adjusted active style
                                : 'bg-brand-surface-alt hover:bg-brand-border text-brand-text-secondary'
                            } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                        Parsed Data
                    </button>
                    <button
                        onClick={() => onViewChange('schema')}
                        disabled={isLoading || !schema} // Disable if no schema
                        className={`px-2.5 py-0.5 text-xs rounded transition-colors duration-200 ${activeView === 'schema'
                                ? 'bg-brand-accent/90 text-white font-semibold shadow-sm' // Slightly adjusted active style
                                : 'bg-brand-surface-alt hover:bg-brand-border text-brand-text-secondary'
                            } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                        Schema Definition
                    </button>
                </div>
            </div>

            {/* Content Area */}
            {/* Make this div scrollable and fill remaining space */}
            <div className="flex-grow overflow-auto relative text-sm p-2">
                {/* Loading indicator */}
                {isLoading && (
                    <div className="absolute inset-0 bg-brand-surface/80 flex items-center justify-center z-10 backdrop-blur-sm rounded-b-md">
                        <p className="text-brand-text-secondary animate-pulse text-lg">Loading...</p>
                    </div>
                )}
                {/* Error display */}
                {error && !isLoading && (
                    <div className="mb-3 p-3 border border-brand-error bg-brand-error-bg/30 rounded">
                        <p className="text-brand-error text-sm font-medium mb-1">Error</p>
                        <p className="text-brand-error/90 text-xs">{error}</p>
                    </div>
                )}

                {/* --- Conditional Rendering based on activeView --- */}

                {activeView === 'data' && !isLoading && (
                    <>
                        {/* Placeholder when no data */}
                        {!error && !parsedData && (
                            <p className="text-brand-text-muted italic text-center pt-10">Paste EDI data or Upload/Load Sample...</p>
                        )}

                        {/* Data Display Area */}
                        {parsedData && (
                            <div>
                                {/* File Info Header */}
                                <div className="mb-3 p-2 border border-brand-border-subtle rounded-md bg-brand-surface-alt">
                                    <h3 className="text-xs font-semibold text-brand-text-secondary mb-1.5 uppercase tracking-wider">File Delimiters</h3>
                                    <div className="flex flex-wrap gap-x-4 gap-y-1">
                                        <p className="text-xs text-brand-text-secondary">Elem: <code className="bg-brand-code-bg px-1.5 py-0.5 rounded font-mono text-brand-text-primary">{formatDelimiter(parsedData.delimiters.element)}</code></p>
                                        <p className="text-xs text-brand-text-secondary">Seg: <code className="bg-brand-code-bg px-1.5 py-0.5 rounded font-mono text-brand-text-primary">{formatDelimiter(parsedData.delimiters.segment)}</code></p>
                                        <p className="text-xs text-brand-text-secondary">Comp: <code className="bg-brand-code-bg px-1.5 py-0.5 rounded font-mono text-brand-text-primary">{formatDelimiter(parsedData.delimiters.component)}</code></p>
                                    </div>
                                </div>

                                {/* Schema warning or Flat list display */}
                                {isFlatList && !error && (
                                    <div className="mb-3 p-3 border border-brand-warning bg-brand-warning-bg/30 rounded">
                                        <p className="text-brand-warning text-sm font-medium mb-1">Schema / Structure Warning</p>
                                        <p className="text-brand-warning/90 text-xs">
                                            {!schema ? "Schema failed to load." :
                                                !schema.structure || schema.structure.length === 0 ? "Schema structure definition is empty." :
                                                    "Could not map segments to hierarchical schema structure."} Displaying flat list.
                                        </p>
                                    </div>
                                )}

                                {/* Render hierarchical or flat nodes */}
                                <div className="space-y-1">
                                    {hierarchicalNodes.length > 0 ? (
                                        hierarchicalNodes.map(renderNode)
                                    ) : (
                                        parsedData.segments.length === 0 && !error && (
                                            <p className="text-brand-text-muted italic text-center pt-10">EDI parsed, but no segments found.</p>
                                        )
                                    )}
                                </div>
                            </div>
                        )}
                    </>
                )}

                {activeView === 'schema' && !isLoading && (
                    <SchemaStructureView schema={schema} />
                )}

                {/* --- End Conditional Rendering --- */}
            </div>
        </div>
    );
};

export default StructuredEdiView;