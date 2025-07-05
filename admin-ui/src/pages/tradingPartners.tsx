import { Create, List, useDataGrid, EditButton } from "@refinedev/mui";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import { useForm } from "@refinedev/react-hook-form";
import { Box, TextField } from "@mui/material";
import { IResourceComponentsProps } from "@refinedev/core";

export const TradingPartnerList: React.FC<IResourceComponentsProps> = () => {
    const { dataGridProps } = useDataGrid();
    
    // Add an actions column to the grid
    const columns: GridColDef[] = [
        { field: 'id', headerName: 'ID', width: 90 },
        { field: 'name', headerName: 'Name', flex: 1 },
        { field: 'description', headerName: 'Description', flex: 2 },
        { field: 'tenant_id', headerName: 'Tenant', flex: 1 },
        {
            field: "actions",
            headerName: "Actions",
            sortable: false,
            renderCell: function render({ row }) {
                return <EditButton hideText recordItemId={row.id} />;
            },
            align: "center",
            headerAlign: "center",
            minWidth: 80,
        },
    ];

    return (
        <List>
            <DataGrid {...dataGridProps} columns={columns} autoHeight />
        </List>
    );
};

export const TradingPartnerCreate: React.FC<IResourceComponentsProps> = () => {
    // --- THIS IS THE FIX ---
    // Add defaultValues to ensure `profiles` is always present in the form data,
    // even if it's an empty array. This prevents the 422 error.
    const { 
        saveButtonProps, 
        refineCore: { formLoading }, 
        register, 
        formState: { errors } 
    } = useForm({
        defaultValues: {
            name: "",
            description: "",
            profiles: [],
        },
    });

    return (
        <Create isLoading={formLoading} saveButtonProps={saveButtonProps}>
            <Box component="form" sx={{ display: "flex", flexDirection: "column" }} autoComplete="off">
                <TextField {...register("name", { required: "This field is required" })}
                    error={!!errors.name} helperText={errors.name?.message as string}
                    margin="normal" fullWidth label="Name" name="name" />
                <TextField {...register("description")}
                    margin="normal" fullWidth multiline rows={4}
                    label="Description" name="description" />
            </Box>
        </Create>
    );
};