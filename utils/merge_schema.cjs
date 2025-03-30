// mergeSchema.js
const fs = require('fs');
const path = require('path');

// --- Configuration ---
const sourceSchemaPath = path.resolve(__dirname, 'src/schemas/json/837.5010.X222.A1.json'); // 837P - Template for envelope STRUCTURE
const targetSchemaPath = path.resolve(__dirname, 'src/schemas/json/837Q3.I.5010.X223.A1.v2.json'); // 837I - Source for CONTENT and specific definitions
const outputSchemaPath = path.resolve(__dirname, 'src/schemas/json/837I.5010.X223.A2.merged.json'); // New output file name
const institutionalVersionCode = "005010X223A2"; // Correct version for 837I

console.log(`Source (Structure Template): ${sourceSchemaPath}`);
console.log(`Target (Content Source):   ${targetSchemaPath}`);
console.log(`Output Schema:             ${outputSchemaPath}`);

// Helper for deep copying
function deepCopy(obj) {
    if (typeof obj !== 'object' || obj === null) {
        return obj; // Return primitives and null as is
    }
    return JSON.parse(JSON.stringify(obj));
}

try {
    // --- Load Schemas ---
    console.log("Loading schemas...");
    const sourceSchemaContent = fs.readFileSync(sourceSchemaPath, 'utf-8');
    const targetSchemaContent = fs.readFileSync(targetSchemaPath, 'utf-8');

    const sourceSchema = JSON.parse(sourceSchemaContent); // Structure template
    const targetSchema = JSON.parse(targetSchemaContent); // Content source
    console.log("Schemas loaded successfully.");

    // --- 1. Extract Envelope Segment Definitions from Source ---
    console.log("Extracting envelope segment definitions from source schema...");
    const envelopeSegmentDefinitions = {};
    const envelopeSegmentIds = ['ISA', 'IEA', 'GS', 'GE'];
    for (const segId of envelopeSegmentIds) {
        if (sourceSchema.segmentDefinitions && sourceSchema.segmentDefinitions[segId]) {
            envelopeSegmentDefinitions[segId] = deepCopy(sourceSchema.segmentDefinitions[segId]);
            console.log(` -> Extracted definition for ${segId}`);
        } else {
            throw new Error(`Required envelope segment definition "${segId}" not found in source schema: ${sourceSchemaPath}`);
        }
    }

    // --- 2. Modify Copied GS Definition for 837I Version ---
    console.log(`Updating copied GS definition for version ${institutionalVersionCode}...`);
    const gsDef = envelopeSegmentDefinitions['GS'];
    if (gsDef && gsDef.elements) {
        const gs08 = gsDef.elements.find(el => el.xid === 'GS08');
        if (gs08 && gs08.valid_codes) {
            gs08.valid_codes.code = [institutionalVersionCode];
            // Update elementsByXid map as well
            if (gsDef.elementsByXid && gsDef.elementsByXid['GS08'] && gsDef.elementsByXid['GS08'].valid_codes) {
                gsDef.elementsByXid['GS08'].valid_codes.code = [institutionalVersionCode];
            }
            console.log(`   -> Updated GS08 version code.`);
        } else {
            console.warn("Could not find GS08 element or valid_codes to update version in copied GS definition.");
        }
    } else {
        console.warn("Could not process copied GS definition elements.");
    }


    // --- 3. Verify and Update Target ST Definition ---
    console.log("Verifying and updating ST definition in target schema...");
    const stDef = targetSchema.segmentDefinitions['ST'];
    const seDef = targetSchema.segmentDefinitions['SE'];

    if (!stDef) throw new Error("ST segment definition missing in target schema.");
    if (!seDef) throw new Error("SE segment definition missing in target schema.");

    // Update ST version code
    if (stDef && stDef.elements) {
        const st03 = stDef.elements.find(el => el.xid === 'ST03');
        if (st03 && st03.valid_codes) {
            st03.valid_codes.code = [institutionalVersionCode];
            console.log(`   -> Updated ST03 version code in target ST definition.`);
            if (stDef.elementsByXid && stDef.elementsByXid['ST03'] && stDef.elementsByXid['ST03'].valid_codes) {
                stDef.elementsByXid['ST03'].valid_codes.code = [institutionalVersionCode];
            }
        } else {
            console.warn("Could not find ST03 element or valid_codes to update version in target ST definition.");
        }
    } else {
        console.warn("Could not process target ST definition elements.");
    }

    // --- 4. Merge All Segment Definitions ---
    console.log("Merging segment definitions...");
    const mergedSegmentDefinitions = {
        ...envelopeSegmentDefinitions,
        ...targetSchema.segmentDefinitions
    };
    console.log(` -> Total merged definitions: ${Object.keys(mergedSegmentDefinitions).length}`);

    // --- 5. Extract Target's Transaction Content Structure ---
    console.log("Extracting transaction content structure from target schema...");
    let transactionContentNodes = [];
    if (targetSchema.structure && targetSchema.structure.length > 0) {
        const assumedContentLoop = targetSchema.structure.find(node => node.type === 'loop'); // Find first loop
        if (assumedContentLoop && assumedContentLoop.children) {
            // Check if this loop seems to contain ST/SE directly (incorrect structure in target)
            const containsST = assumedContentLoop.children.some(node => node.type === 'segment' && node.xid === 'ST');
            const containsSE = assumedContentLoop.children.some(node => node.type === 'segment' && node.xid === 'SE');

            if (containsST && containsSE) {
                // Filter out ST and SE links from the content nodes
                transactionContentNodes = deepCopy(assumedContentLoop.children.filter(
                    node => !(node.type === 'segment' && (node.xid === 'ST' || node.xid === 'SE'))
                ));
                console.log(` -> Found ${transactionContentNodes.length} content nodes inside target loop "${assumedContentLoop.xid}" (excluding ST/SE).`);
            } else {
                // Assume the loop's children ARE the content nodes
                transactionContentNodes = deepCopy(assumedContentLoop.children);
                console.log(` -> Found ${transactionContentNodes.length} content nodes inside target loop "${assumedContentLoop.xid}".`);
            }
        } else {
            console.warn(`Could not find a top-level loop in target schema or loop has no children. Assuming target structure IS the content.`);
            transactionContentNodes = deepCopy(targetSchema.structure);
        }
    }
    if (transactionContentNodes.length === 0) {
        throw new Error("Could not extract transaction content structure from target schema.");
    }

    // --- 6. Get Envelope Structural Links from Source ---
    console.log("Extracting envelope structural links from source schema...");
    const sourceIsaLoop = sourceSchema.structure.find(node => node.type === 'loop' && node.xid === 'ISA_LOOP');
    if (!sourceIsaLoop) throw new Error("ISA_LOOP structure not found in source schema.");
    const sourceGsLoop = sourceIsaLoop.children.find(node => node.type === 'loop' && node.xid === 'GS_LOOP');
    if (!sourceGsLoop) throw new Error("GS_LOOP structure not found in source schema.");
    // *** CORRECTION: Find ST_LOOP inside GS_LOOP in the source schema ***
    const sourceStLoop = sourceGsLoop.children.find(node => node.type === 'loop' && node.xid === 'ST_LOOP');
    if (!sourceStLoop) throw new Error("ST_LOOP structure not found within GS_LOOP in source schema.");

    // Get the actual segment *links*
    const isaLink = sourceIsaLoop.children.find(node => node.type === 'segment' && node.xid === 'ISA');
    const gsLink = sourceGsLoop.children.find(node => node.type === 'segment' && node.xid === 'GS');
    // *** CORRECTION: Find ST/SE links inside the source's ST_LOOP ***
    const stLink = sourceStLoop.children.find(node => node.type === 'segment' && node.xid === 'ST');
    const seLink = sourceStLoop.children.find(node => node.type === 'segment' && node.xid === 'SE');
    // GE and IEA are still direct children of GS_LOOP and ISA_LOOP respectively
    const geLink = sourceGsLoop.children.find(node => node.type === 'segment' && node.xid === 'GE');
    const ieaLink = sourceIsaLoop.children.find(node => node.type === 'segment' && node.xid === 'IEA');

    if (!gsLink || !stLink || !seLink || !geLink || !ieaLink) { // Removed isaLink check as it might not be structured that way
        // Construct a more detailed error message
        let missing = [];
        if (!gsLink) missing.push("GS Link in GS_LOOP");
        if (!stLink) missing.push("ST Link in ST_LOOP");
        if (!seLink) missing.push("SE Link in ST_LOOP");
        if (!geLink) missing.push("GE Link in GS_LOOP");
        if (!ieaLink) missing.push("IEA Link in ISA_LOOP");
        throw new Error(`Could not find required envelope segment links in source schema: ${missing.join(', ')}.`);
    }
    console.log(" -> Found all necessary envelope segment links.");

    // --- 7. Reconstruct the Final Structure ---
    console.log("Reconstructing final schema structure...");
    // Deep copy the structure templates to avoid modifying originals
    const finalIsaLoop = deepCopy(sourceIsaLoop);
    const finalGsLoop = deepCopy(sourceGsLoop);
    const finalStLoop = deepCopy(sourceStLoop); // Need ST_LOOP template properties

    // Clear children of template loops to rebuild them
    finalIsaLoop.children = [];
    finalGsLoop.children = [];
    finalStLoop.children = []; // Clear ST_LOOP children template

    // Build ST_LOOP with ST link, 837I content, and SE link
    finalStLoop.children = [
        deepCopy(stLink),
        ...transactionContentNodes, // Insert the actual 837I content loops/segments
        deepCopy(seLink)
    ];

    // Build GS_LOOP with GS link, the populated ST_LOOP, and GE link
    finalGsLoop.children = [
        deepCopy(gsLink),
        finalStLoop, // Add the fully constructed ST_LOOP
        deepCopy(geLink)
    ];

    // Build ISA_LOOP with GS_LOOP and IEA link
    finalIsaLoop.children = [
        finalGsLoop,
        deepCopy(ieaLink)
    ];

    const finalStructure = [finalIsaLoop]; // Final structure is just the ISA_LOOP

    // --- 8. Assemble Final Schema Object ---
    const finalSchema = {
        transactionName: targetSchema.transactionName.replace("837Q3", "837I"), // Use target's name, maybe normalize
        segmentDefinitions: mergedSegmentDefinitions,
        structure: finalStructure
    };

    // --- 9. Write Output ---
    console.log(`Writing merged schema to ${outputSchemaPath}...`);
    fs.writeFileSync(outputSchemaPath, JSON.stringify(finalSchema, null, 2), 'utf-8'); // Pretty print JSON
    console.log("Schema merge completed successfully!");

} catch (error) {
    console.error("Error during schema merging:", error);
    process.exit(1);
}