import { ParsedEdiData, EdiSegment } from '../ediParser/ediTypes';
import {
    ProcessedTransactionSchema,
    SchemaLoopDefinition,
    // <<< FIX: Removed unused SchemaSegmentLink import >>>
} from '../ediSchema/schemaTypes';
import { AppLogLevel } from '../logger';

type LogCollector = (message: string, level?: AppLogLevel) => void;

export interface HierarchicalEdiLoop {
    type: 'loop';
    definition: SchemaLoopDefinition;
    loopId: string;
    children: HierarchicalEdiNode[];
    instanceNumber: number;
}

export type HierarchicalEdiNode = HierarchicalEdiLoop | EdiSegment;

const findFirstSegmentTrigger = (loopDef: SchemaLoopDefinition): string | null => {
    if (!loopDef.children || loopDef.children.length === 0) return null;
    for (const child of loopDef.children) {
        if (child.type === 'segment') return child.xid;
        if (child.type === 'loop') {
            const nestedTrigger = findFirstSegmentTrigger(child);
            if (nestedTrigger) return nestedTrigger;
        }
    }
    return null;
};

const validateTriggerSegment = (
    segment: EdiSegment,
    loopDef: SchemaLoopDefinition,
    logCollector: LogCollector
): boolean => {
    const logPrefix = `ValidateTrigger[${loopDef.xid} for ${segment.id}(L${segment.lineNumber})]:`;
    logCollector(`${logPrefix} Segment ID matches expected trigger for loop. Passing structural trigger validation.`, 'debug');
    return true;
};

