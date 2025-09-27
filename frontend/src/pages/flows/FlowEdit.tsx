import React from "react";
import { Edit, useForm } from "@refinedev/antd";
import { Form, Input } from "antd";

const { TextArea } = Input;

export const FlowEdit: React.FC = () => {
    const { formProps, saveButtonProps } = useForm();

    return (
        <Edit saveButtonProps={saveButtonProps}>
            <Form {...formProps} layout="vertical">
                <Form.Item
                    label="Name"
                    name="name"
                    rules={[
                        {
                            required: true,
                        },
                    ]}
                >
                    <Input />
                </Form.Item>
                <Form.Item
                    label="Description"
                    name="description"
                >
                    <TextArea rows={4} />
                </Form.Item>
            </Form>
        </Edit>
    );
};