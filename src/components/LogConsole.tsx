import React, { useRef, useEffect } from 'react';

interface LogConsoleProps {
    messages: string[];
    isOpen: boolean; // Determines if the panel is expanded (height > footer)
    onToggle: () => void; // Function to call when the Max/Min button is clicked
    onClear: () => void;
}

const LogConsole: React.FC<LogConsoleProps> = ({ messages, isOpen, onToggle, onClear }) => {
    const consoleBodyRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Scroll to bottom only if it's open and the ref exists
        if (isOpen && consoleBodyRef.current) {
            consoleBodyRef.current.scrollTop = consoleBodyRef.current.scrollHeight;
        }
    }, [messages, isOpen]); // Trigger scroll on new messages or when opened

    // Dynamic height based on the isOpen state passed from App
    const consoleHeight = isOpen ? 'h-60' : 'h-[34px]'; // Full height or just footer height
    // Padding adjusted for consistency
    const headerPadding = 'p-1.5'; // Footer bar always has same padding
    const bodyPadding = isOpen ? 'px-2 pb-2' : ''; // Body padding only when open

    return (
        // Fixed position at the bottom, controlled height
        <div className={`fixed bottom-0 left-0 right-0 z-20 bg-brand-surface border-t border-brand-border shadow-lg transition-all duration-300 ease-in-out ${consoleHeight}`}>
            {/* Footer Bar (Always Visible) */}
            <div className={`flex items-center justify-between border-b border-brand-border-subtle ${headerPadding}`}>
                <span className="text-xs font-medium text-brand-text-secondary uppercase tracking-wider">
                    Processing Logs
                </span>
                {/* Controls are always in the footer */}
                <div className="flex items-center space-x-2">
                    <button
                        onClick={onClear}
                        disabled={messages.length === 0 && !isOpen} // Also disable clear if closed and empty
                        className="px-2 py-0.5 text-xs bg-brand-surface-alt hover:bg-brand-border text-brand-text-secondary rounded disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Clear Logs"
                    >
                        Clear
                    </button>
                    {/* This button now solely controls the open/closed state via onToggle */}
                    <button
                        onClick={onToggle} // Calls the handler passed from App.tsx
                        className="px-2 py-0.5 text-xs bg-brand-surface-alt hover:bg-brand-border text-brand-text-secondary rounded"
                        title={isOpen ? "Minimize Logs" : "Maximize Logs"}
                    >
                        {isOpen ? 'Minimize' : 'Maximize'}
                    </button>
                </div>
            </div>

            {/* Log Content Area (Conditionally Rendered based on isOpen) */}
            {/* Ensures content doesn't exist/render when closed */}
            {isOpen && (
                <div
                    ref={consoleBodyRef}
                    // Calculate height to fill space *above* the footer bar
                    className={`overflow-y-auto h-[calc(100%-35px)] text-[11px] font-mono ${bodyPadding}`}
                >
                    {messages.length === 0 ? (
                        <p className="text-brand-text-muted italic p-2 text-center">No log messages yet.</p>
                    ) : (
                        // Log message rendering with color coding (remains the same)
                        <pre className="whitespace-pre-wrap break-words">
                            {messages.map((msg, index) => {
                                let textColor = 'text-brand-text-primary';
                                if (msg.includes('[ERROR]')) {
                                    textColor = 'text-red-400';
                                } else if (msg.includes('[WARN]') || msg.includes('[BUILD-ORPHAN]')) {
                                    textColor = 'text-yellow-400';
                                } else if (msg.includes('[PARSE-VALID]') || msg.includes('[MATCH]')) {
                                    textColor = 'text-green-400';
                                } else if (msg.includes('[INFO]')) {
                                    textColor = 'text-brand-text-secondary';
                                } else if (msg.includes('[DEBUG]')) {
                                    textColor = 'text-brand-text-muted';
                                }
                                return (
                                    <div key={index} className={textColor}>
                                        {msg}
                                    </div>
                                );
                            })}
                        </pre>
                    )}
                </div>
            )}
        </div>
    );
};

export default LogConsole;