# 04 - Testing Strategy

*Comprehensive testing approach for validating NiFi Python processor migration with confidence and reliability*

## 🎯 **Testing Objectives**

### **Primary Goals**
- **Functional Equivalence**: Ensure native processors produce identical results to backend APIs
- **Performance Validation**: Verify performance improvements meet expectations
- **Reliability Assurance**: Confirm error handling and edge cases work correctly
- **Integration Verification**: Validate processor interactions and data flow

### **Quality Gates**
- **Unit Test Coverage**: 90%+ for all processor code
- **Integration Test Coverage**: 100% of processor combinations
- **Performance Improvement**: 50%+ reduction in processing time
- **Error Rate**: ≤ 0.1% for production workloads

## 📋 **Testing Framework Overview**

### **Testing Pyramid Structure**

```
                    🔺 E2E Tests
                   Production Workflows
                  Load & Stress Testing
                 ═══════════════════════
                🔸 Integration Tests
               Processor Interactions
              Cross-System Validation
             ═══════════════════════════
            🔹 Unit Tests
           Individual Processor Logic
          Shared Module Functionality
         ═══════════════════════════════
```

### **Test Categories**

| Category | Scope | Tools | Frequency |
|----------|-------|-------|-----------|
| **Unit Tests** | Individual processors/modules | pytest, unittest | Every commit |
| **Integration Tests** | Processor interactions | NiFi Test Framework | Every PR |
| **Performance Tests** | Throughput & latency | JMeter, custom scripts | Weekly |
| **Load Tests** | Production simulation | NiFi load testing | Release |
| **Comparison Tests** | API vs Native results | Custom validation | Continuous |

## 🧪 **Phase 1 Testing: EDI Validation Processor**

### **Unit Testing Strategy**

#### **Test Structure**
```python
# tests/unit/test_edi_validation_processor.py
class TestEDIValidationProcessor:
    def setup_method(self):
        self.processor = EDIValidationProcessor()
        self.test_schemas = load_test_schemas()
        self.sample_edi_files = load_sample_edi_files()
    
    def test_valid_edi_validation(self):
        """Test validation of valid EDI documents"""
        
    def test_invalid_edi_validation(self):
        """Test validation of invalid EDI documents"""
        
    def test_schema_not_found_error(self):
        """Test handling of missing schema files"""
        
    def test_tenant_isolation(self):
        """Test tenant-specific schema access"""
```

#### **Test Cases**

**1. Valid EDI Document Testing**
```python
@pytest.mark.parametrize("schema,edi_file,expected_valid", [
    ("270.5010.X279.A1.json", "valid_270_eligibility.edi", True),
    ("271.5010.X279.A1.json", "valid_271_response.edi", True),
    ("837.5010.X222.A1.json", "valid_837_claims.edi", True),
])
def test_valid_documents(schema, edi_file, expected_valid):
    result = processor.validate_edi(
        edi_content=load_test_file(edi_file),
        schema_name=schema,
        tenant_id="test-tenant",
        snip_level=3
    )
    assert result.valid == expected_valid
    assert len(result.findings) == 0
```

**2. Invalid EDI Document Testing**
```python
@pytest.mark.parametrize("edi_file,expected_error_count", [
    ("invalid_missing_segments.edi", 3),
    ("invalid_wrong_format.edi", 1),
    ("invalid_element_count.edi", 5),
])
def test_invalid_documents(edi_file, expected_error_count):
    result = processor.validate_edi(
        edi_content=load_test_file(edi_file),
        schema_name="270.5010.X279.A1.json",
        tenant_id="test-tenant",
        snip_level=3
    )
    assert result.valid == False
    assert len(result.findings) == expected_error_count
```

**3. Edge Case Testing**
```python
def test_empty_edi_content():
    """Test handling of empty EDI content"""
    
def test_malformed_edi_content():
    """Test handling of completely malformed content"""
    
def test_large_edi_document():
    """Test handling of very large EDI documents"""
    
def test_unicode_characters():
    """Test handling of unicode characters in EDI"""
```

### **Integration Testing Strategy**

#### **NiFi Test Framework**
```java
// tests/integration/EDIValidationProcessorTest.java
@ExtendWith(NiFiProcessorTestExtension.class)
class EDIValidationProcessorTest {
    
    @Test
    void testBasicValidation() {
        // Setup test runner
        TestRunner runner = TestRunners.newTestRunner(EDIValidationProcessor.class);
        
        // Configure properties
        runner.setProperty(EDIValidationProcessor.VALIDATION_SCHEMA, "270.5010.X279.A1.json");
        runner.setProperty(EDIValidationProcessor.SNIP_LEVEL, "3");
        runner.setProperty(EDIValidationProcessor.TENANT_ID, "test-tenant");
        
        // Enqueue test data
        runner.enqueue(loadTestEDI("valid_270.edi"));
        
        // Run processor
        runner.run();
        
        // Assert results
        runner.assertAllFlowFilesTransferred(EDIValidationProcessor.REL_SUCCESS, 1);
        
        MockFlowFile result = runner.getFlowFilesForRelationship(EDIValidationProcessor.REL_SUCCESS).get(0);
        result.assertAttributeEquals("edi.validation.valid", "true");
    }
}
```