const processLoop = (
    loopDef: SchemaLoopDefinition,
    startIndex: number,
    instanceNum: number,
    currentSegments: EdiSegment[],
    logCollector: LogCollector,
    schema: ProcessedTransactionSchema | null,
    depth: number = 0
): { loopNode: HierarchicalEdiLoop | null; endIndex: number } => {
    const logPrefix = `${"  ".repeat(depth)}Loop[${loopDef.xid}#${instanceNum}]:`;
    logCollector(`${logPrefix} Entering processLoop, startIndex=${startIndex}`, 'debug');

    const loopNode: HierarchicalEdiLoop = {
        type: 'loop',
        definition: loopDef,
        loopId: `${loopDef.xid}_${instanceNum}`,
        children: [],
        instanceNumber: instanceNum
    };

    let localIndex = startIndex;
    let segmentsConsumedInLoop = 0;

    for (const [childIndex, childDef] of loopDef.children.entries()) {
        logCollector(`${logPrefix} -> Processing schema child ${childIndex + 1}/${loopDef.children.length}: ${childDef.type} ${childDef.xid} (Usage: ${childDef.usage}), Current localIndex=${localIndex}`, 'debug');

        if (localIndex >= currentSegments.length) {
            logCollector(`${logPrefix} -> Ran out of segments while expecting schema child ${childDef.type} ${childDef.xid}.`, 'debug');
            if (childDef.usage === 'R') {
                logCollector(`${logPrefix} -> FATAL (for this loop instance): Ran out of segments, but required ${childDef.type} ${childDef.xid} was expected. Aborting loop processing.`, 'error');
                const isFirstRequiredChild = childIndex === 0 || loopNode.children.length === 0;
                return { loopNode: !isFirstRequiredChild ? loopNode : null, endIndex: startIndex };
            }
            break;
        }

        if (childDef.type === 'segment') {
            let foundCount = 0;
            const maxUse = parseInt(String(childDef.max_use)) || 1;
            logCollector(`${logPrefix} -> Looking for segment ${childDef.xid} (maxUse: ${maxUse}) starting at index ${localIndex}`, 'debug');

            while (localIndex < currentSegments.length &&
                currentSegments[localIndex].id === childDef.xid &&
                foundCount < maxUse) {

                logCollector(`${logPrefix}  [MATCH] --> Segment ${currentSegments[localIndex].id}(L${currentSegments[localIndex].lineNumber}) matched schema segment ${childDef.xid} ('${childDef.name}')`, 'info');

                loopNode.children.push(currentSegments[localIndex]);
                localIndex++;
                segmentsConsumedInLoop++;
                foundCount++;
            }
            logCollector(`${logPrefix} -> Finished segment ${childDef.xid}. Found: ${foundCount}. New localIndex=${localIndex}`, 'debug');

            if (foundCount === 0 && childDef.usage === 'R') {
                logCollector(`${logPrefix} -> FATAL (for this loop instance): Missing required segment ${childDef.xid}. Aborting loop processing.`, 'error');
                const isFirstRequiredChild = (childIndex === 0);
                return { loopNode: !isFirstRequiredChild ? loopNode : null, endIndex: startIndex };
            }
        } else if (childDef.type === 'loop') {
            let nestedInstanceNum = 1;
            const maxRepeatStr = childDef.repeat;
            const maxRepeat = maxRepeatStr === '>1' ? Infinity : (parseInt(String(maxRepeatStr)) || 1);
            const firstNestedSegmentId = findFirstSegmentTrigger(childDef);

            if (!firstNestedSegmentId) {
                logCollector(`${logPrefix} -> ERROR: Loop ${childDef.xid} has no trigger segment defined in schema. Skipping processing this loop definition.`, 'error');
                if (childDef.usage === 'R') {
                    logCollector(`${logPrefix} -> Required loop ${childDef.xid} cannot be processed due to schema error. Aborting parent loop.`, 'error');
                    const isFirstRequiredChild = (childIndex === 0);
                    return { loopNode: !isFirstRequiredChild ? loopNode : null, endIndex: startIndex };
                }
                continue;
            }

            logCollector(`${logPrefix} -> Looking for nested loop ${childDef.xid} (trigger ${firstNestedSegmentId}, maxRepeat: ${maxRepeat}, Usage: ${childDef.usage}) starting search at index ${localIndex}`, 'debug');

            let processedAnyInstances = false;

            while (nestedInstanceNum <= maxRepeat && localIndex < currentSegments.length) {
                logCollector(`${logPrefix} -> Attempting to find instance #${nestedInstanceNum} of loop ${childDef.xid}`, 'debug');

                const currentSegment = currentSegments[localIndex]; // <<< Use currentSegment here

                if (currentSegment.id !== firstNestedSegmentId) {
                    logCollector(`${logPrefix}    -> Segment ${currentSegment.id}(L${currentSegment.lineNumber}) at index ${localIndex} does not match trigger ${firstNestedSegmentId}. Breaking instance search for ${childDef.xid}.`, 'debug');
                    break;
                }

                if (!validateTriggerSegment(currentSegment, childDef, logCollector)) {
                    logCollector(`${logPrefix}    -> Segment ${currentSegment.id}(L${currentSegment.lineNumber}) at index ${localIndex} failed structural trigger validation for loop ${childDef.xid}. Breaking instance search.`, 'warn');
                    break;
                }

                // <<< FIX: Use currentSegment instead of triggerSegment >>>
                logCollector(`${logPrefix}  [MATCH-TRIGGER] -> Segment ${currentSegment.id}(L${currentSegment.lineNumber}) triggers nested loop ${childDef.xid} ('${childDef.name}') instance #${nestedInstanceNum}`, 'info');

                logCollector(`${logPrefix} -> Found valid start for nested loop ${childDef.xid} instance ${nestedInstanceNum} at index ${localIndex}. Calling processLoop recursively.`, 'debug');
                const nestedResult = processLoop(
                    childDef,
                    localIndex,
                    nestedInstanceNum,
                    currentSegments,
                    logCollector,
                    schema,
                    depth + 1
                );
                logCollector(`${logPrefix}    -> Recursive call result for ${childDef.xid}#${nestedInstanceNum}: loopNode exists=${!!nestedResult.loopNode}, endIndex=${nestedResult.endIndex}`, 'debug');

                if (nestedResult.loopNode && nestedResult.endIndex > localIndex) {
                    logCollector(`${logPrefix}    -> Successfully processed nested loop ${childDef.xid}#${nestedInstanceNum}. Consumed ${nestedResult.endIndex - localIndex} segments.`, 'debug');
                    loopNode.children.push(nestedResult.loopNode);
                    const consumedCountInNested = nestedResult.endIndex - localIndex;
                    segmentsConsumedInLoop += consumedCountInNested;
                    localIndex = nestedResult.endIndex;
                    logCollector(`${logPrefix}    -> Updated localIndex to ${localIndex}.`, 'debug');
                    nestedInstanceNum++;
                    processedAnyInstances = true;
                    logCollector(`${logPrefix}  [END-LOOP] <-- Finished processing nested loop ${nestedResult.loopNode.loopId}`, 'debug');
                } else {
                    logCollector(`${logPrefix}    -> Processing nested loop ${childDef.xid} instance ${nestedInstanceNum} returned null/empty or didn't advance index (endIndex=${nestedResult.endIndex}, localIndex=${localIndex}). Breaking instance search.`, 'warn');
                    break;
                }
            } // End while looking for nested instances

            if (!processedAnyInstances && childDef.usage === 'R') {
                logCollector(`${logPrefix} -> FATAL (for this loop instance): Did not process ANY instances of required nested loop ${childDef.xid}. Aborting parent loop processing.`, 'error');
                const isFirstRequiredChild = (childIndex === 0);
                return { loopNode: !isFirstRequiredChild ? loopNode : null, endIndex: startIndex };
            }
        }
    } // End for loop over loopDef.children

    const finalEndIndex = localIndex;
    logCollector(`${logPrefix} Exiting processLoop. Consumed locally: ${segmentsConsumedInLoop}. Final localIndex: ${finalEndIndex}. Children added: ${loopNode.children.length}`, 'debug');

    return { loopNode, endIndex: finalEndIndex };
};

