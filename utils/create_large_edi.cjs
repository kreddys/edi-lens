// create-large-edi.cjs
const fs = require('node:fs');
const path = require('node:path');

// --- Configuration ---
// **** MODIFY THESE VALUES AS NEEDED ****
const INPUT_FILE_PATH = './data/837p.test.0001.edi'; // Path to your source EDI file (relative to script location or absolute)
const OUTPUT_FILE_PATH = './data/837p.test.wrapped.edi'; // Path for the generated large EDI file
const TARGET_TRANSACTION_COUNT = 1; // Number of ST-SE transactions to generate
// ************************************

const ST_CONTROL_NUM_MIN_LENGTH = 4; // Minimum length for ST02/SE02 (adjust if needed)
const ST_CONTROL_NUM_MAX_LENGTH = 9; // Maximum length for ST02/SE02

// --- Helper Functions ---

/**
 * Extracts the value of a specific element from a segment string.
 * @param {string} segmentString The raw segment string (e.g., "ST*837*0001")
 * @param {string} elementDelimiter The element delimiter (e.g., "*")
 * @param {number} elementIndex 1-based index of the element to extract (e.g., 1 for ST01, 2 for ST02)
 * @returns {string | undefined} The element value or undefined if not found.
 */
function getElementValue(segmentString, elementDelimiter, elementIndex) {
    if (!segmentString || elementIndex < 1) return undefined;
    const elements = segmentString.split(elementDelimiter);
    // Adjust index for 0-based array access (elementIndex 1 is at array index 1)
    return elements.length > elementIndex ? elements[elementIndex] : undefined;
}

/**
 * Modifies a specific element within a segment string.
 * @param {string} segmentString The raw segment string.
 * @param {string} elementDelimiter The element delimiter.
 * @param {number} elementIndex 1-based index of the element to modify.
 * @param {string} newValue The new value for the element.
 * @returns {string} The modified segment string.
 */
function modifyElement(segmentString, elementDelimiter, elementIndex, newValue) {
    if (!segmentString || elementIndex < 1) return segmentString;
    const elements = segmentString.split(elementDelimiter);
    if (elements.length > elementIndex) {
        elements[elementIndex] = newValue;
    } else {
        // Handle cases where the element doesn't exist - add padding if necessary
        while (elements.length <= elementIndex) {
            elements.push('');
        }
        elements[elementIndex] = newValue;
    }
    return elements.join(elementDelimiter);
}

/**
 * Generates a padded Transaction Set Control Number.
 * @param {number} index The current transaction index (1-based).
 * @param {string} originalControlNum The original ST02 for length reference.
 * @returns {string} The padded control number.
 */
function generateStControlNumber(index, originalControlNum) {
    const originalLength = originalControlNum?.length || ST_CONTROL_NUM_MIN_LENGTH;
    const targetLength = Math.max(ST_CONTROL_NUM_MIN_LENGTH, Math.min(ST_CONTROL_NUM_MAX_LENGTH, originalLength));
    return String(index).padStart(targetLength, '0');
}

// Helper for escaping regex characters
function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // $& means the whole matched string
}


// --- Main Script Logic ---