### **Comparison Testing**

#### **API vs Native Validation**
```python
# tests/comparison/test_validation_equivalence.py
class TestValidationEquivalence:
    def setup_method(self):
        self.api_client = EDIValidationAPIClient()
        self.native_processor = EDIValidationProcessor()
    
    @pytest.mark.parametrize("test_file", get_all_test_edi_files())
    def test_api_native_equivalence(self, test_file):
        """Ensure API and native validation produce identical results"""
        edi_content = load_test_file(test_file)
        
        # Get API result
        api_result = self.api_client.validate_edi(
            edi_content=edi_content,
            schema_name="270.5010.X279.A1.json",
            tenant_id="test-tenant",
            snip_level=3
        )
        
        # Get native result
        native_result = self.native_processor.validate_edi(
            edi_content=edi_content,
            schema_name="270.5010.X279.A1.json", 
            tenant_id="test-tenant",
            snip_level=3
        )
        
        # Compare results
        assert api_result.valid == native_result.valid
        assert len(api_result.findings) == len(native_result.findings)
        
        # Compare each finding
        for api_finding, native_finding in zip(api_result.findings, native_result.findings):
            assert api_finding.level == native_finding.level
            assert api_finding.code == native_finding.code
            assert api_finding.message == native_finding.message
```

## 🏷️ **Phase 2 Testing: TA1 Generation Processor**

### **Unit Testing Strategy**

#### **TA1 Generation Test Cases**
```python
# tests/unit/test_ta1_generation_processor.py
class TestTA1GenerationProcessor:
    
    def test_ta1_generation_with_errors(self):
        """Test TA1 generation when validation errors exist"""
        isa_header = create_test_isa_header()
        errors = [create_test_interchange_error()]
        
        ta1_content = self.ta1_generator.generate(isa_header, errors)
        
        assert ta1_content is not None
        assert "TA1*" in ta1_content
        assert ta1_content.startswith("ISA*")
        assert ta1_content.endswith("~")
    
    def test_no_ta1_when_not_requested(self):
        """Test no TA1 generation when ISA14 = 0"""
        isa_header = create_test_isa_header(ack_requested=False)
        errors = []
        
        ta1_content = self.ta1_generator.generate(isa_header, errors)
        
        assert ta1_content is None
    
    def test_ta1_generation_forced(self):
        """Test forced TA1 generation regardless of ISA14"""
        isa_header = create_test_isa_header(ack_requested=False)
        errors = []
        
        ta1_content = self.ta1_generator.generate(isa_header, errors, force_generation=True)
        
        assert ta1_content is not None
```

### **Integration Testing**

#### **Validation → TA1 Flow**
```python
def test_validation_ta1_integrated_flow():
    """Test complete validation to TA1 generation flow"""
    
    # Setup processors
    validation_runner = TestRunners.newTestRunner(EDIValidationProcessor.class)
    ta1_runner = TestRunners.newTestRunner(TA1GenerationProcessor.class)
    
    # Configure validation processor
    validation_runner.setProperty(EDIValidationProcessor.VALIDATION_SCHEMA, "270.5010.X279.A1.json")
    validation_runner.setProperty(EDIValidationProcessor.SNIP_LEVEL, "3")
    
    # Configure TA1 processor
    ta1_runner.setProperty(TA1GenerationProcessor.GENERATE_TA1, "true")
    
    # Run validation with invalid EDI
    validation_runner.enqueue(load_test_file("invalid_270.edi"))
    validation_runner.run()
    
    # Get validation result
    validation_result = validation_runner.getFlowFilesForRelationship(REL_SUCCESS).get(0)
    
    # Pass to TA1 processor
    ta1_runner.enqueue(validation_result)
    ta1_runner.run()
    
    # Verify TA1 generation
    ta1_result = ta1_runner.getFlowFilesForRelationship(REL_TA1).get(0)
    ta1_result.assertAttributeEquals("ta1.generated", "true")
    
    # Verify TA1 content
    ta1_content = new String(ta1_result.toByteArray())
    assert ta1_content.contains("TA1*")
    assert ta1_content.contains("*R*")  # Rejection acknowledgment
```

## 📊 **Phase 3 Testing: EDI Parsing Processor**

### **Output Format Validation**

