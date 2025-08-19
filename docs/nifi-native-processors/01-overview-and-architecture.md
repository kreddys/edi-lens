# 01 - Overview and Architecture

*Comprehensive overview of the NiFi Native Python Processors enhancement for EDI Lens*

## 🎯 **Project Mission**

Transform EDI Lens from a backend API-dependent NiFi workflow system into a self-contained, high-performance platform where EDI processing services run natively within NiFi using Python processors.

## 📋 **Current State Analysis**

### **Current Architecture**
```
┌─────────────────┐    HTTP API    ┌─────────────────┐
│                 │   Calls for    │                 │
│  NiFi Workflows │   EDI Services │  Backend APIs   │
│                 │ ───────────────►│                 │
│ - InvokeHTTP    │                │ - Validation    │
│ - ListenHTTP    │                │ - TA1 Gen       │
│ - RouteOnAttr   │                │ - Parsing       │
└─────────────────┘                └─────────────────┘
```

### **Current EDI Services in Backend**
- **EDI Validation Service** (`backend/src/services/edi_validation_service.py`)
- **TA1 Generation Service** (`backend/src/core/acknowledgements/ta1_generator.py`)
- **EDI Parsing Service** (`backend/src/services/edi_parsing_service.py`)
- **Batch Job Service** (`backend/src/services/batch_job_service.py`)

### **Current Workflow Template Pattern**
```yaml
# Example from realtime-edi-processor.yaml
- id: "validate-edi-realtime-processor"
  type: "InvokeHTTP"
  properties:
    HTTP Method: "POST"
    Remote URL: "http://backend:8000/api/v1/edi/validate-realtime"
    Request Body: |
      {
        "edi_content": "${flowfile:content}",
        "tenant_id": "${tenant.id}",
        "validation_schema": "${VALIDATION_SCHEMA}"
      }
```

## 🏗️ **Target Architecture**

### **Native Python Processor Architecture**
```
┌─────────────────────────────────────────────────────────────┐
│                    NiFi Cluster                            │
│                                                             │
│ ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐ │
│ │ EDI Validation  │  │ TA1 Generation  │  │ EDI Parsing   │ │
│ │ Python          │  │ Python          │  │ Python        │ │
│ │ Processor       │  │ Processor       │  │ Processor     │ │
│ └─────────────────┘  └─────────────────┘  └───────────────┘ │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │              Shared Python Modules                     │ │
│ │ - edi_common.validation_service                         │ │
│ │ - edi_common.ta1_generator                              │ │
│ │ - edi_common.edi_parser                                 │ │
│ │ - edi_common.schema_manager                             │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### **Key Design Principles**

#### **1. Zero Network Dependencies for EDI Processing**
- All EDI validation, parsing, and acknowledgment generation happens within NiFi
- No HTTP calls to backend for core EDI operations
- Backend maintains role for workflow orchestration and UI

#### **2. Code Reuse and Portability**
- Port existing Python EDI logic to NiFi processors with minimal changes
- Maintain shared modules for common functionality
- Preserve existing business logic and validation rules

#### **3. Native NiFi Integration**
- Leverage NiFi's parameter contexts for configuration
- Use FlowFile attributes for data passing between processors
- Support NiFi's relationship-based routing

#### **4. Multi-tenant Support**
- Maintain tenant isolation at processor level
- Support tenant-specific schemas and configurations
- Preserve existing security model

## 📊 **Component Architecture**

### **Core Python Processors**

#### **1. EDI Validation Processor**
```python
class EDIValidationProcessor(FlowFileTransform):
    # Validates EDI content against schemas
    # Outputs validation results as FlowFile attributes
    # Supports configurable SNIP levels
```

#### **2. TA1 Generation Processor**
```python
class TA1GenerationProcessor(FlowFileTransform):
    # Generates TA1 acknowledgments
    # Routes original/TA1 content to separate outputs
    # Supports conditional generation based on errors
