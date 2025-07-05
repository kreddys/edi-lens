import {
    Create,
    Datagrid,
    Edit,
    List,
    SimpleForm,
    TextField,
    TextInput,
    required,
    ArrayInput,
    SimpleFormIterator,
    NumberInput,
    SelectInput,
} from 'react-admin';

export const TradingPartnerList = () => (
    <List>
        <Datagrid rowClick="edit" bulkActionButtons={false}>
            <TextField source="id" />
            <TextField source="name" />
            <TextField source="description" />
            <TextField source="tenant_id" label="Tenant" />
        </Datagrid>
    </List>
);

// Note: React-Admin can't easily edit deeply nested structures out of the box.
// This form only allows editing the top-level partner details.
export const TradingPartnerEdit = () => (
    <Edit>
        <SimpleForm>
            <TextInput source="id" disabled />
            <TextInput source="tenant_id" disabled />
            <TextInput source="name" validate={required()} />
            <TextInput source="description" multiline rows={3} />
        </SimpleForm>
    </Edit>
);

// This form allows creating a partner with profiles and criteria
export const TradingPartnerCreate = () => (
    <Create>
        <SimpleForm>
            <TextInput source="name" validate={required()} />
            <TextInput source="description" multiline rows={3} />
            <ArrayInput source="profiles">
                <SimpleFormIterator>
                    <TextInput source="name" validate={required()} label="Profile Name" />
                    <TextInput source="implementation_guide" validate={required()} label="Implementation Guide" />
                    <NumberInput source="priority" defaultValue={10} />
                    <ArrayInput source="criteria">
                        <SimpleFormIterator>
                            <SelectInput source="field_source" label="Field Source" validate={required()} choices={[
                                { id: 'ISA', name: 'ISA' },
                                { id: 'GS', name: 'GS' },
                                { id: 'FILENAME', name: 'Filename' },
                            ]} />
                            <TextInput source="field_identifier" label="Field ID (e.g., 06)" validate={required()} />
                             <SelectInput source="operator" validate={required()} choices={[
                                { id: 'EQUALS', name: 'Equals' },
                                { id: 'STARTS_WITH', name: 'Starts With' },
                                { id: 'CONTAINS', name: 'Contains' },
                            ]} />
                            <TextInput source="value" label="Value" validate={required()} />
                        </SimpleFormIterator>
                    </ArrayInput>
                </SimpleFormIterator>
            </ArrayInput>
        </SimpleForm>
    </Create>
);