async function main() {
    // 1. Use Configured Values
    const inputFile = path.resolve(__dirname, INPUT_FILE_PATH); // Resolve relative to script directory
    const outputFile = path.resolve(__dirname, OUTPUT_FILE_PATH);
    const transactionCount = TARGET_TRANSACTION_COUNT;

    if (transactionCount < 1) {
        console.error("Error: TARGET_TRANSACTION_COUNT in script must be a positive number.");
        process.exit(1);
    }

    console.log(`Input File: ${inputFile}`);
    console.log(`Output File: ${outputFile}`);
    console.log(`Target Transactions: ${transactionCount}`);

    // 2. Read Input File
    let rawEdiContent;
    try {
        rawEdiContent = fs.readFileSync(inputFile, 'utf8');
    } catch (err) {
        console.error(`Error reading input file "${inputFile}":`, err.message);
        process.exit(1);
    }

    // Normalize line endings
    const normalizedEdi = rawEdiContent.replace(/\r\n|\r/g, '\n').trim();
    if (normalizedEdi.length === 0) {
        console.error("Error: Input file is empty or contains only whitespace.");
        process.exit(1);
    }

    // 3. Detect Delimiters (rudimentary based on ISA)
    if (!normalizedEdi.startsWith('ISA') || normalizedEdi.length < 106) {
        console.error("Error: Input file does not start with a valid ISA segment or is too short.");
        process.exit(1);
    }
    const elementDelimiter = normalizedEdi[3];
    const segmentDelimiter = normalizedEdi[105]; // Can be tricky if ISA is exactly 105 chars
    const segmentDelimiterChar = segmentDelimiter === '\n' ? '\n' : segmentDelimiter; // Use actual char for splitting

    console.log(`Detected Element Delimiter: '${elementDelimiter}'`);
    console.log(`Detected Segment Delimiter: '${segmentDelimiter === '\n' ? '\\n' : segmentDelimiter}'`);

    // 4. Split into Segments
    const segmentSeparatorRegex = segmentDelimiterChar === '\n'
        ? /(\n)/ // Split by newline, keep newline as delimiter in result
        : new RegExp(escapeRegex(segmentDelimiterChar));

    const segments = normalizedEdi.split(segmentSeparatorRegex).filter(s => s && s.trim().length > 0);

    // 5. Extract Envelope Segments and First Transaction Template
    let isaSegment, gsSegment, firstStSegment, firstSeSegment, geSegment, ieaSegment;
    let firstStIndex = -1, firstSeIndex = -1, geIndex = -1;

    for (let i = 0; i < segments.length; i++) {
        const segment = segments[i].trim(); // Trim each segment before checking ID
        if (segment.startsWith('ISA' + elementDelimiter)) {
            isaSegment = segment;
        } else if (segment.startsWith('GS' + elementDelimiter)) {
            gsSegment = segment;
        } else if (firstStIndex === -1 && segment.startsWith('ST' + elementDelimiter)) {
            firstStSegment = segment;
            firstStIndex = i;
        } else if (firstStIndex !== -1 && firstSeIndex === -1 && segment.startsWith('SE' + elementDelimiter)) {
            const st02 = getElementValue(firstStSegment, elementDelimiter, 2);
            const se02 = getElementValue(segment, elementDelimiter, 2);
            if (st02 === se02) {
                firstSeSegment = segment;
                firstSeIndex = i;
            } else {
                console.warn(`Warning: Found SE segment at index ${i} with control number ${se02}, but it doesn't match the first ST control number ${st02}. Continuing search...`);
            }
        } else if (segment.startsWith('GE' + elementDelimiter)) {
            geSegment = segment;
            geIndex = i;
        } else if (segment.startsWith('IEA' + elementDelimiter)) {
            ieaSegment = segment;
        }
    }

    // Basic Validation
    if (!isaSegment) { console.error("Error: ISA segment not found."); process.exit(1); }
    if (!gsSegment) { console.error("Error: GS segment not found."); process.exit(1); }
    if (!firstStSegment) { console.error("Error: ST segment not found."); process.exit(1); }
    if (!firstSeSegment) { console.error("Error: Corresponding SE segment not found for the first ST."); process.exit(1); }
    if (!geSegment) { console.error("Error: GE segment not found."); process.exit(1); }
    if (!ieaSegment) { console.error("Error: IEA segment not found."); process.exit(1); }

    // Extract the template block (including ST and SE)
    const templateSegments = segments.slice(firstStIndex, firstSeIndex + 1).map(s => s.trim());
    const originalSt02 = getElementValue(firstStSegment, elementDelimiter, 2);
    console.log(`Using transaction template from index ${firstStIndex} to ${firstSeIndex} (Control#: ${originalSt02})`);

    // 6. Duplicate Transactions
    const duplicatedTransactions = [];
    console.log(`Generating ${transactionCount} transactions...`);
    for (let i = 1; i <= transactionCount; i++) {
        const newStControlNum = generateStControlNumber(i, originalSt02);
        const currentBlock = [...templateSegments]; // Create a copy

        // Modify ST02
        currentBlock[0] = modifyElement(currentBlock[0], elementDelimiter, 2, newStControlNum);
        // Modify SE02 (assuming SE is the last segment in the template)
        const seIndexInTemplate = currentBlock.length - 1;
        currentBlock[seIndexInTemplate] = modifyElement(currentBlock[seIndexInTemplate], elementDelimiter, 2, newStControlNum);

        // Add the modified block (as strings)
        duplicatedTransactions.push(...currentBlock);

        if (i % 1000 === 0) { // Log progress
            console.log(`  Generated ${i} transactions...`);
        }
    }
    console.log(`Finished generating transactions.`);


    // 7. Update GE Segment
    const updatedGeSegment = modifyElement(geSegment, elementDelimiter, 1, String(transactionCount));

    // Update IEA Segment (assuming only 1 GS group in the original and output)
    const updatedIeaSegment = modifyElement(ieaSegment, elementDelimiter, 1, '1'); // Assuming 1 GS group


    // 8. Reconstruct Output EDI String
    const outputParts = [
        isaSegment,
        gsSegment,
        ...duplicatedTransactions,
        updatedGeSegment,
        updatedIeaSegment
    ];

    const outputEdiString = outputParts.join(segmentDelimiterChar) + segmentDelimiterChar; // Add trailing delimiter

    // 9. Write Output File
    try {
        fs.writeFileSync(outputFile, outputEdiString, 'utf8');
        console.log(`Successfully created large EDI file: ${outputFile}`);
    } catch (err) {
        console.error(`Error writing output file "${outputFile}":`, err.message);
        process.exit(1);
    }
}

// Run the main function
main().catch(err => {
    console.error("An unexpected error occurred:", err);
    process.exit(1);
});