"""
NiFi Template Validator

This module provides comprehensive validation of workflow templates against 
NiFi OpenAPI specification before deployment to Registry, preventing deployment
failures through preemptive validation.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from enum import Enum

from ..exceptions.workflow_exceptions import (
    TemplateValidationError,
    ProcessorValidationError,
    ParameterSubstitutionError
)

log = logging.getLogger(__name__)


class ComponentType(Enum):
    """Valid NiFi component types according to OpenAPI spec."""
    CONNECTION = "CONNECTION"
    PROCESSOR = "PROCESSOR"
    PROCESS_GROUP = "PROCESS_GROUP"
    REMOTE_PROCESS_GROUP = "REMOTE_PROCESS_GROUP"
    INPUT_PORT = "INPUT_PORT"
    OUTPUT_PORT = "OUTPUT_PORT"
    REMOTE_INPUT_PORT = "REMOTE_INPUT_PORT"
    REMOTE_OUTPUT_PORT = "REMOTE_OUTPUT_PORT"
    FUNNEL = "FUNNEL"
    LABEL = "LABEL"
    CONTROLLER_SERVICE = "CONTROLLER_SERVICE"
    REPORTING_TASK = "REPORTING_TASK"
    FLOW_ANALYSIS_RULE = "FLOW_ANALYSIS_RULE"
    PARAMETER_CONTEXT = "PARAMETER_CONTEXT"
    PARAMETER_PROVIDER = "PARAMETER_PROVIDER"
    FLOW_REGISTRY_CLIENT = "FLOW_REGISTRY_CLIENT"


class ScheduledState(Enum):
    """Valid scheduled states for NiFi components."""
    ENABLED = "ENABLED"
    DISABLED = "DISABLED" 
    RUNNING = "RUNNING"


class SchedulingStrategy(Enum):
    """Valid scheduling strategies for processors."""
    TIMER_DRIVEN = "TIMER_DRIVEN"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    CRON_DRIVEN = "CRON_DRIVEN"


class NiFiTemplateValidator:
    """
    Validates workflow templates against NiFi OpenAPI specification.
    
    This validator catches structural errors, parameter reference issues, and
    schema compliance problems before templates are deployed to Registry.
    """

    def __init__(self):
        self.parameter_pattern = re.compile(r'#\{([^}]+)\}')
        self.legacy_parameter_pattern = re.compile(r'\$\{([^}]+)\}')
        self.required_processor_fields = {
            'identifier', 'name', 'type', 'componentType'
        }
        self.required_connection_fields = {
            'identifier', 'componentType', 'source', 'destination'
        }

    def validate_template(
        self, 
        template: Dict[str, Any],
        parameters: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Comprehensive template validation.
        
        Args:
            template: The workflow template to validate
            parameters: Optional parameter values for validation
            
        Returns:
            Tuple of (is_valid, list_of_errors)
            
        Raises:
            TemplateValidationError: If validation fails with critical errors
        """
        errors = []
        
        try:
            # 1. Validate RegisteredFlowSnapshot structure
            errors.extend(self._validate_registered_flow_snapshot_structure(template))
            
            # 2. Validate VersionedProcessGroup structure (NiFi Registry standard format)
            if 'flowContents' in template:
                errors.extend(self._validate_versioned_process_group(template['flowContents']))
            else:
                errors.append("Template missing required 'flowContents' (NiFi Registry standard format)")
            
            # 3. Validate processors
            processors = self._extract_processors(template)
            for processor in processors:
                errors.extend(self._validate_processor(processor))
                
            # 4. Validate connections
            connections = self._extract_connections(template)
            for connection in connections:
                errors.extend(self._validate_connection(connection))
                
            # 5. Validate parameter references
            if parameters:
                errors.extend(self._validate_parameter_references(template, parameters))
            
            # 6. Validate component relationships
            errors.extend(self._validate_component_relationships(processors, connections))
            
            is_valid = len(errors) == 0
            
            if not is_valid:
                log.error(f"Template validation failed with {len(errors)} errors: {errors}")
            else:
                log.info("Template validation passed successfully")
                
            return is_valid, errors
            
        except Exception as e:
            error_msg = f"Template validation failed with exception: {str(e)}"
            log.error(error_msg)
            raise TemplateValidationError(error_msg) from e

    def _validate_registered_flow_snapshot_structure(self, template: Dict[str, Any]) -> List[str]:
        """Validate RegisteredFlowSnapshot structure compliance."""
        errors = []
        
        # Check for required top-level structure
        if 'bucket' not in template and 'snapshotMetadata' not in template:
            # This might be our internal format, check for flow_definition
            if 'flow_definition' not in template and 'flowContents' not in template:
                errors.append("Template must have either RegisteredFlowSnapshot structure or flow_definition")
                
        # Validate metadata structure if present
        if 'snapshotMetadata' in template:
            metadata = template['snapshotMetadata']
            required_metadata_fields = ['flowIdentifier', 'version']
            for field in required_metadata_fields:
                if field not in metadata:
                    errors.append(f"snapshotMetadata missing required field: {field}")
                    
        # Validate bucket structure if present  
        if 'bucket' in template:
            bucket = template['bucket']
            if not isinstance(bucket, dict) or 'identifier' not in bucket:
                errors.append("bucket must be an object with 'identifier' field")
                
        return errors

    def _validate_versioned_process_group(self, process_group: Dict[str, Any]) -> List[str]:
        """Validate VersionedProcessGroup structure."""
        errors = []
        
        if not isinstance(process_group, dict):
            errors.append("flowContents must be a dictionary")
            return errors
            
        # Check for processors array
        if 'processors' in process_group:
            if not isinstance(process_group['processors'], list):
                errors.append("processors must be an array")
        else:
            errors.append("VersionedProcessGroup missing 'processors' array")
            
        # Check for connections array
        if 'connections' in process_group:
            if not isinstance(process_group['connections'], list):
                errors.append("connections must be an array")
        else:
            # Connections are optional if no processors connect to each other
            pass
            
        # Validate optional fields with correct types
        optional_arrays = ['inputPorts', 'outputPorts', 'processGroups', 'funnels', 'labels']
        for field in optional_arrays:
            if field in process_group and not isinstance(process_group[field], list):
                errors.append(f"{field} must be an array")
                
        return errors

    def _validate_processor(self, processor: Dict[str, Any]) -> List[str]:
        """Validate VersionedProcessor structure and properties."""
        errors = []
        
        # Check required fields
        for field in self.required_processor_fields:
            if field not in processor:
                errors.append(f"Processor missing required field: {field}")
                
        # Validate componentType
        if 'componentType' in processor:
            if processor['componentType'] != ComponentType.PROCESSOR.value:
                errors.append(f"Processor componentType must be '{ComponentType.PROCESSOR.value}', got: {processor['componentType']}")
        
        # Validate type field (processor class)
        if 'type' in processor:
            processor_type = processor['type']
            if not processor_type.startswith('org.apache.nifi.processors.'):
                log.warning(f"Processor type '{processor_type}' may not be a standard NiFi processor")
                
        # Validate properties structure
        if 'properties' in processor:
            if not isinstance(processor['properties'], dict):
                errors.append("Processor properties must be a dictionary")
            else:
                # Check for parameter syntax - distinguish between NiFi Expression Language and Parameter Context references
                for prop_name, prop_value in processor['properties'].items():
                    if isinstance(prop_value, str) and self.legacy_parameter_pattern.search(prop_value):
                        # Extract the content inside ${...}
                        matches = self.legacy_parameter_pattern.findall(prop_value)
                        for match in matches:
                            # Check if this looks like a NiFi Expression Language function vs a parameter reference
                            if self._is_nifi_expression_language(match):
                                # This is correct NiFi Expression Language, not a parameter reference
                                continue
                            else:
                                # This should be a Parameter Context reference using #{} syntax
                                errors.append(f"Processor '{processor.get('name', 'unknown')}' property '{prop_name}' uses legacy parameter syntax '${{}}'. Use '#{{}}' for Parameter Context references")
        
        # Validate optional scheduling fields
        if 'schedulingStrategy' in processor:
            strategy = processor['schedulingStrategy']
            try:
                SchedulingStrategy(strategy)
            except ValueError:
                errors.append(f"Invalid schedulingStrategy: {strategy}")
                
        if 'scheduledState' in processor:
            state = processor['scheduledState']
            try:
                ScheduledState(state)
            except ValueError:
                errors.append(f"Invalid scheduledState: {state}")
                
        # Validate concurrent tasks
        if 'concurrentlySchedulableTaskCount' in processor:
            count = processor['concurrentlySchedulableTaskCount']
            if not isinstance(count, int) or count < 1:
                errors.append(f"concurrentlySchedulableTaskCount must be a positive integer, got: {count}")
                
        return errors

    def _validate_connection(self, connection: Dict[str, Any]) -> List[str]:
        """Validate VersionedConnection structure."""
        errors = []
        
        # Check required fields
        for field in self.required_connection_fields:
            if field not in connection:
                errors.append(f"Connection missing required field: {field}")
                
        # Validate componentType
        if 'componentType' in connection:
            if connection['componentType'] != ComponentType.CONNECTION.value:
                errors.append(f"Connection componentType must be '{ComponentType.CONNECTION.value}', got: {connection['componentType']}")
                
        # Validate source and destination structure
        for endpoint in ['source', 'destination']:
            if endpoint in connection:
                endpoint_obj = connection[endpoint]
                if not isinstance(endpoint_obj, dict):
                    errors.append(f"Connection {endpoint} must be an object")
                elif 'id' not in endpoint_obj:
                    errors.append(f"Connection {endpoint} missing required 'id' field")
                    
        # Validate selectedRelationships
        if 'selectedRelationships' in connection:
            relationships = connection['selectedRelationships']
            if not isinstance(relationships, list):
                errors.append("selectedRelationships must be an array")
            elif len(relationships) == 0:
                errors.append("Connection must have at least one selected relationship")
                
        return errors

    def _validate_parameter_references(
        self, 
        template: Dict[str, Any], 
        parameters: Dict[str, str]
    ) -> List[str]:
        """Validate parameter references and availability."""
        errors = []
        
        # Extract all parameter references from template
        referenced_params = self._extract_parameter_references(template)
        provided_params = set(parameters.keys())
        
        # Check for missing parameters
        missing_params = referenced_params - provided_params
        if missing_params:
            errors.append(f"Template references undefined parameters: {sorted(missing_params)}")
            
        # Check for unused parameters (warning only)
        unused_params = provided_params - referenced_params
        if unused_params:
            log.warning(f"Provided parameters not used in template: {sorted(unused_params)}")
            
        return errors

    def _validate_component_relationships(
        self, 
        processors: List[Dict[str, Any]], 
        connections: List[Dict[str, Any]]
    ) -> List[str]:
        """Validate relationships between processors and connections."""
        errors = []
        
        processor_ids = {p.get('identifier') for p in processors if p.get('identifier')}
        
        # Validate connection endpoints reference existing processors
        for connection in connections:
            source_id = connection.get('source', {}).get('id')
            dest_id = connection.get('destination', {}).get('id')
            
            if source_id and source_id not in processor_ids:
                # Could be input port or other component, so only warn
                log.warning(f"Connection source '{source_id}' not found in processors")
                
            if dest_id and dest_id not in processor_ids:
                # Could be output port or other component, so only warn  
                log.warning(f"Connection destination '{dest_id}' not found in processors")
                
        return errors

    def _extract_processors(self, template: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all processors from template (NiFi Registry standard format)."""
        processors = []
        
        # Use standard NiFi Registry format: flowContents at root level
        if 'flowContents' in template and 'processors' in template['flowContents']:
            processors.extend(template['flowContents']['processors'])
            
        return processors

    def _extract_connections(self, template: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all connections from template (NiFi Registry standard format)."""
        connections = []
        
        # Use standard NiFi Registry format: flowContents at root level
        if 'flowContents' in template and 'connections' in template['flowContents']:
            connections.extend(template['flowContents']['connections'])
            
        return connections

    def _extract_parameter_references(self, obj: Any, references: Optional[Set[str]] = None) -> Set[str]:
        """Recursively extract parameter references from template structure."""
        if references is None:
            references = set()
            
        if isinstance(obj, str):
            # Find #{param} references
            matches = self.parameter_pattern.findall(obj)
            references.update(matches)
            
        elif isinstance(obj, dict):
            for value in obj.values():
                self._extract_parameter_references(value, references)
                
        elif isinstance(obj, list):
            for item in obj:
                self._extract_parameter_references(item, references)
                
        return references

    def _is_nifi_expression_language(self, expression: str) -> bool:
        """
        Check if an expression is NiFi Expression Language vs a Parameter Context reference.
        
        NiFi Expression Language includes:
        - Built-in functions: now(), filename, uuid, etc.
        - Attribute references: attribute_name
        - Function calls: now():format('pattern'), toUpper(), etc.
        
        Parameter Context references are typically:
        - Simple parameter names: input_directory, output_path, etc.
        """
        # Common NiFi Expression Language patterns
        nifi_functions = [
            'now()', 'filename', 'uuid', 'hostname', 'ip', 'literal', 'random',
            'toUpper', 'toLower', 'trim', 'substring', 'replace', 'replaceAll',
            'contains', 'startsWith', 'endsWith', 'indexOf', 'lastIndexOf',
            'format', 'toDate', 'fromDate', 'plus', 'minus', 'multiply', 'divide',
            'mod', 'and', 'or', 'not', 'gt', 'lt', 'ge', 'le', 'eq', 'ne'
        ]
        
        # Check if the expression contains NiFi function calls
        for func in nifi_functions:
            if func in expression:
                return True
        
        # Check for function call patterns like "something()" or "something:"
        import re
        if re.search(r'\w+\([^)]*\)|[\w:]+:', expression):
            return True
            
        # If it's a simple word without underscores/hyphens, it might be a NiFi attribute
        # Parameter names typically use underscores or hyphens
        if re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', expression.strip()):
            return True
            
        return False

    async def validate_against_live_nifi(
        self, 
        template: Dict[str, Any],
        nifi_client
    ) -> Tuple[bool, List[str]]:
        """
        Validate template processors against live NiFi instance.
        
        Args:
            template: The workflow template to validate
            nifi_client: NiFiAPIClient instance for querying live NiFi
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Get all available processor types from NiFi
            processor_types_response = await nifi_client.get_processor_types()
            available_processors = {}
            
            # Get detailed info for each processor type (including property descriptors)
            log.debug(f"Getting detailed info for processor types...")
            for processor in processor_types_response.get("processorTypes", []):
                processor_type = processor.get("type")
                if processor_type:
                    # For validation, we only need details for processors used in the template
                    available_processors[processor_type] = processor
            
            log.debug(f"Found {len(available_processors)} available processor types in NiFi")
            
            # Extract and validate each processor from template
            processors = self._extract_processors(template)
            log.debug(f"Validating {len(processors)} processors from template")
            
            for processor in processors:
                processor_errors = await self._validate_processor_against_live_nifi(
                    processor, available_processors, nifi_client
                )
                errors.extend(processor_errors)
            
            is_valid = len(errors) == 0
            
            if not is_valid:
                log.error(f"Dynamic NiFi validation failed with {len(errors)} errors: {errors}")
            else:
                log.info("Dynamic NiFi validation passed successfully")
                
            return is_valid, errors
            
        except Exception as e:
            error_msg = f"Dynamic NiFi validation failed with exception: {str(e)}"
            log.error(error_msg)
            return False, [error_msg]

    async def _validate_processor_against_live_nifi(
        self,
        processor: Dict[str, Any],
        available_processors: Dict[str, Dict[str, Any]],
        nifi_client
    ) -> List[str]:
        """Validate a single processor against available NiFi processor types."""
        errors = []
        processor_name = processor.get('name', 'Unknown')
        processor_type = processor.get('type')
        
        if not processor_type:
            errors.append(f"Processor '{processor_name}' missing type field")
            return errors
        
        # Check if processor type exists in NiFi
        if processor_type not in available_processors:
            # Suggest similar processor types
            similar_types = [pt for pt in available_processors.keys() if processor_type.split('.')[-1].lower() in pt.lower()]
            if similar_types:
                errors.append(f"Processor type '{processor_type}' not available in NiFi instance. "
                            f"Similar available types: {', '.join(similar_types[:3])}")
            else:
                errors.append(f"Processor type '{processor_type}' not available in NiFi instance")
            return errors
        
        # Get detailed processor information including property descriptors
        log.debug(f"Getting detailed processor information for {processor_type}")
        nifi_processor = await nifi_client.get_processor_type_details(processor_type)
        
        if not nifi_processor:
            errors.append(f"Failed to get detailed information for processor type '{processor_type}'")
            return errors
        
        # Check if bundle is available (not missing)
        bundle = nifi_processor.get("bundle", {})
        if bundle.get("extensionMissing", False):
            errors.append(f"Bundle for processor type '{processor_type}' is missing in NiFi")
        
        # Validate processor properties against property descriptors
        processor_properties = processor.get('properties', {})
        supported_properties = {}
        
        # Index supported properties
        supported_property_descriptors = nifi_processor.get("supportedPropertyDescriptors", [])
        log.debug(f"Processor {processor_type} has {len(supported_property_descriptors)} property descriptors")
        
        for prop_descriptor in supported_property_descriptors:
            prop_name = prop_descriptor.get("name")
            if prop_name:
                supported_properties[prop_name] = prop_descriptor
                log.debug(f"Found property: {prop_name}")
            else:
                log.debug(f"Property descriptor missing name: {prop_descriptor}")
        
        log.debug(f"Final supported properties for {processor_type}: {list(supported_properties.keys())}")
        
        # Check required properties are provided
        for prop_descriptor in nifi_processor.get("supportedPropertyDescriptors", []):
            prop_name = prop_descriptor.get("name")
            is_required = prop_descriptor.get("required", False)
            
            if is_required and prop_name not in processor_properties:
                # Check if property has a default value
                default_value = prop_descriptor.get("defaultValue")
                if not default_value:
                    errors.append(f"Processor '{processor_name}' missing required property: {prop_name}")
        
        # Validate provided properties exist and have valid values
        for prop_name, prop_value in processor_properties.items():
            if prop_name not in supported_properties:
                # Many NiFi processors (e.g., UpdateAttribute) support dynamic properties that are not listed
                # Skip strict validation for unknown properties and rely on the live creation/update test below
                log.debug(
                    f"Skipping strict property validation for dynamic property '{prop_name}' on processor '{processor_name}'"
                )
                continue
            
            prop_descriptor = supported_properties[prop_name]
            
            # Validate allowable values if specified
            allowable_values = prop_descriptor.get("allowableValues", [])
            if allowable_values and prop_value is not None:
                # Skip validation for parameter references (#{...})
                if not (isinstance(prop_value, str) and self.parameter_pattern.search(prop_value)):
                    valid_values = [av.get("value") for av in allowable_values if av and av.get("value") is not None]
                    # Only validate if there are actual allowable values
                    if valid_values and prop_value not in valid_values:
                        errors.append(f"Processor '{processor_name}' property '{prop_name}' has invalid value. "
                                    f"Expected one of {valid_values}, got: {prop_value}")
        
        # Perform comprehensive validation by testing actual processor creation
        creation_errors = await self._test_processor_creation(processor, nifi_client)
        errors.extend(creation_errors)
        
        return errors

    async def _test_processor_creation(
        self,
        processor: Dict[str, Any],
        nifi_client
    ) -> List[str]:
        """Test if the processor can actually be created in NiFi to catch import-time failures."""
        errors = []
        processor_name = processor.get('name', 'Unknown')
        processor_type = processor.get('type')
        
        try:
            # Get root process group
            root_pg = await nifi_client.get_process_group("root")
            root_id = root_pg["component"]["id"]
            
            # Test processor creation with actual configuration
            log.debug(f"Testing creation of processor '{processor_name}' of type '{processor_type}'")
            
            test_processor = await nifi_client.create_processor(
                parent_group_id=root_id,
                processor_type=processor_type,
                name=f"TEST_VALIDATION_{processor_name}",
                position={"x": 0, "y": 0}
            )
            
            test_id = test_processor["id"]
            
            try:
                # Apply the processor properties from template
                processor_properties = processor.get('properties', {})
                if processor_properties:
                    # Get current processor state
                    current_processor = await nifi_client.get_processor(test_id)
                    current_version = current_processor.get("revision", {}).get("version", 0)
                    
                    # Prepare update payload
                    update_payload = {
                        "component": {
                            "id": test_id,
                            "config": {
                                "properties": processor_properties
                            }
                        },
                        "revision": {
                            "version": current_version
                        }
                    }
                    
                    # Test property application
                    log.debug(f"Testing property application for processor '{processor_name}'")
                    await nifi_client.session.put(
                        f"{nifi_client.nifi_url}/processors/{test_id}",
                        json=update_payload
                    )
                    
                log.info(f"✅ Processor '{processor_name}' creation test passed")
                
            except Exception as prop_error:
                error_msg = f"Processor '{processor_name}' property application failed: {str(prop_error)}"
                log.error(error_msg)
                errors.append(error_msg)
                
            finally:
                # Clean up test processor
                try:
                    current_processor = await nifi_client.get_processor(test_id)
                    current_version = current_processor.get("revision", {}).get("version", 0)
                    await nifi_client.session.delete(f"{nifi_client.nifi_url}/processors/{test_id}?version={current_version}")
                    log.debug(f"Cleaned up test processor '{processor_name}'")
                except Exception as cleanup_error:
                    log.warning(f"Failed to clean up test processor {test_id}: {cleanup_error}")
                    
        except Exception as creation_error:
            error_msg = f"Processor '{processor_name}' creation test failed: {str(creation_error)}"
            log.error(error_msg)
            errors.append(error_msg)
            
        return errors

    def validate_for_registry_deployment(self, template: Dict[str, Any]) -> None:
        """
        Validate template specifically for Registry deployment.
        
        Raises appropriate exceptions for deployment blocking issues.
        """
        is_valid, errors = self.validate_template(template)
        
        if not is_valid:
            # Group errors by type for better error messages
            processor_errors = [e for e in errors if 'Processor' in e]
            connection_errors = [e for e in errors if 'Connection' in e]
            parameter_errors = [e for e in errors if 'parameter' in e.lower()]
            structure_errors = [e for e in errors if e not in processor_errors + connection_errors + parameter_errors]
            
            if processor_errors:
                raise ProcessorValidationError(f"Processor validation failed: {'; '.join(processor_errors)}")
            elif connection_errors:
                raise TemplateValidationError(f"Connection validation failed: {'; '.join(connection_errors)}")
            elif parameter_errors:
                raise ParameterSubstitutionError(f"Parameter validation failed: {'; '.join(parameter_errors)}")
            else:
                raise TemplateValidationError(f"Template validation failed: {'; '.join(structure_errors)}")