#### **JSON Output Testing**
```python
def test_json_output_format():
    """Test JSON output format compliance"""
    edi_content = load_test_file("sample_270.edi")
    
    result = parser.parse_edi(
        edi_content=edi_content,
        output_format="JSON",
        include_metadata=True
    )
    
    parsed_result = json.loads(result)
    
    # Validate structure
    assert "segments" in parsed_result
    assert "metadata" in parsed_result
    assert isinstance(parsed_result["segments"], list)
    
    # Validate segment structure
    first_segment = parsed_result["segments"][0]
    assert "segment_id" in first_segment
    assert "elements" in first_segment
    assert "line_number" in first_segment
    
    # Validate metadata
    metadata = parsed_result["metadata"]
    assert "parsed_at" in metadata
    assert "segment_count" in metadata
    assert "interchange_control_number" in metadata
```

#### **XML Output Testing**
```python
def test_xml_output_format():
    """Test XML output format compliance"""
    edi_content = load_test_file("sample_837.edi")
    
    result = parser.parse_edi(
        edi_content=edi_content,
        output_format="XML",
        include_metadata=True
    )
    
    # Parse XML and validate structure
    root = ET.fromstring(result)
    assert root.tag == "edi_document"
    
    # Validate required elements
    assert root.find("metadata") is not None
    assert root.find("segments") is not None
    
    # Validate segment structure
    segments = root.find("segments")
    first_segment = segments.find("segment")
    assert first_segment.get("id") is not None
    assert first_segment.get("line") is not None
```

### **Performance Testing**

#### **Parser Performance Benchmarks**
```python
@pytest.mark.performance
class TestParsingPerformance:
    
    def test_large_file_parsing_performance(self):
        """Test parsing performance with large EDI files"""
        large_edi = create_large_test_edi(segments=10000)
        
        start_time = time.time()
        result = parser.parse_edi(large_edi, output_format="JSON")
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Assert performance requirements
        assert processing_time < 10.0  # Less than 10 seconds
        assert len(result) > 0
    
    @pytest.mark.parametrize("file_size_mb", [1, 5, 10, 25])
    def test_memory_usage_scaling(self, file_size_mb):
        """Test memory usage scales appropriately with file size"""
        test_edi = create_test_edi_of_size(file_size_mb)
        
        memory_before = get_memory_usage()
        result = parser.parse_edi(test_edi, output_format="JSON")
        memory_after = get_memory_usage()
        
        memory_increase = memory_after - memory_before
        
        # Memory usage should be reasonable (< 3x file size)
        assert memory_increase < (file_size_mb * 3 * 1024 * 1024)
```

## 🔄 **Phase 4 Testing: Template Migration**

### **Template Functional Testing**

#### **Native Template Deployment**
```bash
#!/bin/bash
# tests/integration/test_native_template_deployment.sh

# Deploy native template
./deploy-template.sh --template native-realtime-edi-processor --environment test

# Wait for deployment
sleep 30

# Test basic functionality
curl -X POST http://nifi-test:8080/api/workflows/test-workflow-001/process \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -H "X-Tenant-ID: test-tenant" \
  -d @test-data/valid_270.edi

# Verify response
if [ $? -eq 0 ]; then
    echo "✅ Native template deployment successful"
else
    echo "❌ Native template deployment failed"
    exit 1
fi
```

### **Load Testing**

#### **Performance Comparison Tests**
```python
# tests/load/test_template_performance.py
class TestTemplatePerformance:
    
    def test_native_vs_api_throughput(self):
        """Compare throughput between native and API templates"""
        
        # Test API template
        api_results = run_load_test(
            template="realtime-edi-processor",
            duration_seconds=300,
            requests_per_second=50,
            test_data=get_test_edi_files()
        )
        
        # Test native template
        native_results = run_load_test(
            template="native-realtime-edi-processor", 
            duration_seconds=300,
            requests_per_second=50,
            test_data=get_test_edi_files()
        )
        
        # Compare results
        assert native_results.avg_response_time < api_results.avg_response_time
        assert native_results.error_rate <= api_results.error_rate
        assert native_results.throughput >= api_results.throughput
        
        # Performance improvement should be significant
        improvement = (api_results.avg_response_time - native_results.avg_response_time) / api_results.avg_response_time
        assert improvement >= 0.5  # At least 50% improvement
```

## 🚀 **Phase 5 Testing: Production Optimization**

### **Stress Testing**

