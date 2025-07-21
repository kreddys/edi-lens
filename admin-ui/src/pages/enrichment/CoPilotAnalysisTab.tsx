// FILE: admin-ui/src/pages/enrichment/CoPilotAnalysisTab.tsx
import React, { Dispatch, SetStateAction, useState, useEffect } from 'react';
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
// --- FIX: Removed unused hooks ---
import { useGetIdentity } from '@refinedev/core'; 
import { useQuery } from '@tanstack/react-query';
import { AnalysisResults } from './AnalysisResults';
import { axiosInstance } from '../../providers';
import { AxiosError, AxiosResponse } from 'axios';

const { Text } = Typography;

type TAnalysisResult = {
    job_id: string;
    status: "running" | "complete" | "failed";
    result?: any;
    error?: string;
};

// Define the props the component will receive from its parent
interface CoPilotAnalysisTabProps {
    jobId: string | null;
    setJobId: Dispatch<SetStateAction<string | null>>;
    isLoadingJob: boolean;
    setIsLoadingJob: Dispatch<SetStateAction<boolean>>;
    analysisResult: TAnalysisResult | null;
    setAnalysisResult: Dispatch<SetStateAction<TAnalysisResult | null>>;
}

export const CoPilotAnalysisTab: React.FC<CoPilotAnalysisTabProps> = ({
    jobId,
    setJobId,
    isLoadingJob,
    setIsLoadingJob,
    analysisResult,
    setAnalysisResult,
}) => {
    const [form] = Form.useForm();
    const { data: identity } = useGetIdentity<any>();
    
    // State for schemas is local to this component
    const [schemaFiles, setSchemaFiles] = useState<string[]>([]);
    const [isLoadingSchemas, setIsLoadingSchemas] = useState<boolean>(true);

    useEffect(() => {
        axiosInstance.get<string[]>('/schemas')
            .then((response: AxiosResponse<string[]>) => {
                setSchemaFiles(response.data);
            })
            .catch((error: AxiosError) => {
                notification.error({ message: 'Failed to load schemas', description: error.message });
            })
            .finally(() => {
                setIsLoadingSchemas(false);
            });
    }, []);

    const { isFetching: isPolling } = useQuery<TAnalysisResult, AxiosError>({
        queryKey: ['enrichmentStatus', jobId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/enrichment/status/${jobId}`);
            return response.data;
        },
        enabled: !!jobId && isLoadingJob,
        refetchInterval: 3000,
        onSuccess: (data) => {
            setAnalysisResult(data);
            if (data.status === 'complete' || data.status === 'failed') {
                setIsLoadingJob(false);
                notification.info({ message: 'Analysis Complete', description: `Job ${jobId} finished with status: ${data.status}` });
            }
        },
        onError: (error) => {
            setIsLoadingJob(false);
            notification.error({ message: 'Polling Error', description: `Could not fetch job status: ${error.message}` });
        }
    });

    const handleAnalyze = async (values: any) => {
        if (!identity?.realm_access?.roles?.includes("superuser")) {
            notification.error({ message: "Permission Denied" });
            return;
        }

        setIsLoadingJob(true);
        setAnalysisResult(null);

        try {
            const response = await axiosInstance.post('/enrichment/analyze', values);
            const newJobId = response.data.job_id;
            setJobId(newJobId);
            notification.success({ message: `Analysis Started`, description: `Job ID: ${newJobId}.` });
        } catch (error: any) {
            notification.error({ message: `Error starting analysis: ${error.message}` });
            setIsLoadingJob(false);
        }
    };

    return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Card bordered={false}>
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
                    <Form.Item name="schema_name" label="Schema" rules={[{ required: true }]}>
                        <Select
                            loading={isLoadingSchemas}
                            // --- FIX: Explicitly type fileName ---
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
                 <Card style={{ textAlign: 'center', border: 'none' }} bodyStyle={{paddingTop: 48, paddingBottom: 48}}>
                    <Spin size="large" />
                    <Typography.Title level={5} style={{ marginTop: 16 }}>Analysis in Progress...</Typography.Title>
                    <Text type="secondary">Job ID: {jobId}</Text>
                 </Card>
            )}

            {analysisResult && !isLoadingJob && (
                <AnalysisResults data={analysisResult} />
            )}
        </Space>
    );
};