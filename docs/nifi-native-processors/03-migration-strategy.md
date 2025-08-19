# 03 - Migration Strategy

*Incremental, risk-minimized approach to migrating from backend API calls to native NiFi Python processors*

## 🎯 **Migration Objectives**

### **Primary Goals**
- **Zero Downtime**: Maintain production functionality throughout migration
- **Incremental Progress**: Deliver value in small, testable increments
- **Rollback Capability**: Enable quick reversion at any migration stage
- **Performance Validation**: Measure improvements at each phase

### **Success Criteria**
- All existing workflows continue to function
- Performance improvements are measurable
- Code quality and test coverage are maintained
- Documentation reflects current state

## 📋 **Migration Phases Overview**

| Phase | Duration | Focus | Deliverable | Risk Level |
|-------|----------|-------|-------------|------------|
| **Phase 1** | 2 weeks | Shared modules + basic processor | Functional EDI validation processor | 🟢 Low |
| **Phase 2** | 1 week | TA1 processor + integration | Complete TA1 generation workflow | 🟡 Medium |
| **Phase 3** | 1 week | EDI parsing processor | Full parsing capabilities | 🟡 Medium |
| **Phase 4** | 1 week | Template migration | Native processor templates | 🟠 High |
| **Phase 5** | 1 week | Performance optimization | Production-ready optimization | 🟢 Low |

## 🔄 **Phase 1: Foundation & EDI Validation**

### **Objectives**
- Create shared Python module infrastructure
- Implement and test EDI validation processor
- Establish dual-path validation (API + native)

### **Deliverables**

#### **1.1 Shared Module Creation**
```bash
# Create module structure
mkdir -p nifi-edi-processors/edi_common
cd nifi-edi-processors
```

**Tasks:**
- [ ] Port `backend/src/services/edi_validation_service.py` to `edi_common/validation_service.py`
- [ ] Port `backend/src/core/schema_manager.py` to `edi_common/schema_manager.py`
- [ ] Port `backend/src/api/schemas.py` validation classes to `edi_common/schemas.py`
- [ ] Create `edi_common/__init__.py` with proper imports
- [ ] Create unit tests for ported modules

#### **1.2 EDI Validation Processor Implementation**
```python
# processors/edi_validation_processor.py
class EDIValidationProcessor(FlowFileTransform):
    # Implementation as per specifications
```

**Tasks:**
- [ ] Implement processor class with all required properties
- [ ] Add comprehensive error handling
- [ ] Create processor unit tests
- [ ] Package processor as NAR file

#### **1.3 Dual-Path Testing Infrastructure**
```yaml
# test-workflows/dual-validation-test.yaml
# Workflow that runs both API and native validation for comparison
```

**Tasks:**
- [ ] Create test workflow template with both validation paths
- [ ] Implement result comparison logic
- [ ] Create automated test suite
- [ ] Document validation differences (if any)

### **Testing Strategy**
```bash
# Phase 1 Testing Commands
./test-native-validation.sh --schema 270.5010.X279.A1.json --input sample-edi.txt
./compare-validation-results.sh --native-result native.json --api-result api.json
```

### **Success Criteria**
- [ ] Native validation produces identical results to API validation
- [ ] Performance metrics show improvement (baseline: API response time)
- [ ] All unit tests pass
- [ ] Documentation is complete

### **Rollback Plan**
- Remove native processor from workflow templates
- Continue using API-based validation
- Archive processor code for future iteration

## 🏷️ **Phase 2: TA1 Generation Integration**

### **Objectives**
- Implement TA1 generation processor
- Create integrated validation → TA1 workflow
- Maintain backward compatibility

### **Deliverables**

#### **2.1 TA1 Module Porting**
**Tasks:**
- [ ] Port `backend/src/core/acknowledgements/ta1_generator.py` to `edi_common/ta1_generator.py`
- [ ] Port `backend/src/core/acknowledgements/ta1_defs.py` to `edi_common/ta1_defs.py`
- [ ] Port `backend/src/core/cdm.py` to `edi_common/cdm.py`
- [ ] Create comprehensive unit tests

#### **2.2 TA1 Processor Implementation**
**Tasks:**
- [ ] Implement TA1GenerationProcessor class
- [ ] Add validation error → TA1 error mapping
- [ ] Create processor integration tests
- [ ] Update NAR package

