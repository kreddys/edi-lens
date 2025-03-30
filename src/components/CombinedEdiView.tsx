import React, { ChangeEvent, useRef } from 'react';
// Import SampleFileInfo type from App.tsx
import { SampleFileInfo } from '../App'; // Adjust path as needed

interface CombinedEdiViewProps {
    displayValue: string;
    onValueChange: (text: string) => void;
    isInputMode: boolean;
    isProcessing: boolean;
    placeholder?: string;
    onClear: () => void;
    onUploadClick: () => void;
    isDisabled: boolean;
    samples: SampleFileInfo[]; // Receives the (potentially filtered) list
    onLoadSample: (sampleKey: string) => void;
}

const CombinedEdiView: React.FC<CombinedEdiViewProps> = ({
    displayValue,
    onValueChange,
    isInputMode,
    isProcessing,
    placeholder,
    onClear,
    onUploadClick,
    isDisabled,
    samples, // Receives filtered list
    onLoadSample,
}) => {
    const sampleSelectRef = useRef<HTMLSelectElement>(null);

    const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
        if (isDisabled) return;
        onValueChange(event.target.value);
    };

    const handleSampleChange = (event: ChangeEvent<HTMLSelectElement>) => {
        const selectedKey = event.target.value;
        if (selectedKey) {
            onLoadSample(selectedKey);
            if (sampleSelectRef.current) {
                sampleSelectRef.current.value = ''; // Reset dropdown
            }
        }
    };

    const labelText = isInputMode ? "EDI INPUT" : "EDI VIEW (FORMATTED)";
    const textareaTextColor = isInputMode ? 'text-brand-text-primary' : 'text-brand-text-secondary';

    const isClearDisabled = displayValue.length === 0 || isDisabled;
    const isUploadDisabled = isDisabled;
    // Disable sample dropdown if main control is disabled OR if there are no samples for the current schema
    const isSampleDisabled = isDisabled || samples.length === 0;

    return (
        <div className={`h-full flex flex-col relative bg-brand-surface border border-brand-border rounded-md ${isDisabled ? 'opacity-70' : ''}`}>
            {/* Header Area */}
            <div className="flex-shrink-0 flex items-center justify-between px-2 pt-1.5 pb-1 border-b border-brand-border-subtle gap-2 flex-wrap">
                <label htmlFor="combinedEdiTextArea" className="text-xs font-medium text-brand-text-secondary uppercase tracking-wider flex-shrink-0">
                    {labelText}
                </label>
                {/* Buttons Container */}
                <div className="flex items-center space-x-1 flex-wrap gap-y-1">
                    {/* Sample Loader Dropdown */}
                    <select
                        ref={sampleSelectRef}
                        onChange={handleSampleChange}
                        disabled={isSampleDisabled} // Updated disabled logic
                        className="text-xs bg-brand-surface-alt border border-brand-border rounded py-0.5 px-1.5 focus:ring-brand-accent focus:border-brand-accent text-brand-text-secondary disabled:opacity-50 disabled:cursor-not-allowed max-w-[150px]"
                        title={isSampleDisabled && samples.length === 0 && !isDisabled ? "No samples for selected schema" : "Load a sample EDI file"}
                        value="" // Keep value controlled by resetting on change
                    >
                        {/* Show different placeholder based on whether samples exist */}
                        {samples.length > 0 ? (
                            <option value="" disabled>Load Sample...</option>
                        ) : (
                            <option value="" disabled>No Samples</option>
                        )}
                        {/* Map over the received samples list */}
                        {samples.map(sample => (
                            <option key={sample.key} value={sample.key}>
                                {sample.name}
                            </option>
                        ))}
                    </select>

                    {/* Upload Button */}
                    <button
                        onClick={onUploadClick}
                        disabled={isUploadDisabled}
                        className="px-2 py-0.5 text-xs bg-brand-accent/80 hover:bg-brand-accent text-white rounded disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-1"
                        title="Upload EDI file"
                    >
                        {/* SVG Icon */}
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                        </svg>
                        Upload
                    </button>
                    {/* Clear Button */}
                    <button
                        onClick={onClear}
                        disabled={isClearDisabled}
                        className="px-2.5 py-0.5 text-xs bg-brand-surface-alt hover:bg-brand-border text-brand-text-secondary rounded disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Clear Input"
                    >
                        Clear
                    </button>
                </div>
            </div>

            {/* Text Area */}
            <div className="flex-grow relative overflow-hidden">
                <textarea
                    id="combinedEdiTextArea"
                    value={displayValue}
                    onChange={handleChange}
                    placeholder={placeholder}
                    className={`w-full h-full p-2 resize-none focus:outline-none text-sm font-mono whitespace-pre bg-transparent ${textareaTextColor} placeholder-brand-text-muted ${isDisabled ? 'cursor-not-allowed' : ''}`}
                    spellCheck="false"
                    readOnly={isDisabled || !isInputMode}
                />
            </div>

            {/* Processing Overlay */}
            {isProcessing && (
                <div className="absolute inset-0 bg-brand-surface/80 backdrop-blur-sm flex items-center justify-center rounded-md z-10">
                    <span className="text-brand-text-secondary animate-pulse text-lg">Processing EDI...</span>
                </div>
            )}
        </div>
    );
};

export default CombinedEdiView;