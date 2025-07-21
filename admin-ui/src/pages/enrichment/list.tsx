// FILE: admin-ui/src/pages/enrichment/list.tsx
import React, { useState, useEffect } from 'react';
import {
    Card,
    Typography,
    Form,
    Input,
    Button,
    Space,
    Spin,
    notification,
    Select
} from 'antd';
import { useGetIdentity } from '@refinedev/core';
import { useQuery } from '@tanstack/react-query';
import { AnalysisResults } from './AnalysisResults';
import { axiosInstance } from '../../providers'; // Use the barrel file import
import { AxiosResponse, AxiosError } from 'axios'; // Import types for axios

const { Title, Text } = Typography;

type TAnalysisResult = {
    job_id: string;
    status: "running" | "complete" | "failed";
    result?: any;
    error?: string;
};

export const EnrichmentPage: React.FC = () => {
    const [form] = Form.useForm();
    const { data: identity } = useGetIdentity<any>();
    
    const [schemaFiles, setSchemaFiles] = useState<string[]>([]);
    const [isLoadingSchemas, setIsLoadingSchemas] = useState<boolean>(true);
    
    const [jobId, setJobId] = useState<string | null>(null);
    const [isLoadingJob, setIsLoadingJob] = useState<boolean>(false);
    const [analysisResult, setAnalysisResult] = useState<TAnalysisResult | null>(null);

    useEffect(() => {
        axiosInstance.get<string[]>('/schemas') // Add generic type to get()
            .then((response: AxiosResponse<string[]>) => { // Type the response
                setSchemaFiles(response.data);
            })
            .catch((error: AxiosError) => { // Type the error
                notification.error({ message: 'Failed to load schemas', description: error.message });
            })
            .finally(() => {
                setIsLoadingSchemas(false);
            });
    }, []);

    // isFetching from useQuery is our polling indicator
    const { isFetching: isPolling } = useQuery<TAnalysisResult, AxiosError>({ // Type the error
        queryKey: ['enrichmentStatus', jobId],
        queryFn: async () => {
            console.log(`[DEBUG] Polling for jobId: ${jobId}`);
            const response = await axiosInstance.get(`/enrichment/status/${jobId}`);
            console.log("[DEBUG] Polling response received:", response.data);
            return response.data;
        },
        enabled: !!jobId && isLoadingJob,
        refetchInterval: 3000,
        onSuccess: (data) => {
            setAnalysisResult(data);
            if (data.status === 'complete' || data.status === 'failed') {
                setIsLoadingJob(false);
                notification.info({
                    message: 'Analysis Complete',
                    description: `Job ${jobId} finished with status: ${data.status}`,
                });
            }
        },
        onError: (error) => {
            setIsLoadingJob(false);
            notification.error({
                message: 'Polling Error',
                description: `Could not fetch job status: ${error.message}`,
            });
        }
    });

    const handleAnalyze = async (values: any) => {
        if (!identity?.realm_access?.roles?.includes("superuser")) {
            notification.error({ message: "Permission Denied", description: "You must be a superuser to run schema analysis." });
            return;
        }

        console.log("[DEBUG] handleAnalyze called with values:", values);
        setIsLoadingJob(true);
        setAnalysisResult(null);

        try {
            const response = await axiosInstance.post('/enrichment/analyze', values);
            const newJobId = response.data.job_id;
            console.log("[DEBUG] Analysis job started successfully. Job ID:", newJobId);
            setJobId(newJobId);
            notification.success({ message: `Analysis Started`, description: `Job ID: ${newJobId}.` });
        } catch (error: any) {
            console.error("[DEBUG] Error starting analysis job:", error);
            notification.error({ message: `Error starting analysis: ${error.message}` });
            setIsLoadingJob(false);
        }
    };

    return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Card>
                <Title level={4}>Co-Pilot Analysis</Title>
                <Text type="secondary">
                    Select a schema and provide a segment to have the AI Co-Pilot analyze it against its knowledge base and propose changes. (Superuser only)
                </Text>
                <Form
                    form={form}
                    layout="vertical"
                    onFinish={handleAnalyze}
                    style={{ marginTop: 24 }}
                    initialValues={{ schema_name: "837.5010.X222.A1.json" }}
                >
                    <Form.Item
                        name="schema_name"
                        label="Schema"
                        rules={[{ required: true }]}
                    >
                        <Select
                            loading={isLoadingSchemas}
                            options={schemaFiles.map((fileName: string) => ({ label: fileName, value: fileName }))}
                            placeholder="Select a schema file"
                        />
                    </Form.Item>
                    <Form.Item name="segment_id" label="Segment ID" rules={[{ required: true }]}>
                        <Input placeholder="e.g., CLM" />
                    </Form.Item>
                    <Form.Item name="context_id" label="Context ID" rules={[{ required: true }]}>
                        <Input placeholder="e.g., 2300.CLM" />
                    </Form.Item>
                    <Form.Item>
                        <Button type="primary" htmlType="submit" loading={isLoadingJob}>
                            {isLoadingJob ? 'Analyzing...' : 'Start Analysis'}
                        </Button>
                    </Form.Item>
                </Form>
            </Card>

            {(isLoadingJob || isPolling) && (
                 <Card style={{ textAlign: 'center' }}>
                    <Spin size="large" />
                    <Title level={5} style={{ marginTop: 16 }}>Analysis in Progress...</Title>
                    <Text type="secondary">Job ID: {jobId}</Text>
                 </Card>
            )}

            {analysisResult && !isLoadingJob && (
                <AnalysisResults data={analysisResult} />
            )}
        </Space>
    );
};