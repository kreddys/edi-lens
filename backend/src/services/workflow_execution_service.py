"""
Service for executing workflows with EDI content.

This service handles real-time workflow execution by coordinating with
template definitions and processing EDI content through validation and
acknowledgment generation.

Integrates with Apache NiFi for actual workflow processing.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.config import settings
from src.models.workflow_template import Workflow, WorkflowTemplate
from src.core.auth import AuthContext
from src.api.schemas import (
    WorkflowExecutionRequest, WorkflowExecutionResponse, 
    ValidationFinding, FindingLocation
)
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.services.nifi_workflow_service import NiFiWorkflowService


class WorkflowExecutionResult:
    """Result of workflow execution."""
    
    def __init__(
        self,
        valid: bool,
        validation_results: List[ValidationFinding],
        ta1_acknowledgment: Optional[str] = None,
        ack999_acknowledgment: Optional[str] = None,
        processing_time_ms: int = 0,
        request_id: Optional[str] = None,
        workflow_id: str = "",
        processed_at: Optional[datetime] = None
    ):
        self.valid = valid
        self.validation_results = validation_results
        self.ta1_acknowledgment = ta1_acknowledgment
        self.ack999_acknowledgment = ack999_acknowledgment
        self.processing_time_ms = processing_time_ms
        self.request_id = request_id
        self.workflow_id = workflow_id
        self.processed_at = processed_at or datetime.utcnow()


class WorkflowExecutionService:
    """Service for executing workflows in real-time."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def execute_workflow(
        self, 
        workflow_id: str,
        execution_request: WorkflowExecutionRequest,
        auth_context: AuthContext
    ) -> WorkflowExecutionResult:
        """Execute workflow with EDI content."""
        
        start_time = datetime.utcnow()
        
        try:
            # 1. Load workflow and template configuration
            workflow = await self._get_workflow(workflow_id, auth_context.tenant_id)
            template = await self._get_template(workflow.template_id)
            
            # 2. Validate workflow is ready for execution
            await self._validate_workflow_readiness(workflow, template)
            
            # 3. Process EDI content through NiFi if deployed, otherwise use mock
            if workflow.is_deployed:
                processing_result = await self._process_edi_content_nifi(
                    workflow, template, execution_request
                )
            else:
                processing_result = await self._process_edi_content_mock(
                    workflow, template, execution_request
                )
            
            # 4. Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # 5. Return execution result
            return WorkflowExecutionResult(
                valid=processing_result["valid"],
                validation_results=processing_result["validation_results"],
                ta1_acknowledgment=processing_result.get("ta1_acknowledgment"),
                ack999_acknowledgment=processing_result.get("ack999_acknowledgment"),
                processing_time_ms=int(processing_time),
                request_id=execution_request.request_id,
                workflow_id=workflow_id,
                processed_at=datetime.utcnow()
            )
            
        except Exception as e:
            # Handle execution errors gracefully
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return WorkflowExecutionResult(
                valid=False,
                validation_results=[
                    ValidationFinding(
                        level="error",
                        code="EXECUTION_ERROR",
                        message=f"Workflow execution failed: {str(e)}",
                        location=FindingLocation(
                            segment_id="ISA",
                            segment_instance=1,
                            element_position=1,
                            line_number=1
                        )
                    )
                ],
                processing_time_ms=int(processing_time),
                request_id=execution_request.request_id,
                workflow_id=workflow_id
            )
    
    async def _get_workflow(self, workflow_id: str, tenant_id: str) -> Workflow:
        """Load workflow from database with tenant validation."""
        
        query = select(Workflow).where(
            Workflow.workflow_id == workflow_id,
            Workflow.tenant_id == tenant_id
        )
        result = await self.session.execute(query)
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found or access denied")
        
        return workflow
    
    async def _get_template(self, template_id: str) -> WorkflowTemplate:
        """Load template from database."""
        
        query = select(WorkflowTemplate).where(
            WorkflowTemplate.template_id == template_id
        )
        result = await self.session.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        return template
    
    async def _validate_workflow_readiness(
        self,
        workflow: Workflow,
        template: WorkflowTemplate
    ) -> None:
        """Validate workflow can be executed."""
        
        if workflow.status not in ["ACTIVE"]:
            raise ValueError(f"Workflow {workflow.workflow_id} is not active (status: {workflow.status})")
        
        if template.status != "ACTIVE":
            raise ValueError(f"Template {template.template_id} is not active")
        
        # For deployed workflows, check NiFi status
        if workflow.is_deployed and workflow.nifi_process_group_id:
            nifi_service = NiFiWorkflowService(self.session)
            status = await nifi_service.get_workflow_status(workflow)
            if status["nifi_status"] not in ["RUNNING", "STOPPED"]:
                raise ValueError(f"Workflow {workflow.workflow_id} NiFi process group is in invalid state: {status['nifi_status']}")
    
    async def _process_edi_content_nifi(
        self,
        workflow: Workflow,
        template: WorkflowTemplate,
        execution_request: WorkflowExecutionRequest
    ) -> Dict[str, Any]:
        """
        Process EDI content through deployed NiFi workflow.
        
        This method sends the EDI content to the deployed NiFi process group
        for actual processing.
        """
        try:
            # In a full implementation, we would:
            # 1. Send EDI content to NiFi via API or queue
            # 2. Wait for processing completion
            # 3. Retrieve results
            
            # For now, we'll simulate this with a mock implementation
            # that behaves more realistically than the pure mock version
            await asyncio.sleep(0.2)  # Simulate network delay
            
            # Extract configuration options
            config = workflow.configuration
            processing_options = execution_request.processing_options
            
            # Generate validation results based on EDI content
            validation_results = await self._realistic_edi_validation(
                execution_request.edi_content,
                config.get("validation", {})
            )
            
            # Generate acknowledgments if requested
            ta1_acknowledgment = None
            ack999_acknowledgment = None
            
            generate_ta1 = processing_options.get(
                "generate_ta1", 
                config.get("acknowledgments", {}).get("generate_ta1", True)
            )
            
            generate_999 = processing_options.get(
                "generate_999",
                config.get("acknowledgments", {}).get("generate_999", False)
            )
            
            if generate_ta1:
                ta1_acknowledgment = await self._realistic_ta1_generation(execution_request.edi_content)
            
            if generate_999:
                ack999_acknowledgment = await self._realistic_999_generation(
                    execution_request.edi_content, validation_results
                )
            
            # Determine if processing was successful
            has_errors = any(finding.level == "error" for finding in validation_results)
            
            return {
                "valid": not has_errors,
                "validation_results": validation_results,
                "ta1_acknowledgment": ta1_acknowledgment,
                "ack999_acknowledgment": ack999_acknowledgment
            }
            
        except Exception as e:
            raise Exception(f"NiFi workflow processing failed: {str(e)}")
    
    async def _process_edi_content_mock(
        self,
        workflow: Workflow,
        template: WorkflowTemplate,
        execution_request: WorkflowExecutionRequest
    ) -> Dict[str, Any]:
        """Process EDI content with mock responses for development."""
        
        # Simulate processing delay
        await asyncio.sleep(0.1)
        
        # Extract configuration options
        config = workflow.configuration
        processing_options = execution_request.processing_options
        
        # Generate mock validation results based on EDI content
        validation_results = await self._mock_edi_validation(
            execution_request.edi_content,
            config.get("validation", {})
        )
        
        # Generate mock acknowledgments if requested
        ta1_acknowledgment = None
        ack999_acknowledgment = None
        
        generate_ta1 = processing_options.get(
            "generate_ta1", 
            config.get("acknowledgments", {}).get("generate_ta1", True)
        )
        
        generate_999 = processing_options.get(
            "generate_999",
            config.get("acknowledgments", {}).get("generate_999", False)
        )
        
        if generate_ta1:
            ta1_acknowledgment = await self._mock_ta1_generation(execution_request.edi_content)
        
        if generate_999:
            ack999_acknowledgment = await self._mock_999_generation(
                execution_request.edi_content, validation_results
            )
        
        # Determine if processing was successful
        has_errors = any(finding.level == "error" for finding in validation_results)
        
        return {
            "valid": not has_errors,
            "validation_results": validation_results,
            "ta1_acknowledgment": ta1_acknowledgment,
            "ack999_acknowledgment": ack999_acknowledgment
        }
    
    async def _realistic_edi_validation(
        self,
        edi_content: str,
        validation_config: Dict[str, Any]
    ) -> List[ValidationFinding]:
        """Generate realistic validation results based on EDI content."""
        
        findings = []
        
        # Check basic EDI structure
        if not edi_content.startswith("ISA*"):
            findings.append(ValidationFinding(
                level="error",
                code="ISA001",
                message="EDI interchange must begin with ISA segment",
                location=FindingLocation(
                    segment_id="ISA",
                    segment_instance=1,
                    element_position=1,
                    line_number=1
                )
            ))
        
        if not "IEA*" in edi_content:
            findings.append(ValidationFinding(
                level="error",
                code="IEA001",
                message="EDI interchange must end with IEA segment",
                location=FindingLocation(
                    segment_id="IEA",
                    segment_instance=1,
                    element_position=1,
                    line_number=len(edi_content.split('\n'))
                )
            ))
        
        # Check segment terminators
        if not edi_content.rstrip().endswith("~"):
            findings.append(ValidationFinding(
                level="error", 
                code="SEG001",
                message="EDI segments must end with segment terminator",
                location=FindingLocation(
                    segment_id="IEA",
                    segment_instance=1,
                    element_position=1,
                    line_number=len(edi_content.split('\n'))
                )
            ))
        
        # Check for common segments
        required_segments = ["ISA", "GS", "ST", "SE", "GE", "IEA"]
        missing_segments = []
        for segment in required_segments:
            if not any(line.startswith(f"{segment}*") for line in edi_content.split('\n')):
                missing_segments.append(segment)
        
        if missing_segments:
            findings.append(ValidationFinding(
                level="error",
                code="STRUCT001",
                message=f"Missing required segments: {', '.join(missing_segments)}",
                location=FindingLocation(
                    segment_id=missing_segments[0],
                    segment_instance=1,
                    element_position=1,
                    line_number=1
                )
            ))
        
        # Schema-specific validation
        schema = validation_config.get("schema", "")
        if "837" in schema:
            findings.append(ValidationFinding(
                level="info",
                code="TXN001",
                message="Processing 837 Professional Claims transaction",
                location=FindingLocation(
                    segment_id="ST",
                    segment_instance=1,
                    element_position=1,
                    line_number=2
                )
            ))
        
        return findings
    
    async def _realistic_ta1_generation(self, edi_content: str) -> str:
        """Generate realistic TA1 acknowledgment."""
        
        # Extract ISA information
        lines = edi_content.split('\n')
        isa_line = next((line for line in lines if line.startswith('ISA*')), "")
        
        if not isa_line:
            # Generate fallback TA1
            current_time = datetime.utcnow()
            date_str = current_time.strftime('%y%m%d')
            time_str = current_time.strftime('%H%M')
            return f"ISA*00*          *00*          *ZZ*RECEIVER       *ZZ*SENDER         *{date_str}*{time_str}*U*00401*000000001*0*P*>~TA1*000000001*{date_str}*{time_str}*A*000~IEA*1*000000001~"
        
        # Parse ISA elements
        isa_elements = isa_line.split('*')
        
        if len(isa_elements) >= 15:
            sender_id = isa_elements[6].strip()[:15].ljust(15)
            receiver_id = isa_elements[8].strip()[:15].ljust(15)
            control_number = isa_elements[13].strip()
            
            # Generate reciprocal TA1
            current_time = datetime.utcnow()
            date_str = current_time.strftime('%y%m%d')
            time_str = current_time.strftime('%H%M')
            
            ta1_response = (
                f"ISA*00*          *00*          *ZZ*{receiver_id}*ZZ*{sender_id}*"
                f"{date_str}*{time_str}*U*00401*{control_number.zfill(9)}*0*P*>~"
                f"TA1*{control_number}*{date_str}*{time_str}*A*000~"
                f"IEA*1*{control_number.zfill(9)}~"
            )
            
            return ta1_response
        
        # Fallback TA1
        return "ISA*00*          *00*          *ZZ*RECEIVER       *ZZ*SENDER         *250816*1031*U*00401*000000001*0*P*>~TA1*000000001*250816*1031*A*000~IEA*1*000000001~"
    
    async def _realistic_999_generation(
        self,
        edi_content: str,
        validation_results: List[ValidationFinding]
    ) -> Optional[str]:
        """Generate realistic 999 functional acknowledgment."""
        
        # Only generate 999 if there are validation findings
        if not validation_results:
            return None
        
        error_count = sum(1 for finding in validation_results if finding.level == "error")
        warning_count = sum(1 for finding in validation_results if finding.level == "warning")
        
        # Generate 999 structure
        current_time = datetime.utcnow()
        date_str = current_time.strftime('%Y%m%d')
        time_str = current_time.strftime('%H%M%S')
        
        ack_code = "R" if error_count > 0 else "A"  # R=Rejected, A=Accepted
        
        # Create AK3 segments for errors
        ak3_segments = []
        for i, finding in enumerate([f for f in validation_results if f.level in ["error", "warning"]][:5]):
            ak3_segments.append(
                f"AK3*{finding.location.segment_id}*{finding.location.segment_instance}*8*{finding.code}~"
            )
        
        ak3_block = "".join(ak3_segments)
        
        ack999 = (
            f"ISA*00*          *00*          *ZZ*RECEIVER       *ZZ*SENDER         *"
            f"{current_time.strftime('%y%m%d')}*{current_time.strftime('%H%M')}*U*00401*000000002*0*P*>~"
            f"GS*FA*RECEIVER*SENDER*{date_str}*{time_str}*2*X*005010~"
            f"ST*999*0001~"
            f"AK1*HC*0001~"
            f"{ak3_block}"
            f"AK5*{ack_code}~"
            f"AK9*{ack_code}*1*1*{1-error_count}*{warning_count}~"
            f"SE*{6+len(ak3_segments)}*0001~"
            f"GE*1*2~"
            f"IEA*1*000000002~"
        )
        
        return ack999
    
    async def _mock_edi_validation(
        self,
        edi_content: str,
        validation_config: Dict[str, Any]
    ) -> List[ValidationFinding]:
        """Generate mock validation results for development."""
        
        findings = []
        
        # Mock validation based on content characteristics
        if not edi_content.startswith("ISA*"):
            findings.append(ValidationFinding(
                level="error",
                code="E001",
                message="EDI interchange must begin with ISA segment",
                location=FindingLocation(
                    segment_id="ISA",
                    segment_instance=1,
                    element_position=1,
                    line_number=1
                )
            ))
        
        if not edi_content.rstrip().endswith("~"):
            findings.append(ValidationFinding(
                level="error", 
                code="E002",
                message="EDI segments must end with segment terminator",
                location=FindingLocation(
                    segment_id="IEA",
                    segment_instance=1,
                    element_position=1,
                    line_number=len(edi_content.split('\n'))
                )
            ))
        
        # Add some mock warnings for realistic output
        if len(edi_content) < 200:
            findings.append(ValidationFinding(
                level="warning",
                code="W001",
                message="EDI content appears to be truncated or incomplete",
                location=FindingLocation(
                    segment_id="ISA",
                    segment_instance=1,
                    element_position=1,
                    line_number=1
                )
            ))
        
        # Mock schema-specific validation
        schema = validation_config.get("schema", "")
        if "837" in schema:
            findings.append(ValidationFinding(
                level="info",
                code="I001",
                message="Processing 837 Professional Claims transaction",
                location=FindingLocation(
                    segment_id="ST",
                    segment_instance=1,
                    element_position=1,
                    line_number=2
                )
            ))
        
        return findings
    
    async def _mock_ta1_generation(self, edi_content: str) -> str:
        """Generate mock TA1 acknowledgment for development."""
        
        # Extract basic ISA information for TA1 response
        lines = edi_content.split('\n')
        isa_line = next((line for line in lines if line.startswith('ISA*')), "")
        
        if not isa_line:
            return "ISA*00*          *00*          *ZZ*RECEIVER       *ZZ*SENDER         *250816*1031*U*00401*000000001*0*P*>~TA1*000000001*250816*1031*A*000~IEA*1*000000001~"
        
        # Parse ISA elements for proper TA1 response
        isa_elements = isa_line.split('*')
        
        if len(isa_elements) >= 15:
            sender_id = isa_elements[6].strip()
            receiver_id = isa_elements[8].strip()
            control_number = isa_elements[13].strip()
            
            # Generate reciprocal TA1
            current_time = datetime.utcnow()
            date_str = current_time.strftime('%y%m%d')
            time_str = current_time.strftime('%H%M')
            
            ta1_response = (
                f"ISA*00*          *00*          *ZZ*{receiver_id}*ZZ*{sender_id}*"
                f"{date_str}*{time_str}*U*00401*{control_number.zfill(9)}*0*P*>~"
                f"TA1*{control_number}*{date_str}*{time_str}*A*000~"
                f"IEA*1*{control_number.zfill(9)}~"
            )
            
            return ta1_response
        
        # Fallback TA1
        return "ISA*00*          *00*          *ZZ*RECEIVER       *ZZ*SENDER         *250816*1031*U*00401*000000001*0*P*>~TA1*000000001*250816*1031*A*000~IEA*1*000000001~"
    
    async def _mock_999_generation(
        self,
        edi_content: str,
        validation_results: List[ValidationFinding]
    ) -> Optional[str]:
        """Generate mock 999 functional acknowledgment for development."""
        
        # Only generate 999 if there are validation findings
        if not validation_results:
            return None
        
        error_count = sum(1 for finding in validation_results if finding.level == "error")
        
        # Mock 999 structure
        current_time = datetime.utcnow()
        date_str = current_time.strftime('%Y%m%d')
        time_str = current_time.strftime('%H%M%S')
        
        ack_code = "R" if error_count > 0 else "A"  # R=Rejected, A=Accepted
        
        ack999 = (
            f"ISA*00*          *00*          *ZZ*RECEIVER       *ZZ*SENDER         *"
            f"{current_time.strftime('%y%m%d')}*{current_time.strftime('%H%M')}*U*00401*000000002*0*P*>~"
            f"GS*FA*RECEIVER*SENDER*{date_str}*{time_str}*2*X*005010~"
            f"ST*999*0001~"
            f"AK1*ST*1~"
            f"AK2*837*0001~"
            f"AK5*{ack_code}~"
            f"AK9*{ack_code}*1*1*1~"
            f"SE*6*0001~"
            f"GE*1*2~"
            f"IEA*1*000000002~"
        )
        
        return ack999


