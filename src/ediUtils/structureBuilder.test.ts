import { describe, it, expect, vi, beforeEach } from 'vitest';
import { buildHierarchicalData, HierarchicalEdiLoop } from './structureBuilder';
import { ParsedEdiData, EdiSegment } from '../ediParser/ediTypes';
import { ProcessedTransactionSchema } from '../ediSchema/schemaTypes';
import { AppLogger } from '../logger';

const mockLogger: AppLogger = vi.fn();

beforeEach(() => {
    vi.clearAllMocks();
})

// --- Mock Data ---
const mockSegment = (id: string, line: number, elements: string[] = []): EdiSegment => ({
    type: 'segment',
    id,
    lineNumber: line,
    rawSegmentString: `${id}*${elements.join('*')}`,
    elements: elements.map(value => ({ value })),
});

const mockParsedData: ParsedEdiData = {
    rawEdiString: '...',
    delimiters: { element: '*', segment: '~', component: ':' },
    segments: [
        mockSegment('ISA', 1), mockSegment('GS', 2), mockSegment('ST', 3, ['837']),
        mockSegment('BHT', 4), mockSegment('HL', 5, ['1', '', '20', '1']),
        mockSegment('NM1', 6, ['85']), mockSegment('HL', 7, ['2', '1', '22', '0']),
        mockSegment('SBR', 8, ['P']), mockSegment('NM1', 9, ['IL']),
        mockSegment('CLM', 10, ['PATCTRL01', '100.00']), mockSegment('LX', 11, ['1']),
        mockSegment('SV1', 12), mockSegment('LX', 13, ['2']), mockSegment('SV1', 14),
        mockSegment('HL', 15, ['3', '1', '22', '0']), mockSegment('SBR', 16, ['S']),
        mockSegment('NM1', 17, ['IL']), mockSegment('CLM', 18, ['PATCTRL02', '250.00']),
        mockSegment('LX', 19, ['1']), mockSegment('SV1', 20),
        mockSegment('SE', 21, ['XX', '1239']), mockSegment('GE', 22, ['1', '101']),
        mockSegment('IEA', 23, ['1', '000000101']),
    ]
};

const mockSchema: ProcessedTransactionSchema = {
    transactionName: 'Test 837',
    segmentDefinitions: {
        ISA: { name: 'ISA', usage: 'R', pos: '010', max_use: 1, elements: [] },
        GS: { name: 'GS', usage: 'R', pos: '020', max_use: 1, elements: [] },
        ST: { name: 'ST', usage: 'R', pos: '030', max_use: 1, elements: [] },
        BHT: { name: 'BHT', usage: 'R', pos: '040', max_use: 1, elements: [] },
        HL: { name: 'HL', usage: 'R', pos: '000', max_use: 1, elements: [] },
        NM1: { name: 'NM1', usage: 'R', pos: '000', max_use: 1, elements: [] },
        SBR: { name: 'SBR', usage: 'R', pos: '000', max_use: 1, elements: [] },
        CLM: { name: 'CLM', usage: 'R', pos: '000', max_use: 1, elements: [] },
        LX: { name: 'LX', usage: 'R', pos: '000', max_use: 1, elements: [] },
        SV1: { name: 'SV1', usage: 'R', pos: '000', max_use: 1, elements: [] },
        SE: { name: 'SE', usage: 'R', pos: '970', max_use: 1, elements: [] },
        GE: { name: 'GE', usage: 'R', pos: '980', max_use: 1, elements: [] },
        IEA: { name: 'IEA', usage: 'R', pos: '990', max_use: 1, elements: [] },
    },
    structure: [
        { type: 'segment', xid: 'ISA', pos: '010', usage: 'R', max_use: 1, name: 'ISA' },
        { type: 'segment', xid: 'GS', pos: '020', usage: 'R', max_use: 1, name: 'GS' },
        { type: 'segment', xid: 'ST', pos: '030', usage: 'R', max_use: 1, name: 'ST' },
        { type: 'segment', xid: 'BHT', pos: '040', usage: 'R', max_use: 1, name: 'BHT' },
        {
            type: 'loop', xid: '2000A', name: 'Billing Provider Loop', pos: '100', usage: 'R', repeat: 1, children: [
                { type: 'segment', xid: 'HL', pos: '010', usage: 'R', max_use: 1, name: 'Billing HL' },
                { type: 'segment', xid: 'NM1', pos: '020', usage: 'R', max_use: 1, name: 'Billing Name' },
                {
                    type: 'loop', xid: '2000B', name: 'Subscriber Loop', pos: '200', usage: 'R', repeat: '>1', children: [
                        { type: 'segment', xid: 'HL', pos: '010', usage: 'R', max_use: 1, name: 'Subscriber HL' },
                        { type: 'segment', xid: 'SBR', pos: '020', usage: 'R', max_use: 1, name: 'Subscriber Info' },
                        { type: 'segment', xid: 'NM1', pos: '030', usage: 'R', max_use: 1, name: 'Subscriber Name' },
                        {
                            type: 'loop', xid: '2300', name: 'Claim Loop', pos: '300', usage: 'S', repeat: '>1', children: [
                                { type: 'segment', xid: 'CLM', pos: '010', usage: 'R', max_use: 1, name: 'Claim Info' },
                                {
                                    type: 'loop', xid: '2400', name: 'Service Line Loop', pos: '020', usage: 'S', repeat: '>1', children: [
                                        { type: 'segment', xid: 'LX', pos: '010', usage: 'R', max_use: 1, name: 'Service Line #' },
                                        { type: 'segment', xid: 'SV1', pos: '020', usage: 'R', max_use: 1, name: 'Service Line Info' },
                                    ]
                                },
                            ]
                        },
                    ]
                },
            ]
        },
        { type: 'segment', xid: 'SE', pos: '970', usage: 'R', max_use: 1, name: 'SE' },
        { type: 'segment', xid: 'GE', pos: '980', usage: 'R', max_use: 1, name: 'GE' },
        { type: 'segment', xid: 'IEA', pos: '990', usage: 'R', max_use: 1, name: 'IEA' },
    ]
};
// --- End Mock Data ---

