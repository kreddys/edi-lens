import React, { useState, useEffect } from 'react';
import { notification, Button, Typography } from 'antd';
import { DatabaseOutlined, RocketOutlined, InfoCircleOutlined, SettingOutlined } from '@ant-design/icons';
import { SplitPanel } from '../../components/SplitPanel';
import { FlowJsonEditor } from '../../components/FlowJsonEditor';
import { BucketSelector } from '../../components/BucketSelector';
import { FlowActions } from '../../components/FlowActions';
import { FlowStatusPanel } from '../../components/FlowStatusPanel';
import { TemplateDropdown } from '../../components/TemplateDropdown';
import { MinimizableCard } from '../../components/MinimizableCard';
import { ParameterEditor } from '../../components/ParameterEditor';
import { flowAPI } from '../../providers/data';

const { Text } = Typography;

interface Bucket {
  bucket_id: string;
  bucket_name: string;
  description?: string;
}

interface ValidationError {
  component_type: string;
  component_name: string;
  error_type: string;
  message: string;
  details: Record<string, any>;
}

// Default template removed - JSON editor now starts empty for better UX

interface FlowDesignerProps {
  editingFlowId?: string | null;
  onBack?: () => void;
}

export const FlowDesigner: React.FC<FlowDesignerProps> = ({ 
  editingFlowId, 
  onBack 
}) => {
  // Flow Definition State
  const [flowJson, setFlowJson] = useState<string>('');
  const [flowName, setFlowName] = useState<string>('Simple File Processing');
  const [flowDescription, setFlowDescription] = useState<string>('A basic file processing flow that moves files from input to output directory');
  const [flowParameters, setFlowParameters] = useState<Record<string, string>>({});
  const [templateParameters, setTemplateParameters] = useState<Record<string, { description: string; default: string }>>({});
  
  // Bucket Management State
  const [buckets, setBuckets] = useState<Bucket[]>([]);
  const [bucketMode, setBucketMode] = useState<'select' | 'create'>('select');
  const [selectedBucketId, setSelectedBucketId] = useState<string>('');
  const [newBucketName, setNewBucketName] = useState<string>('');
  const [newBucketDescription, setNewBucketDescription] = useState<string>('');
  
  // Status State
  const [status, setStatus] = useState<'idle' | 'validating' | 'deploying' | 'success' | 'error'>('idle');
  const [deploymentProgress, setDeploymentProgress] = useState<number>(0);
  const [deploymentStage, setDeploymentStage] = useState<string>('');
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [errorDetails, setErrorDetails] = useState<any>(null);
  
  // Loading States
  const [bucketsLoading, setBucketsLoading] = useState<boolean>(false);
  const [deployLoading, setDeployLoading] = useState<boolean>(false);
  const [jsonError, setJsonError] = useState<string>('');

  // Load buckets on component mount
  useEffect(() => {
    loadBuckets();
  }, []);

  // Validate JSON whenever it changes
  useEffect(() => {
    validateJson(flowJson);
  }, [flowJson]);

  // Reset bucket mode based on available buckets
  useEffect(() => {
    if (buckets.length === 0 && bucketMode === 'select') {
      setBucketMode('create');
    }
  }, [buckets, bucketMode]);

  const loadBuckets = async () => {
    setBucketsLoading(true);
    try {
      const bucketsData = await flowAPI.listBuckets();
      const bucketArray = Array.isArray(bucketsData) ? bucketsData : [];
      setBuckets(bucketArray);
      
      // Auto-select first bucket if available
      if (bucketArray.length > 0 && !selectedBucketId) {
        setSelectedBucketId(bucketArray[0].bucket_id);
      }
    } catch (error) {
      console.error('Failed to load buckets:', error);
      notification.error({
        message: 'Failed to load buckets',
        description: 'Could not connect to the backend API. Make sure the backend is running.'
      });
    } finally {
      setBucketsLoading(false);
    }
  };

  const validateJson = (jsonString: string) => {
    if (!jsonString.trim()) {
      setJsonError('Flow definition is required');
      return false;
    }

    try {
      const parsed = JSON.parse(jsonString);
      
      // Basic validation
      if (!parsed.name) {
        setJsonError('Flow definition must include a "name" field');
        return false;
      }
      
      if (!parsed.processors || !Array.isArray(parsed.processors)) {
        setJsonError('Flow definition must include a "processors" array');
        return false;
      }

      setJsonError('');
      return true;
    } catch (error) {
      setJsonError('Invalid JSON format');
      return false;
    }
  };

  const handleJsonChange = (value: string) => {
    setFlowJson(value);
    setStatus('idle');
    setValidationErrors([]);
    setErrorDetails(null);
  };

  const handleTemplateSelect = (templateData: any) => {
    // Update the JSON editor with the template
    setFlowJson(JSON.stringify(templateData, null, 2));
    
    // Update flow name and description from template
    if (templateData.name) {
      setFlowName(templateData.name);
    }
    if (templateData.description) {
      setFlowDescription(templateData.description);
    }
    
    // Extract and set template parameters with default values
    if (templateData.parameters) {
      const templateParams: Record<string, string> = {};
      const templateParamDefs: Record<string, { description: string; default: string }> = {};
      
      Object.entries(templateData.parameters).forEach(([key, paramDef]: [string, any]) => {
        templateParams[key] = paramDef.default || '';
        templateParamDefs[key] = {
          description: paramDef.description || '',
          default: paramDef.default || ''
        };
      });
      
      setFlowParameters(templateParams);
      setTemplateParameters(templateParamDefs);
    } else {
      setFlowParameters({});
      setTemplateParameters({});
    }
    
    // Reset status
    setStatus('idle');
    setValidationErrors([]);
    setErrorDetails(null);
    
    notification.success({
      message: 'Template Loaded',
      description: `Template "${templateData.name}" has been loaded into the editor`
    });
  };

  // Validation function removed - validation happens automatically during deployment

  const handleDeployFlow = async () => {
    // Validation checks
    if (!validateJson(flowJson)) {
      notification.error({
        message: 'Invalid Flow Definition',
        description: 'Please fix the JSON errors before deploying'
      });
      return;
    }

    if (!flowName.trim()) {
      notification.error({
        message: 'Flow Name Required',
        description: 'Please enter a flow name'
      });
      return;
    }

    let bucketId = selectedBucketId;

    // Handle bucket creation if needed
    if (bucketMode === 'create') {
      if (!newBucketName.trim()) {
        notification.error({
          message: 'Bucket Name Required',
          description: 'Please enter a bucket name to create a new registry bucket'
        });
        return;
      }

      try {
        setStatus('deploying');
        setDeploymentProgress(20);
        setDeploymentStage('Creating registry bucket...');

        const newBucket = await flowAPI.createBucket(newBucketName, newBucketDescription);
        bucketId = newBucket.bucket_id;
        
        // Update buckets list
        setBuckets(prev => [...prev, newBucket]);
        // Bucket created successfully (showing in deployment success instead)
      } catch (bucketError: any) {
        console.error('Bucket creation error:', bucketError);
        setStatus('error');
        
        const errorData = bucketError?.response?.data?.detail || {};
        
        // Set error details for status panel display
        setErrorDetails(errorData.details || {});
        setValidationErrors(errorData.details?.failures || []);
        
        // Simple notification for bucket creation failure
        const errorMessage =
          errorData.user_message ||
          bucketError?.message ||
          'Failed to create bucket';

        notification.error({
          message: 'Bucket Creation Failed',
          description: errorMessage
        });
        return;
      }
    }

    if (!bucketId) {
      notification.error({
        message: 'Bucket Required',
        description: 'Please select an existing bucket or create a new one'
      });
      return;
    }

    // Deploy the flow
    try {
      setDeployLoading(true);
      setStatus('deploying');
      setDeploymentProgress(60);
      setDeploymentStage('Deploying flow to NiFi...');

      const flowDefinition = JSON.parse(flowJson);
      
      // Override name and description from form
      flowDefinition.name = flowName;
      flowDefinition.description = flowDescription;

      await flowAPI.deployAndStore(flowDefinition, bucketId, flowParameters);

      setStatus('success');
      setDeploymentProgress(100);
      setDeploymentStage('');

      // Reset form after successful deployment and optionally go back
      setTimeout(() => {
        setStatus('idle');
        setDeploymentProgress(0);
        if (onBack) {
          onBack(); // Return to flows list after successful deployment
        }
      }, 2000);

    } catch (deploymentError: any) {
      console.error('Flow deployment error:', deploymentError);
      setDeployLoading(false);
      setStatus('error');
      setDeploymentProgress(0);
      setDeploymentStage('');
      
      // Extract detailed error information
      const errorData = deploymentError?.response?.data?.detail || {};
      const hasDetailedErrors = errorData.details?.failures?.length > 0;
      
      if (hasDetailedErrors) {
        setErrorDetails(errorData.details);
        setValidationErrors(errorData.details.failures || []);
        
        // Error details now shown in status panel instead of modal
      } else {
        notification.error({
          message: 'Deployment Failed',
          description: errorData.user_message || 'Failed to deploy flow'
        });
      }
    } finally {
      setDeployLoading(false);
    }
  };

  const leftPanel = (
    <FlowJsonEditor
      value={flowJson}
      onChange={handleJsonChange}
      error={jsonError}
      loading={deployLoading}
      extra={
        <TemplateDropdown
          onTemplateSelect={handleTemplateSelect}
          disabled={deployLoading}
        />
      }
    />
  );

  const rightPanel = (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <MinimizableCard
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <DatabaseOutlined />
            <Text strong>Registry Bucket</Text>
          </div>
        }
        defaultMinimized={false}
      >
        <BucketSelector
          buckets={buckets}
          mode={bucketMode}
          selectedBucketId={selectedBucketId}
          newBucketName={newBucketName}
          newBucketDescription={newBucketDescription}
          onModeChange={setBucketMode}
          onBucketSelect={setSelectedBucketId}
          onNewBucketNameChange={setNewBucketName}
          onNewBucketDescriptionChange={setNewBucketDescription}
          loading={bucketsLoading || deployLoading}
        />
      </MinimizableCard>
      
      <MinimizableCard
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RocketOutlined />
            <Text strong>Flow Configuration</Text>
          </div>
        }
        defaultMinimized={false}
      >
        <FlowActions
          flowName={flowName}
          flowDescription={flowDescription}
          onFlowNameChange={setFlowName}
          onFlowDescriptionChange={setFlowDescription}
          onDeploy={handleDeployFlow}
          deployLoading={deployLoading}
          canDeploy={!jsonError && flowName.trim().length > 0}
        />
      </MinimizableCard>
      
      {(Object.keys(flowParameters).length > 0 || Object.keys(templateParameters).length > 0) && (
        <MinimizableCard
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <SettingOutlined />
              <Text strong>Flow Parameters</Text>
            </div>
          }
          defaultMinimized={false}
        >
          <ParameterEditor
            parameters={flowParameters}
            onParametersChange={setFlowParameters}
            templateParameters={templateParameters}
            disabled={deployLoading}
          />
        </MinimizableCard>
      )}
      
      <div style={{ flex: 1 }}>
        <MinimizableCard
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <InfoCircleOutlined />
              <Text strong>Flow Status</Text>
            </div>
          }
          defaultMinimized={false}
          style={{ marginBottom: 0, height: '100%' }}
          bodyStyle={{ height: 'calc(100% - 57px)', overflow: 'auto' }}
        >
          <FlowStatusPanel
            status={status}
            validationErrors={validationErrors}
            deploymentProgress={deploymentProgress}
            deploymentStage={deploymentStage}
            successMessage={status === 'success' ? `Flow "${flowName}" deployed successfully` : undefined}
            errorMessage={status === 'error' ? 'Flow deployment failed' : undefined}
            errorDetails={errorDetails}
          />
        </MinimizableCard>
      </div>
    </div>
  );

  const pageTitle = editingFlowId ? "Edit Flow" : "Create New Flow";
  
  return (
    <div style={{ background: '#f5f5f5', minHeight: '100vh' }}>
      {/* Header with back button */}
      <div style={{ 
        padding: '16px 24px', 
        background: '#fff', 
        borderBottom: '1px solid #d9d9d9',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {onBack && (
            <Button onClick={onBack}>
              ← Back to Flows
            </Button>
          )}
          <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>
            {pageTitle}
          </h2>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ padding: '24px' }}>
        <div style={{ 
          background: '#fff', 
          borderRadius: '6px', 
          border: '1px solid #d9d9d9',
          overflow: 'hidden'
        }}>
          <SplitPanel
            leftPanel={leftPanel}
            rightPanel={rightPanel}
            leftSpan={14}
            rightSpan={10}
            gutter={24}
          />
        </div>
      </div>
    </div>
  );
};