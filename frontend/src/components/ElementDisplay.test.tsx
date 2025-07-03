import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ElementDisplay from './ElementDisplay';
import { SchemaElementAttribute, SchemaCompositeAttribute } from '../ediSchema/schemaTypes';
import { EdiElement } from '../ediParser/ediTypes';

describe('ElementDisplay', () => {
    const mockElement: EdiElement = { value: 'ELEMENT_VALUE' };
    const mockElementEmpty: EdiElement = { value: '' };

    const mockDefinitionSimple: SchemaElementAttribute = {
        xid: 'NM103', data_ele: '1035', name: 'Last Name', usage: 'R', seq: '03',
        valid_codes: { code: ['SMITH', 'JONES'] }
    };

    const mockDefinitionComposite: SchemaCompositeAttribute = {
        xid: 'CLM05', data_ele: 'C023', name: 'Service Location', usage: 'S', seq: '05',
        elements: [
            { xid: 'CLM05-01', data_ele: '1331', name: 'Place Code', usage: 'R', seq: '01' },
            { xid: 'CLM05-02', data_ele: '1332', name: 'Facility Qualifier', usage: 'R', seq: '02' },
        ]
    };

    it('renders simple element correctly', () => {
        render(<ElementDisplay element={mockElement} definition={mockDefinitionSimple} segmentId="NM1" elementIndex={2} />);

        expect(screen.getByText('R')).toBeInTheDocument(); // Usage
        expect(screen.getByText('R')).toHaveClass('text-brand-usage-r');
        expect(screen.getByText('Last Name')).toBeInTheDocument(); // Name
        expect(screen.getByText('(DE 1035)')).toBeInTheDocument(); // Description
        expect(screen.getByText('NM103')).toBeInTheDocument(); // ID
        expect(screen.getByText('ELEMENT_VALUE')).toBeInTheDocument(); // Value
        expect(screen.getByText('Codes:')).toBeInTheDocument();
        expect(screen.getByText('SMITH | JONES')).toBeInTheDocument();
    });

    it('renders empty element value', () => {
        render(<ElementDisplay element={mockElementEmpty} definition={mockDefinitionSimple} segmentId="NM1" elementIndex={2} />);
        expect(screen.getByText('[Empty]')).toBeInTheDocument();
        expect(screen.getByText('[Empty]')).toHaveClass('italic');
    });

    it('renders composite element correctly', () => {
        render(<ElementDisplay element={mockElement} definition={mockDefinitionComposite} segmentId="CLM" elementIndex={4} />);

        expect(screen.getByText('S')).toBeInTheDocument(); // Usage
        expect(screen.getByText('Service Location')).toBeInTheDocument(); // Name
        expect(screen.getByText('(DE C023) (Composite)')).toBeInTheDocument(); // Description
        expect(screen.getByText('CLM05')).toBeInTheDocument(); // ID
        expect(screen.getByText('ELEMENT_VALUE')).toBeInTheDocument(); // Raw Value
        expect(screen.getByText('Composite Definition:')).toBeInTheDocument();
        expect(screen.getByText(/01: Place Code \(1331\)/)).toBeInTheDocument();
        expect(screen.getByText(/02: Facility Qualifier \(1332\)/)).toBeInTheDocument();
        expect(screen.getByText(/Basic parser displays raw composite value above/)).toBeInTheDocument();
    });

    it('renders gracefully without definition', () => {
        render(<ElementDisplay element={mockElement} definition={undefined} segmentId="UNK" elementIndex={0} />);
        expect(screen.getByText('?')).toBeInTheDocument(); // Usage
        expect(screen.getByText('Element 01')).toBeInTheDocument(); // Default Name
        expect(screen.queryByText('(DE')).not.toBeInTheDocument(); // No Description
        expect(screen.getByText('UNK01')).toBeInTheDocument(); // ID
        expect(screen.getByText('ELEMENT_VALUE')).toBeInTheDocument(); // Value
        expect(screen.queryByText('Codes:')).not.toBeInTheDocument();
        expect(screen.queryByText('Composite Definition:')).not.toBeInTheDocument();
    });

    // Add tests for other usages (S, N), missing valid codes, etc.
});