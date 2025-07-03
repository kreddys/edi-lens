import { describe, it, expect, vi, beforeEach } from 'vitest';
import { parseEdi } from './ediParser';
import { AppLogger } from '../logger';

// Minimal mock logger for testing
const mockLogger: AppLogger = vi.fn();

beforeEach(() => {
    vi.clearAllMocks();
})

describe('ediParser', () => {
    it('should return error for empty string', () => {
        const result = parseEdi('', mockLogger);
        expect(result.error).toBe('EDI string is empty.');
        expect(result.data).toBeNull();
    });

    it('should parse a simple 837P string with default delimiters', () => {
        // Input uses default delimiters: *, ~, :
        const edi = `ISA*00*          *00*          *ZZ*123456789      *ZZ*11111          *170508*1141*^*00501*000000101*1*P*:~GS*HC*123456789*11111*20170617*1741*101*X*005010X222A1~ST*837*1239*005010X222A1~BHT*0019*00*010*20170617*1741*CH~NM1*41*2*SUBMITTER*****46*ABC123~SE*5*1239~GE*1*101~IEA*1*000000101~`;
        const result = parseEdi(edi, mockLogger);

        expect(result.error).toBeNull();
        expect(result.data).not.toBeNull();
        // Expect the standard default delimiters to be detected correctly
        expect(result.data?.delimiters).toEqual({ element: '*', segment: '~', component: ':' });
        expect(result.data?.segments).toHaveLength(8);

        // Basic checks on segments (remain the same)
        expect(result.data?.segments[0].id).toBe('ISA');
        expect(result.data?.segments[0].elements).toHaveLength(16);
        expect(result.data?.segments[0].elements[5].value).toBe('123456789      ');
        expect(result.data?.segments[0].lineNumber).toBe(1);

        expect(result.data?.segments[1].id).toBe('GS');
        expect(result.data?.segments[1].elements).toHaveLength(8);
        expect(result.data?.segments[1].elements[0].value).toBe('HC'); // Check first element of GS

        expect(result.data?.segments[2].id).toBe('ST');
        expect(result.data?.segments[2].elements).toHaveLength(3);
        expect(result.data?.segments[2].elements[0].value).toBe('837');

        expect(result.data?.segments[3].id).toBe('BHT');
        expect(result.data?.segments[3].elements[0].value).toBe('0019');

        expect(result.data?.segments[4].id).toBe('NM1');
        expect(result.data?.segments[4].elements[0].value).toBe('41');

        expect(result.data?.segments[5].id).toBe('SE');
        expect(result.data?.segments[5].elements[0].value).toBe('5');

        expect(result.data?.segments[6].id).toBe('GE');
        expect(result.data?.segments[6].elements[0].value).toBe('1');

        expect(result.data?.segments[7].id).toBe('IEA');
        expect(result.data?.segments[7].elements[0].value).toBe('1');
    });

    it('should detect non-default delimiters from ISA', () => {
        // FIX: Corrected test data to use '!' and '>' within subsequent segments
        const edi = `ISA!00!          !00!          !ZZ!SENDERID       !ZZ!RECEIVERID     !240101!1200!^!00501!000000001!0!P!>#GS!HC!SENDER!RECEIVER!20240101!1200!1!X!005010X222A1#ST!837!0001#SE!2!0001#GE!1!1#IEA!1!000000001#`;
        const result = parseEdi(edi, mockLogger);

        expect(result.error).toBeNull();
        expect(result.data?.delimiters).toEqual({ element: '!', segment: '#', component: '>' });
        expect(result.data?.segments).toHaveLength(6);
        // Now check segment IDs and elements using the *correct* delimiters
        expect(result.data?.segments[1].id).toBe('GS');
        expect(result.data?.segments[1].elements).toHaveLength(8);
        expect(result.data?.segments[1].elements[0].value).toBe('HC');
        expect(result.data?.segments[2].id).toBe('ST');
        expect(result.data?.segments[2].elements).toHaveLength(2); // ST!837!0001 -> ID=ST, elements=['837', '0001']
        expect(result.data?.segments[2].elements[0].value).toBe('837');
    });

    it('should handle segments split by newline when segment delimiter is newline', () => {
        // Input uses newline as segment terminator
        const edi = `ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240101*1200*^*00501*000000001*0*P*:\nGS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1\nST*837*0001\nSE*3*0001\nGE*1*1\nIEA*1*000000001\n`;
        const result = parseEdi(edi, mockLogger);

        expect(result.error).toBeNull();
        expect(result.data?.delimiters).toEqual({ element: '*', segment: '\n', component: ':' });
        expect(result.data?.segments).toHaveLength(6);
        expect(result.data?.segments[0].id).toBe('ISA');
        expect(result.data?.segments[1].id).toBe('GS');
        expect(result.data?.segments[2].id).toBe('ST');
        expect(result.data?.segments[3].id).toBe('SE');
        expect(result.data?.segments[4].id).toBe('GE');
        expect(result.data?.segments[5].id).toBe('IEA');
    });

    it('should return error if no valid segments found', () => {
        const result = parseEdi('Just some random text~NotAnID*data~', mockLogger);
        // Expect error because neither "Just some random text" nor "NotAnID" are valid segment IDs
        expect(result.error).not.toBeNull();
        expect(result.error).toMatch(/No valid segments found/i);
        expect(result.data).toBeNull();
    });

    it('should parse ONLY ISA if only ISA is present (no terminator)', () => {
        // Input is a short ISA segment without the segment terminator
        const edi = `ISA*00*          *00*          *ZZ*123456789      *ZZ*11111         *170508*1141*^*00501*000000101*1*P*:`;
        const result = parseEdi(edi, mockLogger);
        expect(result.error).toBeNull(); // No fatal error expected now
        expect(result.data).not.toBeNull();
        expect(result.data?.segments).toHaveLength(1); // Only ISA
        expect(result.data?.segments[0].id).toBe('ISA');
        // FIX: Update assertion to match the actual warning logged for short ISA
        expect(mockLogger).toHaveBeenCalledWith(expect.stringContaining('too short'), 'warn');
    });
});