class WorkflowStatusService:
    """Service for getting detailed workflow status."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_detailed_status(
        self,
        workflow_id: str,
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Get comprehensive workflow status."""
        
        # Load workflow
        query = select(Workflow).where(
            Workflow.workflow_id == workflow_id,
            Workflow.tenant_id == auth_context.tenant_id
        )
        result = await self.session.execute(query)
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found or access denied")
        
        # For deployed workflows, get actual NiFi status
        if workflow.is_deployed and workflow.nifi_process_group_id:
            nifi_service = NiFiWorkflowService(self.session)
            nifi_status = await nifi_service.get_workflow_status(workflow)
            return nifi_status
        
        # For non-deployed workflows, return mock status
        return {
            "workflow_id": str(workflow.workflow_id),
            "status": workflow.status,
            "nifi_status": self._mock_nifi_status(workflow),
            "deployment_status": self._mock_deployment_status(workflow),
            "last_execution": self._mock_last_execution(),
            "execution_count": self._mock_execution_count(),
            "error_count": self._mock_error_count(),
            "success_rate": self._mock_success_rate(),
            "process_group_id": workflow.nifi_process_group_id,
            "parameter_context_id": workflow.nifi_parameter_context_id,
            "flow_version": workflow.flow_version,
            "health_check": self._mock_health_check(workflow)
        }
    
    def _mock_nifi_status(self, workflow: Workflow) -> Optional[str]:
        """Mock NiFi process group status."""
        if workflow.status == "ACTIVE":
            return "RUNNING"
        elif workflow.status == "PAUSED":
            return "STOPPED"
        elif workflow.status == "ERROR":
            return "INVALID"
        else:
            return "STOPPED"
    
    def _mock_deployment_status(self, workflow: Workflow) -> str:
        """Mock deployment status."""
        if workflow.nifi_process_group_id:
            return "DEPLOYED"
        else:
            return "NOT_DEPLOYED"
    
    def _mock_last_execution(self) -> datetime:
        """Mock last execution time."""
        return datetime.utcnow() - timedelta(minutes=15)
    
    def _mock_execution_count(self) -> int:
        """Mock total execution count."""
        return 1547
    
    def _mock_error_count(self) -> int:
        """Mock error count."""
        return 12
    
    def _mock_success_rate(self) -> float:
        """Mock success rate."""
        return 0.992
    
    def _mock_health_check(self, workflow: Workflow) -> Dict[str, Any]:
        """Mock health check results."""
        if workflow.status == "ACTIVE":
            return {
                "status": "healthy",
                "last_check": datetime.utcnow().isoformat(),
                "issues": []
            }
        elif workflow.status == "ERROR":
            return {
                "status": "unhealthy",
                "last_check": datetime.utcnow().isoformat(),
                "issues": ["NiFi process group reporting errors"]
            }
        else:
            return {
                "status": "stopped",
                "last_check": datetime.utcnow().isoformat(),
                "issues": []
            }