#### **2.3 Integrated Workflow Template**
```yaml
# templates/native-validation-ta1-workflow.yaml
processors:
  - EDIValidationProcessor
  - TA1GenerationProcessor
connections:
  - validation.success → ta1.input
```

**Tasks:**
- [ ] Create integrated workflow template
- [ ] Implement FlowFile attribute passing
- [ ] Test complete validation → TA1 flow
- [ ] Compare with existing API-based workflow

### **Testing Strategy**
```bash
# Phase 2 Testing Commands
./test-validation-ta1-flow.sh --input invalid-edi.txt --expect-ta1-rejection
./test-validation-ta1-flow.sh --input valid-edi.txt --expect-ta1-acceptance
./compare-ta1-results.sh --native ta1-native.edi --api ta1-api.edi
```

### **Success Criteria**
- [ ] TA1 generation produces identical results to API service
- [ ] Integrated workflow handles all error scenarios
- [ ] Performance shows 50%+ improvement over API calls
- [ ] Zero data loss in attribute passing

### **Rollback Plan**
- Revert to Phase 1 configuration
- Disable TA1 processor in templates
- Continue using API for TA1 generation

## 📊 **Phase 3: EDI Parsing Processor**

### **Objectives**
- Complete EDI processing trifecta with parsing processor
- Support multiple output formats
- Enable format-agnostic downstream processing

### **Deliverables**

#### **3.1 Parser Module Porting**
**Tasks:**
- [ ] Port `backend/src/core/edi_parser.py` to `edi_common/edi_parser.py`
- [ ] Port `backend/src/services/edi_parsing_service.py` to `edi_common/parsing_service.py`
- [ ] Add support for XML and CSV output formats
- [ ] Create format conversion tests

#### **3.2 EDI Parsing Processor Implementation**
**Tasks:**
- [ ] Implement EDIParsingProcessor class
- [ ] Add configurable output format support
- [ ] Implement segment filtering capability
- [ ] Create comprehensive test suite

#### **3.3 Multi-Format Output Testing**
**Tasks:**
- [ ] Test JSON output format compliance
- [ ] Test XML output format compliance  
- [ ] Test CSV output format compliance
- [ ] Validate metadata extraction accuracy

### **Testing Strategy**
```bash
# Phase 3 Testing Commands
./test-edi-parsing.sh --format JSON --input healthcare-270.edi
./test-edi-parsing.sh --format XML --filter "ISA,GS,ST" --input claims-837.edi
./validate-parsing-accuracy.sh --compare-with-api
```

### **Success Criteria**
- [ ] Parsing accuracy matches API service (100%)
- [ ] All output formats are valid and complete
- [ ] Performance improvement over API calls
- [ ] Memory usage is within acceptable limits

### **Rollback Plan**
- Remove parsing processor from workflows
- Revert to API-based parsing
- Maintain Phase 2 capabilities

## 🔄 **Phase 4: Template Migration**

### **Objectives**
- Migrate existing workflow templates to use native processors
- Maintain API fallback capability
- Enable gradual production rollout

### **Deliverables**

#### **4.1 Template Analysis & Planning**
**Tasks:**
- [ ] Audit all existing workflow templates using backend APIs
- [ ] Identify templates for migration priority
- [ ] Create migration mapping document
- [ ] Plan dual-template strategy

#### **4.2 Native Template Creation**
**Templates to Migrate:**
- `realtime-edi-processor.yaml` → `native-realtime-edi-processor.yaml`
- `batch-edi-processor.yaml` → `native-batch-edi-processor.yaml`

**Tasks:**
- [ ] Create native versions of all templates
- [ ] Update configuration schemas
- [ ] Maintain parameter compatibility
- [ ] Test template deployment

#### **4.3 Gradual Rollout Strategy**
```yaml
# Rollout Configuration
rollout_strategy:
  phase_4a: 
    templates: ["native-realtime-edi-processor"]
    traffic_percentage: 10%
    monitoring_period: 24_hours
  
  phase_4b:
    templates: ["native-realtime-edi-processor", "native-batch-edi-processor"]
    traffic_percentage: 50%
    monitoring_period: 48_hours
    
  phase_4c:
    templates: ["all_native_templates"]
    traffic_percentage: 100%
    monitoring_period: 72_hours
```

