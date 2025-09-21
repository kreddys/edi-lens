# NiFi Flow Configurations

This directory contains YAML-based flow configurations for NiFi workflows.

## Available Flows

### `edi-validation-flow.yaml`
Complete EDI validation workflow with proper positioning and relationships:
- **GetFile** - Reads EDI files from `/tmp/nifi-test-data/`
- **EDI Validation Processor** - Validates against 837.5010.X222.A1.json schema
- **LogMessage** processors - Log success/failure results
- **PutFile** processors - Output JSON results to success/failure directories

## Usage

### Create a Flow
```bash
# Create flow with cleanup of existing processors
python3 scripts/nifi-automation/nifi_flow_manager.py create --config scripts/nifi-automation/flows/edi-validation-flow.yaml

# Create flow without cleanup (add to existing)
python3 scripts/nifi-automation/nifi_flow_manager.py create --config scripts/nifi-automation/flows/edi-validation-flow.yaml --no-cleanup

# Create and auto-start processors
python3 scripts/nifi-automation/nifi_flow_manager.py create --config scripts/nifi-automation/flows/edi-validation-flow.yaml --start
```

### Delete/Cleanup Flows
```bash
# Delete all processors and connections
python3 scripts/nifi-automation/nifi_flow_manager.py cleanup

# Delete specific flow by name
python3 scripts/nifi-automation/nifi_flow_manager.py delete --flow-name "EDI Validation"
```

## YAML Configuration Format

```yaml
flow:
  name: "Flow Name"
  description: "Flow description"
  
  processors:
    - id: "unique_id"           # Internal reference ID
      name: "Display Name"      # Name shown in NiFi UI
      type: "ProcessorType"     # NiFi processor class
      position:
        x: 100                  # X coordinate in UI
        y: 200                  # Y coordinate in UI
      properties:
        "Property Name": "value"
      auto_terminated_relationships:
        - "relationship_name"
  
  connections:
    - id: "connection_id"
      source: "source_processor_id"
      destination: "dest_processor_id"
      relationships:
        - "success"
  
  settings:
    auto_start: false           # Auto-start after creation
    cleanup_on_error: true     # Cleanup if creation fails
```

## Processor Types

### Standard NiFi Processors
- `org.apache.nifi.processors.standard.GetFile`
- `org.apache.nifi.processors.standard.PutFile`
- `org.apache.nifi.processors.standard.LogMessage`

### Custom EDI Processors
- `EDIValidationProcessor` - EDI validation against schemas
- `EDIParsingProcessor` - Parse EDI to JSON/XML/CSV
- `TA1GenerationProcessor` - Generate TA1 acknowledgments

## Best Practices

1. **Positioning**: Use consistent spacing (350px horizontal, 100px vertical)
2. **Naming**: Use descriptive names that indicate purpose
3. **Relationships**: Always auto-terminate unused relationships
4. **Properties**: Use expression language where appropriate (`${property.name}`)
5. **IDs**: Use descriptive, unique IDs for processors and connections

## Examples

### Simple Linear Flow
```yaml
processors:
  - id: "input"
    name: "Input Processor"
    # ... config
  - id: "process"
    name: "Processing"
    # ... config
  - id: "output"
    name: "Output"
    # ... config

connections:
  - source: "input"
    destination: "process"
    relationships: ["success"]
  - source: "process"
    destination: "output"
    relationships: ["success"]
```

### Branching Flow
```yaml
processors:
  - id: "input"
    # ... config
  - id: "success_path"
    # ... config
  - id: "failure_path"
    # ... config

connections:
  - source: "input"
    destination: "success_path"
    relationships: ["success"]
  - source: "input"
    destination: "failure_path"
    relationships: ["failure"]
```