```

#### **3. EDI Parsing Processor**
```python
class EDIParsingProcessor(FlowFileTransform):
    # Parses EDI into structured formats (JSON/XML/CSV)
    # Extracts metadata and segment information
    # Enables downstream format-agnostic processing
```

### **Shared Module Structure**
```
nifi/edi_common/
├── __init__.py
├── validation_service.py      # Ported from backend
├── ta1_generator.py           # Ported from backend
├── edi_parser.py              # Ported from backend
├── cdm.py                     # Common Data Model
├── schema_manager.py          # Schema loading/caching
└── schemas.py                 # Data structures
```

### **Configuration Management**

#### **Schema Distribution**
```
nifi/schemas/
├── 270.5010.X279.A1.json     # Healthcare eligibility
├── 271.5010.X279.A1.json     # Healthcare eligibility response
├── 837.5010.X222.A1.json     # Healthcare claims
└── tenant-specific/
    ├── tenant-a/
    └── tenant-b/
```

#### **Parameter Context Integration**
```yaml
# Workflow parameter context
parameters:
  VALIDATION_SCHEMA: "270.5010.X279.A1.json"
  SNIP_LEVEL: "3"
  GENERATE_TA1: "true"
  SCHEMA_BASE_PATH: "/opt/nifi/schemas"
```

## 🔄 **Data Flow Architecture**

### **Native Processor Flow**
```
HTTP Request → Extract Tenant → Validate EDI → Generate TA1 → Format Response
    ↓              ↓              ↓              ↓              ↓
ListenHTTP → UpdateAttribute → EDIValidation → TA1Generator → ReplaceText
                               (Python)        (Python)
```

### **FlowFile Attribute Flow**
```yaml
Input Attributes:
  - tenant.id: "tenant-a"
  - http.headers.Authorization: "Bearer ..."

Processing Attributes:
  - edi.validation.valid: "true"
  - edi.validation.findings.count: "0"
  - ta1.generated: "true"
  - ta1.content: "ISA*..."

Output Attributes:
  - processing.completed.at: "2024-01-15T10:30:00Z"
  - response.type: "success"
```

## 🚀 **Performance Benefits**

### **Eliminated Overheads**
- **HTTP Request/Response**: ~50-100ms per API call
- **JSON Serialization**: ~10-20ms for large payloads
- **Network Latency**: ~5-15ms per request
- **Connection Pooling**: Resource contention eliminated

### **Enhanced Capabilities**
- **Native Clustering**: Automatic load distribution across NiFi nodes
- **Memory Efficiency**: Direct FlowFile processing without HTTP buffering
- **Error Handling**: Native NiFi retry and error routing
- **Monitoring**: Built-in NiFi metrics and logging

## 🔒 **Security Considerations**

### **Maintained Security Model**
- Tenant isolation through processor configuration
- Authentication handled at NiFi listener level
- Schema access controlled by tenant ID
- Audit logging through NiFi provenance

### **Enhanced Security**
- No sensitive data in HTTP requests
- Reduced attack surface (no exposed backend APIs)
- Direct access control at processor level

## 📈 **Scalability Improvements**

### **Horizontal Scaling**
- Processors scale with NiFi cluster nodes
- No backend bottlenecks for EDI processing
- Independent scaling of different EDI operations

### **Vertical Scaling**
- Direct memory access to EDI data
- Reduced CPU overhead from HTTP processing
- Optimized JVM memory usage

## 🔧 **Development Benefits**

### **Simplified Architecture**
- Single codebase for EDI logic
- Reduced complexity in workflow templates
- Easier debugging and troubleshooting

### **Enhanced Flexibility**
- Mix and match EDI processors in workflows
- Custom processor combinations for specific use cases
- Rapid prototyping of new EDI services

---

**Next**: [Processor Specifications](./02-processor-specifications.md)

**Status**: 📋 **Architecture Defined** - Ready for detailed processor design