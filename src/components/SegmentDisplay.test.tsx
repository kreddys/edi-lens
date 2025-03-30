import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest'; // <<< Added vi
import SegmentDisplay from './SegmentDisplay';
import { EdiSegment } from '../ediParser/ediTypes';
import { ProcessedTransactionSchema } from '../ediSchema/schemaTypes';

// <<< Added vi >>>
vi.mock('./ElementDisplay', () => ({
    default: ({ element, definition, segmentId, elementIndex }: any) => (
        <div data-testid={`element-${segmentId}${String(elementIndex + 1).padStart(2, '0')}`}>
            {element.value} - {definition?.name || 'No Def'}
        </div>
    ),
}));

// ... rest of the test file remains the same ...
const mockSegmentNM1: EdiSegment = {
    type: 'segment',
    id: 'NM1',
    lineNumber: 10,
    rawSegmentString: 'NM1*IL*1*SMITH*JOHN****MI*123456789',
    elements: [{ value: 'IL' }, { value: '1' }, { value: 'SMITH' }, { value: 'JOHN' }, { value: '' }, { value: '' }, { value: '' }, { value: 'MI' }, { value: '123456789' }]
};

const mockSchema: ProcessedTransactionSchema = {
    transactionName: 'Test',
    segmentDefinitions: {
        NM1: {
            name: 'Individual Name', usage: 'R', pos: '010', max_use: 1,
            elements: [
                { xid: 'NM101', data_ele: '98', name: 'Entity ID Code', usage: 'R', seq: '01' },
                { xid: 'NM102', data_ele: '1065', name: 'Entity Type', usage: 'R', seq: '02' },
                { xid: 'NM103', data_ele: '1035', name: 'Last Name', usage: 'R', seq: '03' },
                // ... other element defs
            ]
        }
    },
    structure: [] // Not needed for this component test
};

describe('SegmentDisplay', () => {
    it('renders segment header correctly and collapses by default', () => {
        render(<SegmentDisplay segment={mockSegmentNM1} schema={mockSchema} level={1} />);

        expect(screen.getByText('10')).toBeInTheDocument(); // Line number
        expect(screen.getByText('NM1')).toBeInTheDocument(); // ID
        expect(screen.getByText('- Individual Name')).toBeInTheDocument(); // Name from schema
        // Check that elements are NOT visible initially
        expect(screen.queryByTestId('element-NM101')).not.toBeInTheDocument();
        expect(screen.queryByText('IL - Entity ID Code')).not.toBeInTheDocument();
    });

    it('expands and shows elements on click', async () => {
        const user = userEvent.setup();
        render(<SegmentDisplay segment={mockSegmentNM1} schema={mockSchema} level={1} />);

        const header = screen.getByText('NM1');
        await user.click(header);

        // Check that elements ARE visible after click
        expect(await screen.findByTestId('element-NM101')).toBeInTheDocument();
        expect(await screen.findByText('IL - Entity ID Code')).toBeInTheDocument(); // Check mocked ElementDisplay output
    });

    it('collapses elements on second click', async () => {
        const user = userEvent.setup();
        render(<SegmentDisplay segment={mockSegmentNM1} schema={mockSchema} level={1} />);

        const header = screen.getByText('NM1');
        // First click (expand)
        await user.click(header);
        expect(await screen.findByTestId('element-NM101')).toBeInTheDocument();

        // Second click (collapse)
        await user.click(header);
        expect(screen.queryByTestId('element-NM101')).not.toBeInTheDocument();
    });
});