**Tasks:**
- [ ] Implement feature flag system for template selection
- [ ] Create monitoring dashboard for native vs API performance
- [ ] Establish rollback procedures
- [ ] Document operational runbooks

### **Testing Strategy**
```bash
# Phase 4 Testing Commands
./deploy-native-template.sh --template native-realtime-edi-processor --environment staging
./run-load-test.sh --template native-realtime-edi-processor --duration 1h --rps 100
./compare-template-performance.sh --native native-realtime --api realtime-edi-processor
```

### **Success Criteria**
- [ ] All native templates deploy successfully
- [ ] Performance metrics exceed API-based templates
- [ ] Error rates remain at or below baseline
- [ ] User experience is unchanged

### **Rollback Plan**
- Revert template deployments to API-based versions
- Maintain native processors for future use
- Document lessons learned

## 🚀 **Phase 5: Production Optimization**

### **Objectives**
- Optimize performance and resource usage
- Implement production monitoring
- Remove API dependencies
- Complete documentation

### **Deliverables**

#### **5.1 Performance Optimization**
**Tasks:**
- [ ] Profile processor memory usage
- [ ] Optimize schema loading and caching
- [ ] Implement connection pooling where applicable
- [ ] Tune JVM parameters for Python processors

#### **5.2 Monitoring & Observability**
**Tasks:**
- [ ] Implement custom metrics for processors
- [ ] Create Grafana dashboards for native processor performance
- [ ] Set up alerting for processor failures
- [ ] Document operational procedures

#### **5.3 API Dependency Removal**
**Tasks:**
- [ ] Remove unused API endpoints from backend
- [ ] Update documentation to reflect native processing
- [ ] Archive old workflow templates
- [ ] Clean up unused backend service code

#### **5.4 Documentation & Training**
**Tasks:**
- [ ] Update user documentation
- [ ] Create operational runbooks
- [ ] Conduct team training sessions
- [ ] Document lessons learned

### **Testing Strategy**
```bash
# Phase 5 Testing Commands
./run-performance-benchmark.sh --duration 4h --load production-level
./validate-monitoring.sh --check-metrics --check-alerts
./test-disaster-recovery.sh --simulate-processor-failure
```

### **Success Criteria**
- [ ] 99.9% uptime achieved
- [ ] Performance improvements documented and verified
- [ ] Team training completed
- [ ] All documentation updated

### **Completion Checklist**
- [ ] All backend API dependencies removed
- [ ] Production monitoring operational
- [ ] Performance benchmarks documented
- [ ] Migration retrospective completed

## 📊 **Risk Management**

### **Risk Mitigation Strategies**

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Performance Regression** | Medium | High | Dual-path testing, gradual rollout |
| **Data Corruption** | Low | Critical | Comprehensive testing, rollback capability |
| **Integration Issues** | Medium | Medium | Phase-by-phase validation |
| **Resource Constraints** | Low | Medium | Performance monitoring, capacity planning |

### **Monitoring & Alerts**
```yaml
# Key Metrics to Monitor
metrics:
  - processor_execution_time
  - processor_error_rate
  - memory_usage_per_processor
  - flowfile_processing_rate
  - schema_cache_hit_ratio

alerts:
  - processor_error_rate > 1%
  - processor_execution_time > baseline + 20%
  - memory_usage > 80% of allocated
```

## 🔧 **Development Workflow**

### **Branch Strategy**
```bash
# Branch naming convention
feature/phase-1-validation-processor
feature/phase-2-ta1-processor  
feature/phase-3-parsing-processor
feature/phase-4-template-migration
feature/phase-5-optimization
```

### **Testing Requirements**
- Unit tests: 90%+ coverage
- Integration tests: All processor combinations
- Performance tests: Baseline + 20% improvement target
- Load tests: Production-level traffic simulation

### **Review Process**
1. **Code Review**: 2 reviewers required
2. **Architecture Review**: For each phase
3. **Performance Review**: Benchmark validation
4. **Security Review**: Access control and data handling

---

**Next**: [Testing Strategy](./04-testing-strategy.md)

**Status**: 🔄 **Migration Plan Complete** - Ready for detailed testing strategy