#### **High Load Scenarios**
```python
@pytest.mark.stress
class TestProductionStress:
    
    def test_sustained_high_load(self):
        """Test processors under sustained high load"""
        
        # Run high load for extended period
        results = run_stress_test(
            template="native-realtime-edi-processor",
            duration_hours=4,
            peak_rps=200,
            test_data_variety=get_production_variety_edi()
        )
        
        # Verify stability
        assert results.error_rate < 0.001  # Less than 0.1% errors
        assert results.memory_leak_detected == False
        assert results.cpu_usage_avg < 80  # Average CPU usage under 80%
    
    def test_concurrent_tenant_processing(self):
        """Test multiple tenants processing simultaneously"""
        
        tenant_results = []
        
        # Start processing for multiple tenants
        for tenant_id in get_test_tenants():
            result = start_concurrent_processing(
                tenant_id=tenant_id,
                template="native-realtime-edi-processor",
                duration_minutes=30,
                rps=25
            )
            tenant_results.append(result)
        
        # Wait for completion
        wait_for_completion(tenant_results)
        
        # Verify tenant isolation
        for result in tenant_results:
            assert result.error_rate < 0.001
            assert result.data_leakage_detected == False
```

### **Chaos Testing**

#### **Failure Resilience**
```python
@pytest.mark.chaos
class TestFailureResilience:
    
    def test_processor_failure_recovery(self):
        """Test recovery from processor failures"""
        
        # Start normal processing
        load_test = start_background_load_test(
            template="native-realtime-edi-processor",
            rps=50
        )
        
        # Introduce processor failure
        simulate_processor_failure(processor_type="EDIValidationProcessor")
        
        # Wait for recovery
        wait_for_recovery(timeout_seconds=60)
        
        # Verify processing resumes
        post_failure_metrics = get_processing_metrics()
        assert post_failure_metrics.processing_resumed == True
        assert post_failure_metrics.data_loss == 0
    
    def test_memory_pressure_handling(self):
        """Test handling of memory pressure scenarios"""
        
        # Create memory pressure
        create_memory_pressure()
        
        # Process large EDI files
        results = process_large_files(
            file_sizes=[50, 100, 200],  # MB
            concurrent_processing=True
        )
        
        # Verify graceful handling
        assert results.out_of_memory_errors == 0
        assert results.processing_completed == True
```

## 📊 **Testing Infrastructure**

### **Test Data Management**

#### **Test File Organization**
```
tests/
├── data/
│   ├── valid/
│   │   ├── 270_eligibility_inquiry.edi
│   │   ├── 271_eligibility_response.edi
│   │   └── 837_professional_claims.edi
│   ├── invalid/
│   │   ├── missing_segments.edi
│   │   ├── wrong_element_count.edi
│   │   └── invalid_format.edi
│   ├── edge_cases/
│   │   ├── empty_file.edi
│   │   ├── unicode_content.edi
│   │   └── very_large_file.edi
│   └── schemas/
│       ├── 270.5010.X279.A1.json
│       ├── 271.5010.X279.A1.json
│       └── 837.5010.X222.A1.json
├── fixtures/
│   ├── test_contexts.py
│   ├── mock_processors.py
│   └── sample_responses.py
└── utils/
    ├── test_helpers.py
    ├── performance_utils.py
    └── data_generators.py
```

### **Continuous Integration Pipeline**

#### **GitHub Actions Workflow**
```yaml
# .github/workflows/nifi-processor-tests.yml
name: NiFi Processor Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r test-requirements.txt
      
      - name: Run unit tests
        run: |
          pytest tests/unit/ --cov=processors --cov=edi_common
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      nifi:
        image: apache/nifi:1.18.0
        ports:
          - 8080:8080
    
    steps:
      - uses: actions/checkout@v3
      - name: Wait for NiFi startup
        run: |
          timeout 300 bash -c 'until curl -f http://localhost:8080/nifi/; do sleep 5; done'
      
      - name: Deploy test processors
        run: |
          ./scripts/deploy-test-processors.sh
      
      - name: Run integration tests
        run: |
          pytest tests/integration/ -v

  performance-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v3
      - name: Run performance benchmarks
        run: |
          ./scripts/run-performance-tests.sh
      
      - name: Upload performance results
        uses: actions/upload-artifact@v3
        with:
          name: performance-results
          path: test-results/performance/
```

### **Test Reporting**

#### **Test Results Dashboard**
```python
# tests/reporting/generate_test_report.py
def generate_comprehensive_test_report():
    """Generate comprehensive test report with metrics"""
    
    report = TestReport()
    
    # Unit test results
    report.add_section("Unit Tests", get_unit_test_results())
    
    # Integration test results
    report.add_section("Integration Tests", get_integration_test_results())
    
    # Performance comparison
    report.add_section("Performance Comparison", compare_api_vs_native_performance())
    
    # Coverage analysis
    report.add_section("Code Coverage", get_coverage_analysis())
    
    # Quality metrics
    report.add_section("Quality Metrics", get_quality_metrics())
    
    # Generate HTML report
    report.save_html("test-results/comprehensive-report.html")
    
    # Generate JSON for CI integration
    report.save_json("test-results/test-metrics.json")
```

---

**Next**: [Implementation Roadmap](./05-implementation-roadmap.md)

**Status**: 🧪 **Testing Strategy Complete** - Ready for implementation planning