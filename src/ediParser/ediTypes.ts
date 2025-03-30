export interface EdiElement {
    value: string;
    // Future enhancement: Add support for composite elements
    // componentValues?: string[];
}

export interface EdiSegment {
    type: 'segment'; // <<< ADDED type discriminator
    id: string; // e.g., ISA, GS, NM1
    elements: EdiElement[];
    lineNumber: number; // Original line number (approximate)
    rawSegmentString: string; // Store the original segment string
}

export interface ParsedEdiData {
    segments: EdiSegment[];
    delimiters: {
        element: string;
        segment: string;
        component?: string; // Optional: store if detected
    };
    rawEdiString: string; // Keep the original raw string
}

export interface ParseEdiResult {
    data: ParsedEdiData | null;
    error: string | null;
}