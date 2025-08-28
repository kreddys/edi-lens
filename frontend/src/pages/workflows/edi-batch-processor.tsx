import React from 'react';
import { EdiBatchProcessor } from '../../components/workflow/EdiBatchProcessor';
import { useNavigate } from 'react-router-dom';

export const EdiBatchProcessorPage: React.FC = () => {
  const navigate = useNavigate();

  const handleWorkflowCreate = (workflow: any) => {
    console.log('Workflow created:', workflow);
    // Optionally navigate to workflow details page
    // navigate(`/workflows/show/${workflow.workflow_id}`);
  };

  const handleExecutionComplete = (result: any) => {
    console.log('Execution completed:', result);
    // Handle execution completion
  };

  return (
    <EdiBatchProcessor
      onWorkflowCreate={handleWorkflowCreate}
      onExecutionComplete={handleExecutionComplete}
    />
  );
};

export default EdiBatchProcessorPage;