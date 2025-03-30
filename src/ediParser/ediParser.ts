import { ParseEdiResult, EdiSegment, EdiElement } from './ediTypes';
import { AppLogger, noOpLogger } from '../logger';

const escapeRegex = (s: string) => s.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');

// Regex to validate typical X12 Segment IDs (2 or 3 uppercase letters/numbers)
const segmentIdRegex = /^[A-Z0-9]{2,3}$/;

export const parseEdi = (
    rawEdiString: string,
    logger: AppLogger = noOpLogger
): ParseEdiResult => {
    logger("[PARSE] Starting EDI document parsing", 'info');

    if (!rawEdiString || rawEdiString.trim().length === 0) {
        logger("[PARSE] Input string is empty", 'warn');
        return { data: null, error: "EDI string is empty." };
    }

    const normalizedEdi = rawEdiString.replace(/\r\n|\r/g, '\n');
    logger(`[PARSE] Normalized string (length: ${normalizedEdi.length})`, 'debug');

    let elementDelimiter = '*';
    let segmentDelimiter = '~';
    let componentDelimiter: string | undefined = ':';
    const isaHeaderLength = 106;

    if (normalizedEdi.startsWith('ISA') && normalizedEdi.length >= isaHeaderLength) {
        logger(`[PARSE] Found ISA segment at start. Length: ${normalizedEdi.length}`, 'debug');
        logger(`[PARSE-DEBUG] Char at index 3 (Element?): '${normalizedEdi[3]}' (Code: ${normalizedEdi.charCodeAt(3)})`, 'debug');
        logger(`[PARSE-DEBUG] Char at index 104 (Component?): '${normalizedEdi[104]}' (Code: ${normalizedEdi.charCodeAt(104)})`, 'debug');
        logger(`[PARSE-DEBUG] Char at index 105 (Segment?): '${normalizedEdi[105]}' (Code: ${normalizedEdi.charCodeAt(105)})`, 'debug');
        logger(`[PARSE-DEBUG] Char at index 103 (Before Component?): '${normalizedEdi[103]}' (Code: ${normalizedEdi.charCodeAt(103)})`, 'debug');

        const detectedElementDelimiter = normalizedEdi[3];
        const detectedSegmentDelimiter = normalizedEdi[105];
        const detectedComponentDelimiter = normalizedEdi[104];

        logger(`[PARSE] Attempting detection from raw string indices - Element:'${detectedElementDelimiter}', Segment:'${detectedSegmentDelimiter === '\n' ? '\\n' : detectedSegmentDelimiter}', Component:'${detectedComponentDelimiter}'`, 'debug');

        const alphanumeric = /^[a-z0-9]$/i;
        let useDetected = true;
        if (alphanumeric.test(detectedElementDelimiter) || alphanumeric.test(detectedSegmentDelimiter)) {
            logger(`[PARSE] Warning: Detected Element ('${detectedElementDelimiter}') or Segment ('${detectedSegmentDelimiter}') delimiter is alphanumeric. Check EDI validity.`, 'warn');
        }
        if (detectedElementDelimiter === detectedSegmentDelimiter ||
            detectedElementDelimiter === detectedComponentDelimiter ||
            (detectedComponentDelimiter && detectedSegmentDelimiter === detectedComponentDelimiter)) {
            logger(`[PARSE] Error: Detected delimiters are not unique (Elem:'${detectedElementDelimiter}', Seg:'${detectedSegmentDelimiter}', Comp:'${detectedComponentDelimiter}'). Cannot parse reliably. Reverting to defaults.`, 'error');
            useDetected = false;
            elementDelimiter = '*';
            segmentDelimiter = '~';
            componentDelimiter = ':';
        }

        if (useDetected) {
            elementDelimiter = detectedElementDelimiter;
            segmentDelimiter = detectedSegmentDelimiter;
            componentDelimiter = detectedComponentDelimiter;
            logger(`[PARSE] Delimiters successfully detected and assigned.`, 'info');
        } else {
            logger(`[PARSE] Reverted to default delimiters due to validation failure.`, 'info');
        }
    } else if (normalizedEdi.startsWith('ISA')) {
        logger(`[PARSE] ISA segment found, but too short (length ${normalizedEdi.length}) to reliably detect all delimiters. Using defaults.`, 'warn');
    } else {
        logger("[PARSE] ISA segment not found at start. Using default delimiters.", 'warn');
    }

    try {
        logger(`[PARSE] Using Delimiters - Element: '${elementDelimiter}', Segment: '${segmentDelimiter === '\n' ? '\\n' : segmentDelimiter}'`, 'info');

        const segmentSeparatorRegex = segmentDelimiter === '\n'
            ? /\n\s*/
            : new RegExp(escapeRegex(segmentDelimiter) + '\\s*');

        const trimmedNormalizedEdi = normalizedEdi.trim();
        const segmentStrings = trimmedNormalizedEdi.split(segmentSeparatorRegex);

        if (segmentStrings.length > 0 && segmentStrings[segmentStrings.length - 1] === '') {
            segmentStrings.pop();
        }

        logger(`[PARSE] Found ${segmentStrings.length} potential segment strings after split`, 'debug');

        const segments: EdiSegment[] = [];
        let cumulativeLines = 1;

        for (const rawSegmentPart of segmentStrings) {
            const approxLineNum = cumulativeLines;
            const trimmedSegment = rawSegmentPart.trim();

            if (trimmedSegment.length === 0) {
                cumulativeLines += (rawSegmentPart.match(/\n/g) || []).length;
                if (segmentDelimiter === '\n') cumulativeLines++;
                continue;
            }

            const elementSeparatorRegex = new RegExp(escapeRegex(elementDelimiter));
            const parts = trimmedSegment.split(elementSeparatorRegex);
            const segmentId = parts[0];

            if (!segmentId || !segmentIdRegex.test(segmentId)) {
                logger(`[PARSE] Invalid or non-standard segment ID "${segmentId}" found at approx line ${approxLineNum}. Skipping. Raw Trimmed: "${trimmedSegment}"`, 'warn');
                cumulativeLines += (rawSegmentPart.match(/\n/g) || []).length;
                if (segmentDelimiter === '\n') cumulativeLines++;
                continue;
            }

            // <<< NEW: Log successful segment identification >>>
            logger(`[PARSE-VALID] Identified segment ${segmentId} (Line ${approxLineNum})`, 'info');

            const elements: EdiElement[] = parts.slice(1).map((val) => {
                return { value: val };
            });

            segments.push({
                type: 'segment',
                id: segmentId,
                elements: elements,
                lineNumber: approxLineNum,
                rawSegmentString: trimmedSegment,
            });

            cumulativeLines += (rawSegmentPart.match(/\n/g) || []).length;
            if (segmentDelimiter === '\n' && rawSegmentPart !== segmentStrings[segmentStrings.length - 1]) {
                cumulativeLines++;
            }
        } // End segment loop

        if (segments.length === 0) {
            const errorMsg = "No valid segments found after parsing";
            logger(`[PARSE] ${errorMsg}`, 'error');
            return { data: null, error: errorMsg };
        }

        logger(`[PARSE] Successfully parsed ${segments.length} total segments`, 'info');

        return {
            data: {
                segments,
                delimiters: { element: elementDelimiter, segment: segmentDelimiter, component: componentDelimiter },
                rawEdiString: normalizedEdi,
            },
            error: null
        };

    } catch (error: any) {
        const errorMsg = `Parsing failed during segment processing: ${error.message}`;
        logger(`[PARSE] ${errorMsg}`, 'error');
        if (error.stack) logger(`[PARSE] Stack: ${error.stack}`, 'debug');
        return { data: null, error: errorMsg };
    }
};