describe('structureBuilder', () => {
    it('should return empty array if parsedData is null', () => {
        const result = buildHierarchicalData(null, mockSchema, mockLogger);
        expect(result).toEqual([]);
    });

    it('should return flat list if schema is null or has no structure', () => {
        const resultNullSchema = buildHierarchicalData(mockParsedData, null, mockLogger);
        expect(resultNullSchema).toEqual(mockParsedData.segments);

        const resultEmptyStructure = buildHierarchicalData(mockParsedData, { ...mockSchema, structure: [] }, mockLogger);
        expect(resultEmptyStructure).toEqual(mockParsedData.segments);
    });

    it('should build hierarchical structure based on schema', () => {
        const result = buildHierarchicalData(mockParsedData, mockSchema, mockLogger);

        // Basic structure checks
        expect(result).toHaveLength(8);
        expect(result[0].type).toBe('segment');
        expect((result[0] as EdiSegment).id).toBe('ISA');
        expect(result[1].type).toBe('segment');
        expect((result[1] as EdiSegment).id).toBe('GS');
        expect(result[2].type).toBe('segment');
        expect((result[2] as EdiSegment).id).toBe('ST');
        expect(result[3].type).toBe('segment');
        expect((result[3] as EdiSegment).id).toBe('BHT');
        expect(result[4].type).toBe('loop');
        expect(result[5].type).toBe('segment');
        expect((result[5] as EdiSegment).id).toBe('SE');
        expect(result[6].type).toBe('segment');
        expect((result[6] as EdiSegment).id).toBe('GE');
        expect(result[7].type).toBe('segment');
        expect((result[7] as EdiSegment).id).toBe('IEA');


        // Check 2000A
        const loop2000A = result[4] as HierarchicalEdiLoop;
        expect(loop2000A.loopId).toBe('2000A_1');
        expect(loop2000A.children).toHaveLength(4);
        expect(loop2000A.children[0].type).toBe('segment');
        expect((loop2000A.children[0] as EdiSegment).id).toBe('HL');
        expect(loop2000A.children[1].type).toBe('segment');
        expect((loop2000A.children[1] as EdiSegment).id).toBe('NM1');
        expect(loop2000A.children[2].type).toBe('loop');
        expect((loop2000A.children[2] as HierarchicalEdiLoop).loopId).toBe('2000B_1');
        expect(loop2000A.children[3].type).toBe('loop');
        expect((loop2000A.children[3] as HierarchicalEdiLoop).loopId).toBe('2000B_2');


        // Check first 2000B instance
        const loop2000B_1 = loop2000A.children[2] as HierarchicalEdiLoop;
        expect(loop2000B_1.children).toHaveLength(4);
        expect(loop2000B_1.children[0].type).toBe('segment');
        expect((loop2000B_1.children[0] as EdiSegment).id).toBe('HL');
        expect(loop2000B_1.children[1].type).toBe('segment');
        expect((loop2000B_1.children[1] as EdiSegment).id).toBe('SBR');
        expect(loop2000B_1.children[2].type).toBe('segment');
        expect((loop2000B_1.children[2] as EdiSegment).id).toBe('NM1');
        expect(loop2000B_1.children[3].type).toBe('loop');
        expect((loop2000B_1.children[3] as HierarchicalEdiLoop).loopId).toBe('2300_1');

        // Check first 2300 instance (Claim 1)
        const loop2300_1 = loop2000B_1.children[3] as HierarchicalEdiLoop;
        expect(loop2300_1.children).toHaveLength(3);
        expect(loop2300_1.children[0].type).toBe('segment');
        expect((loop2300_1.children[0] as EdiSegment).id).toBe('CLM');
        expect(loop2300_1.children[1].type).toBe('loop');
        expect((loop2300_1.children[1] as HierarchicalEdiLoop).loopId).toBe('2400_1');
        expect(loop2300_1.children[2].type).toBe('loop');
        expect((loop2300_1.children[2] as HierarchicalEdiLoop).loopId).toBe('2400_2');

        // Check first 2400 instance (Service Line 1.1)
        const loop2400_1_1 = loop2300_1.children[1] as HierarchicalEdiLoop;
        expect(loop2400_1_1.children).toHaveLength(2);
        expect(loop2400_1_1.children[0].type).toBe('segment');
        expect((loop2400_1_1.children[0] as EdiSegment).id).toBe('LX');
        expect(loop2400_1_1.children[1].type).toBe('segment');
        expect((loop2400_1_1.children[1] as EdiSegment).id).toBe('SV1');

        // Check second 2400 instance (Service Line 1.2)
        const loop2400_1_2 = loop2300_1.children[2] as HierarchicalEdiLoop;
        expect(loop2400_1_2.children).toHaveLength(2);
        expect(loop2400_1_2.children[0].type).toBe('segment');
        expect((loop2400_1_2.children[0] as EdiSegment).id).toBe('LX');
        expect(loop2400_1_2.children[1].type).toBe('segment');
        expect((loop2400_1_2.children[1] as EdiSegment).id).toBe('SV1');


        // Check second 2000B instance
        const loop2000B_2 = loop2000A.children[3] as HierarchicalEdiLoop;
        expect(loop2000B_2.children).toHaveLength(4);
        expect(loop2000B_2.children[0].type).toBe('segment');
        expect((loop2000B_2.children[0] as EdiSegment).id).toBe('HL');
        expect((loop2000B_2.children[0] as EdiSegment).lineNumber).toBe(15);
        expect(loop2000B_2.children[1].type).toBe('segment');
        expect((loop2000B_2.children[1] as EdiSegment).id).toBe('SBR');
        expect(loop2000B_2.children[2].type).toBe('segment');
        expect((loop2000B_2.children[2] as EdiSegment).id).toBe('NM1');
        expect(loop2000B_2.children[3].type).toBe('loop');
        expect((loop2000B_2.children[3] as HierarchicalEdiLoop).loopId).toBe('2300_1');

        // Check second 2300 instance (Claim 2)
        const loop2300_2 = loop2000B_2.children[3] as HierarchicalEdiLoop;
        expect(loop2300_2.children).toHaveLength(2);
        expect(loop2300_2.children[0].type).toBe('segment');
        expect((loop2300_2.children[0] as EdiSegment).id).toBe('CLM');
        expect(loop2300_2.children[1].type).toBe('loop');
        expect((loop2300_2.children[1] as HierarchicalEdiLoop).loopId).toBe('2400_1');
    });

    it('should handle segments not defined in the structure (place them where found)', () => {
        const dataWithExtra = {
            ...mockParsedData,
            segments: [
                mockParsedData.segments[0], mockParsedData.segments[1], mockParsedData.segments[2],
                mockSegment('XYZ', 3.5), mockParsedData.segments[3], mockSegment('ABC', 4.5),
                ...mockParsedData.segments.slice(4)
            ]
        };
        const result = buildHierarchicalData(dataWithExtra, mockSchema, mockLogger);
        expect(result).toHaveLength(10);
        expect(result[3].type).toBe('segment');
        expect((result[3] as EdiSegment).id).toBe('XYZ');
        expect(result[4].type).toBe('segment');
        expect((result[4] as EdiSegment).id).toBe('BHT');
        expect(result[5].type).toBe('segment');
        expect((result[5] as EdiSegment).id).toBe('ABC');
        expect(result[6].type).toBe('loop');
    });

});