export const buildHierarchicalData = (
    parsedData: ParsedEdiData | null,
    schema: ProcessedTransactionSchema | null,
    logCollector: LogCollector
): HierarchicalEdiNode[] => {

    if (!parsedData || !parsedData.segments || parsedData.segments.length === 0) {
        logCollector("[BUILD] No parsed segments to process.", 'info');
        return [];
    }
    if (!schema || !schema.structure || schema.structure.length === 0) {
        logCollector("[BUILD] Schema structure is missing or empty. Returning flat list.", 'warn');
        return [...parsedData.segments];
    }

    logCollector("[BUILD] Starting hierarchical structure build...", 'info');
    const allSegments = [...parsedData.segments];
    const result: HierarchicalEdiNode[] = [];
    let currentGlobalIndex = 0;
    let segmentConsumedFlags = new Array(allSegments.length).fill(false);
    logCollector(`[BUILD] Total segments to process: ${allSegments.length}`, 'info');

    for (const topLevelDef of schema.structure) {
        logCollector(`[BUILD] Processing top-level schema definition: ${topLevelDef.type} ${topLevelDef.xid}`, 'debug');
        if (currentGlobalIndex >= allSegments.length) {
            logCollector("[BUILD] Reached end of segments while processing schema.", 'debug');
            break;
        }

        if (topLevelDef.type === 'loop') {
            let instanceNum = 1;
            const repeatStr = topLevelDef.repeat;
            const maxRepeat = repeatStr === '>1' ? Infinity : (parseInt(String(repeatStr)) || 1);
            logCollector(`[BUILD] -> Looking for top-level loop ${topLevelDef.xid}, maxRepeat=${maxRepeat}. Search starting from globalIndex ${currentGlobalIndex}`, 'debug');

            const firstSegmentId = findFirstSegmentTrigger(topLevelDef);
            if (!firstSegmentId) {
                logCollector(`[BUILD] -> ERROR: Schema definition for top-level loop ${topLevelDef.xid} has no trigger segment. Skipping this schema entry.`, 'error');
                continue;
            }
            logCollector(`[BUILD] -> Trigger segment for ${topLevelDef.xid} is ${firstSegmentId}`, 'debug');

            while (instanceNum <= maxRepeat && currentGlobalIndex < allSegments.length) {
                logCollector(`[BUILD] -> Searching for instance #${instanceNum} of ${topLevelDef.xid} starting at index ${currentGlobalIndex}`, 'debug');

                let loopStartIndex = -1;
                for (let i = currentGlobalIndex; i < allSegments.length; i++) {
                    if (!segmentConsumedFlags[i] && allSegments[i].id === firstSegmentId) {
                        loopStartIndex = i;
                        break;
                    }
                }
                logCollector(`[BUILD] -> Result of findIndex for trigger ${firstSegmentId}: ${loopStartIndex}`, 'debug');

                if (loopStartIndex === -1) {
                    logCollector(`[BUILD] -> No more unconsumed trigger segments ('${firstSegmentId}') found for loop ${topLevelDef.xid}. Breaking instance search.`, 'debug');
                    break;
                }

                if (loopStartIndex > currentGlobalIndex) {
                    logCollector(`[BUILD] -> Found trigger at index ${loopStartIndex}, but current index is ${currentGlobalIndex}. Checking for skipped segments.`, 'debug');
                    const skippedSegments: EdiSegment[] = [];
                    for (let i = currentGlobalIndex; i < loopStartIndex; i++) {
                        if (!segmentConsumedFlags[i]) {
                            skippedSegments.push(allSegments[i]);
                            segmentConsumedFlags[i] = true;
                        }
                    }
                    if (skippedSegments.length > 0) {
                        skippedSegments.forEach(seg => {
                            logCollector(`[BUILD-ORPHAN] Segment ${seg.id}(L${seg.lineNumber}) added as unhandled (before loop ${topLevelDef.xid})`, 'warn');
                            result.push(seg);
                        });
                    }
                    currentGlobalIndex = loopStartIndex;
                    logCollector(`[BUILD] -> Advanced globalIndex to ${currentGlobalIndex} after handling skipped segments.`, 'debug');
                }

                if (currentGlobalIndex >= allSegments.length || segmentConsumedFlags[currentGlobalIndex]) {
                    logCollector(`[BUILD] -> Index out of bounds or segment already consumed (${currentGlobalIndex}) before processing loop trigger. Breaking instance search.`, 'error');
                    break;
                }
                const triggerSegment = allSegments[currentGlobalIndex];

                if (!validateTriggerSegment(triggerSegment, topLevelDef, logCollector)) {
                    logCollector(`[BUILD] -> Trigger segment ${triggerSegment.id}(L${triggerSegment.lineNumber}) at index ${currentGlobalIndex} failed validation for loop ${topLevelDef.xid}. Treating as unhandled.`, 'warn');
                    logCollector(`[BUILD-ORPHAN] Segment ${triggerSegment.id}(L${triggerSegment.lineNumber}) added as unhandled (invalid trigger for loop ${topLevelDef.xid})`, 'warn');
                    result.push(triggerSegment);
                    segmentConsumedFlags[currentGlobalIndex] = true;
                    currentGlobalIndex++;
                    continue;
                }

                logCollector(`[BUILD-MATCH-TRIGGER] -> Segment ${triggerSegment.id}(L${triggerSegment.lineNumber}) triggers top-level loop ${topLevelDef.xid} ('${topLevelDef.name}') instance #${instanceNum}`, 'info');

                logCollector(`[BUILD] -> Trigger segment validated. Calling processLoop for ${topLevelDef.xid}#${instanceNum} starting at index ${currentGlobalIndex}`, 'debug');
                const loopResult = processLoop(
                    topLevelDef,
                    currentGlobalIndex,
                    instanceNum,
                    allSegments,
                    logCollector,
                    schema,
                    1
                );
                logCollector(`[BUILD] -> Result from processLoop for ${topLevelDef.xid}#${instanceNum}: node exists=${!!loopResult.loopNode}, endIndex=${loopResult.endIndex}`, 'debug');

                if (loopResult.loopNode && loopResult.endIndex > currentGlobalIndex) {
                    result.push(loopResult.loopNode);
                    const consumedCount = loopResult.endIndex - currentGlobalIndex;
                    logCollector(`[BUILD] -> Loop ${topLevelDef.xid}#${instanceNum} processed successfully, consumed ${consumedCount} segments. Advancing globalIndex from ${currentGlobalIndex} to ${loopResult.endIndex}.`, 'debug');
                    for (let i = currentGlobalIndex; i < loopResult.endIndex; i++) {
                        if (i < segmentConsumedFlags.length) {
                            if (segmentConsumedFlags[i]) {
                                logCollector(`[BUILD] -> WARNING: Segment at index ${i} (${allSegments[i]?.id}) was already marked consumed but is being consumed again by loop ${topLevelDef.xid}#${instanceNum}.`, 'warn');
                            }
                            segmentConsumedFlags[i] = true;
                        } else {
                            logCollector(`[BUILD] -> WARNING: Attempted to mark consumed flag out of bounds at index ${i}`, 'warn');
                        }
                    }
                    currentGlobalIndex = loopResult.endIndex;
                    instanceNum++;
                    logCollector(`[BUILD] [END-LOOP] <-- Finished processing top-level loop ${loopResult.loopNode.loopId}`, 'debug');
                } else {
                    logCollector(`[BUILD] -> WARN: processLoop for ${topLevelDef.xid}#${instanceNum} returned null or failed to advance index (endIndex=${loopResult.endIndex}, startIndex=${currentGlobalIndex}). Treating trigger ${triggerSegment.id}(L${triggerSegment.lineNumber}) as unhandled.`, 'warn');
                    logCollector(`[BUILD-ORPHAN] Segment ${triggerSegment.id}(L${triggerSegment.lineNumber}) added as unhandled (failed processing for loop ${topLevelDef.xid})`, 'warn');
                    result.push(triggerSegment);
                    segmentConsumedFlags[currentGlobalIndex] = true;
                    currentGlobalIndex++;
                    logCollector(`[BUILD] -> Added orphaned trigger ${triggerSegment.id} to results. Advanced globalIndex to ${currentGlobalIndex}. Breaking instance search for ${topLevelDef.xid}.`, 'debug');
                    break;
                }
            } // End while loop searching for instances

            if (instanceNum === 1 && topLevelDef.usage === 'R') {
                logCollector(`[BUILD] -> WARNING: Required top-level loop ${topLevelDef.xid} was not found or no instances were successfully processed.`, 'warn');
            }
        } else if (topLevelDef.type === 'segment') {
            logCollector(`[BUILD] -> Looking for top-level segment ${topLevelDef.xid} (Usage: ${topLevelDef.usage}) starting search at globalIndex ${currentGlobalIndex}`, 'debug');
            let foundCount = 0;
            const maxUse = parseInt(String(topLevelDef.max_use)) || 1;

            while (foundCount < maxUse &&
                currentGlobalIndex < allSegments.length &&
                !segmentConsumedFlags[currentGlobalIndex] &&
                allSegments[currentGlobalIndex].id === topLevelDef.xid) {
                const segment = allSegments[currentGlobalIndex];
                logCollector(`[BUILD-MATCH] Segment ${segment.id}(L${segment.lineNumber}) matched top-level schema segment ${topLevelDef.xid} ('${topLevelDef.name}') (Instance ${foundCount + 1}/${maxUse})`, 'info');

                result.push(segment);
                segmentConsumedFlags[currentGlobalIndex] = true;
                currentGlobalIndex++;
                foundCount++;
            }

            if (foundCount === 0) {
                logCollector(`[BUILD] -> Top-level segment ${topLevelDef.xid} not found or already consumed starting at index ${currentGlobalIndex}.`, 'debug');
                if (topLevelDef.usage === 'R') {
                    logCollector(`[BUILD] -> WARNING: Required top-level segment ${topLevelDef.xid} was not found.`, 'warn');
                }
            } else {
                logCollector(`[BUILD] -> Finished processing top-level segment ${topLevelDef.xid}. Found ${foundCount}. Advanced globalIndex to ${currentGlobalIndex}.`, 'debug');
            }
        }
    } // End FOR loop over schema.structure

    if (currentGlobalIndex < allSegments.length) {
        logCollector(`[BUILD] Finished schema structure. Checking for remaining unconsumed segments from index ${currentGlobalIndex}.`, 'debug');
        const remainingSegments: EdiSegment[] = [];
        for (let i = currentGlobalIndex; i < allSegments.length; i++) {
            if (!segmentConsumedFlags[i]) {
                remainingSegments.push(allSegments[i]);
            }
        }

        if (remainingSegments.length > 0) {
            remainingSegments.forEach(seg => {
                logCollector(`[BUILD-ORPHAN] Segment ${seg.id}(L${seg.lineNumber}) added as unhandled (remaining at end)`, 'warn');
                result.push(seg);
            });
        } else {
            logCollector("[BUILD] No remaining unconsumed segments found at the end.", 'debug');
        }
    } else {
        logCollector("[BUILD] All segments processed or accounted for by schema structure.", 'debug');
    }

    const totalSegmentsInResult = result.reduce((count, node) => {
        if (node.type === 'segment') return count + 1;
        if (node.type === 'loop') {
            const countChildren = (loopNode: HierarchicalEdiLoop): number => {
                return loopNode.children.reduce((subCount, child) => {
                    if (child.type === 'segment') return subCount + 1;
                    if (child.type === 'loop') return subCount + countChildren(child);
                    return subCount;
                }, 0);
            };
            return count + countChildren(node);
        }
        return count;
    }, 0);

    logCollector(`[BUILD] Hierarchical structure build finished. Input segments: ${allSegments.length}, Segments in final structure (incl. orphans): ${totalSegmentsInResult}.`, 'info');
    if (totalSegmentsInResult !== allSegments.length) {
        logCollector(`[BUILD] -> INFO: Segment count mismatch (${totalSegmentsInResult} vs ${allSegments.length}) may indicate segments discarded during initial parsing or complex orphan handling.`, 'info');
    }

    return result;
};