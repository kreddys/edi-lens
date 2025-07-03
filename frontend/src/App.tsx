import { useState, useEffect, useCallback, useRef, ChangeEvent, useMemo } from 'react';
import CombinedEdiView from './components/CombinedEdiView'; // Make sure path is correct
import StructuredEdiView from './components/StructuredEdiView'; // Make sure path is correct
import LogConsole from './components/LogConsole'; // Make sure path is correct
import { parseEdi } from './ediParser/ediParser';
import { ParseEdiResult, EdiSegment } from './ediParser/ediTypes';
import { ProcessedTransactionSchema } from './ediSchema/schemaTypes';
import { AppLogger, AppLogLevel } from './logger';
import { buildHierarchicalData, HierarchicalEdiNode } from './ediUtils/structureBuilder';

// Import Sample Files
import sample837P_0001 from './samples/837p.test.0001.edi?raw';
import sample837P_0002 from './samples/837p.test.0002.edi?raw';
import sample837P_Wrapped from './samples/837p.test.wrapped.edi?raw';
import sample837I from './samples/837I.test.0001.edi?raw';
import sample835 from './samples/835.test.0001.edi?raw';
import sample277CA from './samples/277CA.test.0001.edi?raw';
// Add more sample imports

type SchemaModule = { default: ProcessedTransactionSchema };
const schemaModules = import.meta.glob('/src/schemas/json/*.json', { eager: false }) as Record<string, () => Promise<SchemaModule>>;

interface DynamicSchemaInfo {
  key: string; // e.g., "837P.5010.X222.A1"
  name: string;
  version: string;
  filePath: string;
  load: () => Promise<SchemaModule>;
}

// Modified SampleFileInfo Interface
export interface SampleFileInfo {
  key: string; // Unique identifier for the sample itself
  name: string; // User-friendly display name
  content: string; // The raw EDI content
  schemaKey: string; // <<< NEW: Key of the schema this sample corresponds to
}

// Helper to format segments
const formatEdiSegments = (segments: EdiSegment[], segmentDelimiter: string): string => {
  if (!segments || segments.length === 0) return '';
  const ediString = segments.map(seg => seg.rawSegmentString.trim()).join(segmentDelimiter === '\n' ? '\n' : segmentDelimiter + '\n');
  const endsWithDelimiter = segments[segments.length - 1]?.rawSegmentString.trim().endsWith(segmentDelimiter);
  return endsWithDelimiter || segmentDelimiter === '\n' ? ediString : ediString + segmentDelimiter;
};

function App() {
  const [rawEdi, setRawEdi] = useState<string>('');
  const [formattedEdiDisplay, setFormattedEdiDisplay] = useState<string>('');
  const [isInputMode, setIsInputMode] = useState<boolean>(true);
  const [parsedResult, setParsedResult] = useState<ParseEdiResult>({ data: null, error: null });
  const [schema, setSchema] = useState<ProcessedTransactionSchema | null>(null);
  const [isSchemaLoading, setIsSchemaLoading] = useState<boolean>(false); // Start false
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [hierarchicalNodes, setHierarchicalNodes] = useState<HierarchicalEdiNode[]>([]);
  const [logMessages, setLogMessages] = useState<string[]>([]);
  const [isLogConsoleOpen, setIsLogConsoleOpen] = useState<boolean>(false);
  const [activeStructuredView, setActiveStructuredView] = useState<'data' | 'schema'>('data');
  const [selectedSchemaKey, setSelectedSchemaKey] = useState<string>('');
  const debounceTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Derived State
  const isBusy = isSchemaLoading || isProcessing;

  // Samples Memo
  const availableSamples = useMemo<SampleFileInfo[]>(() => [
    { key: '837p-1', name: '837P Multiple Subscribers', content: sample837P_0001, schemaKey: '837.5010.X222.A1' },
    { key: '837p-2', name: '837P Multiple Transactions', content: sample837P_0002, schemaKey: '837.5010.X222.A1' },
    { key: '837p-3', name: '837P Wrapped', content: sample837P_Wrapped, schemaKey: '837.5010.X222.A1' },
    { key: '837i-1', name: '837I Sample', content: sample837I, schemaKey: '837.5010.X223.A1.v2' },
    { key: '835', name: '835 Sample', content: sample835, schemaKey: '835.5010.X221.A1.v2' },
    { key: '277ca', name: '277CA Sample', content: sample277CA, schemaKey: '277.5010.X214' },
  ], []);

  // Logging Callback
  const appLogger: AppLogger = useCallback((message: string, level: AppLogLevel = 'log') => {
    const timestamp = new Date().toLocaleTimeString();
    const levelIndicator = level.toUpperCase();
    const formattedMessage = `[${timestamp}] [${levelIndicator}] ${message}`;

    switch (level) {
      case 'warn': console.warn(formattedMessage); break;
      case 'error': console.error(formattedMessage); break;
      case 'debug': console.debug(formattedMessage); break;
      case 'info': console.info(formattedMessage); break;
      default: console.log(formattedMessage); break;
    }

    if (isLogConsoleOpen) {
      setLogMessages(prev => [...prev, formattedMessage].slice(-1000));
    } else {
      if (level === 'error' || level === 'warn') {
        setLogMessages(prev => [...prev, formattedMessage].slice(-50));
      }
    }
  }, [isLogConsoleOpen]); // Stable dependency

  // Available Schemas Memo
  const availableSchemas: DynamicSchemaInfo[] = useMemo(() => {
    const schemas: DynamicSchemaInfo[] = [];
    for (const path in schemaModules) {
      const match = path.match(/\/([^\/]+)\.json$/);
      const filename = match ? match[1] : '';
      if (!filename) {
        console.warn(`Could not extract filename from path: ${path}`);
        continue;
      }
      const nameParts = filename.split('.');
      let version = 'N/A';
      let name = filename;
      let baseKey = filename;

      if (nameParts.length > 1) {
        baseKey = nameParts[0];
        version = nameParts.slice(1).join('.');
        if (baseKey.startsWith('837')) name = `${baseKey} Claim`;
        else if (baseKey.startsWith('835')) name = `${baseKey} Remittance`;
        else if (baseKey.startsWith('277')) name = `${baseKey} Acknowledgment`;
        else if (baseKey.startsWith('270')) name = `${baseKey} Eligibility Request`;
        else if (baseKey.startsWith('271')) name = `${baseKey} Eligibility Response`;
        else name = `${baseKey} Transaction`;
      } else {
        if (baseKey.startsWith('837')) name = `${baseKey} Claim`;
        else if (baseKey.startsWith('835')) name = `${baseKey} Remittance`;
        else name = `${baseKey} Transaction`;
      }
      schemas.push({ key: filename, name, version, filePath: path, load: schemaModules[path] });
    }
    schemas.sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version));
    if (schemas.length === 0) {
      appLogger("No JSON schemas found in /src/schemas/json/", 'warn');
    }
    return schemas;
  }, [appLogger]); // Stable dependency

  // Function to load a specific schema
  const loadSpecificSchema = useCallback(async (key: string) => {
    const schemaInfo = availableSchemas.find(s => s.key === key);
    if (!schemaInfo) {
      appLogger(`Schema with key "${key}" not found.`, 'error');
      setSchema(null);
      setParsedResult(prev => ({ ...prev, error: `Schema "${key}" not found.` }));
      return;
    }

    appLogger(`Loading schema: ${schemaInfo.name} (${schemaInfo.version})...`, 'info');
    setIsSchemaLoading(true); // Set loading TRUE

    // Clear previous state
    if (debounceTimeoutRef.current) { clearTimeout(debounceTimeoutRef.current); }
    setRawEdi('');
    setFormattedEdiDisplay('');
    setParsedResult({ data: null, error: null });
    setHierarchicalNodes([]);
    setIsInputMode(true);
    setSchema(null); // Clear schema during load
    setActiveStructuredView('data');
    if (fileInputRef.current) { fileInputRef.current.value = ''; }

    try {
      const module = await schemaInfo.load();
      if (module.default?.transactionName && module.default?.segmentDefinitions && module.default?.structure) {
        setSchema(module.default); // Set schema on success
        appLogger(`Schema "${schemaInfo.name}" loaded successfully.`, 'info');
      } else { throw new Error("Invalid schema format."); }
    } catch (error: any) {
      const errorMsg = `Failed to load schema "${schemaInfo.name}" (${key}): ${error?.message || error}`;
      appLogger(errorMsg, 'error');
      setSchema(null); // Ensure schema is null on error
      setParsedResult({ data: null, error: errorMsg });
    } finally {
      setIsSchemaLoading(false); // Set loading FALSE
      appLogger(`Schema loading finished for key "${key}".`, 'debug');
    }
  }, [appLogger, availableSchemas]); // Stable dependencies

  // Effect to load schema when selection changes
  useEffect(() => {
    if (selectedSchemaKey) {
      loadSpecificSchema(selectedSchemaKey);
    }
  }, [selectedSchemaKey, loadSpecificSchema]); // loadSpecificSchema is memoized

  // --- Parsing & Building ---
  // Use a ref to track if processing is ongoing to avoid dependency cycle
  const isProcessingRef = useRef(false);
  const triggerParseAndBuild = useCallback((ediTextToParse: string) => {
    // Check ref *before* starting
    if (isProcessingRef.current) {
      appLogger("Processing already in progress, skipping.", 'warn');
      return;
    }
    if (!schema) {
      appLogger("Cannot parse: Schema not loaded.", 'error');
      setParsedResult({ data: null, error: "Cannot parse: Schema not loaded." });
      return;
    }

    // Set flag and state
    isProcessingRef.current = true;
    setIsProcessing(true);
    setParsedResult({ data: null, error: null });
    setHierarchicalNodes([]);
    setFormattedEdiDisplay('');

    const operationLogsBuffer: string[] = [];
    const collectingLogger: AppLogger = (message, level = 'log') => {
      const timestamp = new Date().toLocaleTimeString();
      const levelIndicator = level.toUpperCase();
      const formattedMessage = `[${timestamp}] [${levelIndicator}] ${message}`;
      operationLogsBuffer.push(formattedMessage);
      // Minimal console logging here
      if (level === 'error') console.error(formattedMessage);
      else if (level === 'warn') console.warn(formattedMessage);
    };

    setTimeout(() => {
      const localSchema = schema; // Capture schema for async use
      try {
        if (!localSchema) { throw new Error("Schema became null unexpectedly."); }

        collectingLogger("Starting EDI processing pipeline (async step)", 'info');
        collectingLogger("Phase 1: Parsing raw EDI content", 'info');
        const parseStart = performance.now();
        const localParseResult = parseEdi(ediTextToParse, collectingLogger); // Use collectingLogger
        const parseTime = performance.now() - parseStart;
        collectingLogger(`Parsing completed in ${parseTime.toFixed(2)}ms`, 'debug');

        let nodes: HierarchicalEdiNode[] = [];
        let formattedString = '';

        if (localParseResult.data) {
          collectingLogger("Phase 2: Building hierarchical structure", 'info');
          const buildStart = performance.now();
          nodes = buildHierarchicalData(localParseResult.data, localSchema, collectingLogger); // Use collectingLogger
          const buildTime = performance.now() - buildStart;
          collectingLogger(`Structure built in ${buildTime.toFixed(2)}ms`, 'debug');

          formattedString = formatEdiSegments(localParseResult.data.segments, localParseResult.data.delimiters.segment);
          collectingLogger("Phase 3: Formatting EDI display string", 'info');
        } else {
          collectingLogger("Skipping structure build: No data from parsing.", 'warn');
        }

        // Update state AFTER async work
        setParsedResult(localParseResult);
        setHierarchicalNodes(nodes);
        if (localParseResult.data) {
          setFormattedEdiDisplay(formattedString);
          setIsInputMode(false);
          appLogger("Successfully parsed and formatted EDI.", 'info'); // Log success via main logger
        } else {
          setFormattedEdiDisplay('');
          setIsInputMode(true);
          appLogger("EDI processing failed.", 'warn'); // Log failure via main logger
        }
      } catch (error: any) {
        const errorMsg = `Unexpected error during processing: ${error?.message || error}`;
        collectingLogger(errorMsg, 'error'); // Log error via collecting logger
        setParsedResult({ data: null, error: errorMsg });
        setHierarchicalNodes([]);
        setFormattedEdiDisplay('');
        setIsInputMode(true);
      } finally {
        setLogMessages(prev => [...prev, ...operationLogsBuffer].slice(-1000)); // Update main log state
        isProcessingRef.current = false; // Reset flag
        setIsProcessing(false); // Reset state
        appLogger("Processing pipeline finished.", 'debug'); // Log finish via main logger
      }
    }, 10);

    // Dependencies: Only things needed to *define* the function, not things it *sets*.
    // schema is needed for the initial check.
    // appLogger is needed to log messages.
    // availableSchemas & selectedSchemaKey are used for logging context only.
  }, [schema, appLogger, selectedSchemaKey, availableSchemas]);

  // Debounced trigger
  const triggerParseAndBuildDebounced = useCallback((ediTextToParse: string) => {
    if (isSchemaLoading) {
      appLogger("Debounce skipped: Schema is loading.", 'debug');
      if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);
      return;
    }
    if (!schema) {
      appLogger("Debounce skipped: Schema not selected/loaded.", 'warn');
      if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);
      // Set error only if one doesn't exist
      setParsedResult(prev => prev.error ? prev : { data: null, error: "Cannot process EDI: Select a schema first." });
      return;
    }

    appLogger("Input detected, debouncing operation (500ms)...", 'debug');
    if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);
    debounceTimeoutRef.current = setTimeout(() => {
      appLogger("Debounce finished, triggering parse & build...", 'debug');
      triggerParseAndBuild(ediTextToParse);
    }, 500);

    // triggerParseAndBuild is stable. isSchemaLoading and schema are needed for checks.
  }, [schema, isSchemaLoading, appLogger, triggerParseAndBuild]);

  // --- Input Handling Callbacks ---
  const handleClearInput = useCallback(() => {
    if (debounceTimeoutRef.current) { clearTimeout(debounceTimeoutRef.current); }
    setRawEdi('');
    setFormattedEdiDisplay('');
    setParsedResult({ data: null, error: null });
    setHierarchicalNodes([]);
    setIsInputMode(true);
    // Stop processing only if it was active
    if (isProcessingRef.current) {
      isProcessingRef.current = false;
      setIsProcessing(false);
    }
    if (fileInputRef.current) { fileInputRef.current.value = ''; }
    appLogger("Input cleared.", 'info');
  }, [appLogger]); // Stable

  const handleCombinedEdiChange = (text: string) => {
    setRawEdi(text);
    setIsInputMode(true);
  };

  const handleSchemaChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const newKey = event.target.value;
    if (newKey === selectedSchemaKey) return;
    setSelectedSchemaKey(newKey); // Triggers useEffect[selectedSchemaKey]
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    const targetInput = event.target;
    if (files && files.length > 0) {
      const file = files[0];
      appLogger(`File selected: ${file.name} (Size: ${file.size} bytes, Type: ${file.type})`, 'info');
      if (file.size > 10 * 1024 * 1024) { appLogger(`Warning: File size large...`, 'warn'); }
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const fileContent = e.target?.result as string;
          if (typeof fileContent !== 'string') throw new Error("Failed to read file content as text.");
          appLogger("File read successfully.", 'info');
          if (debounceTimeoutRef.current) { clearTimeout(debounceTimeoutRef.current); }
          // Reset state *before* setting rawEdi
          setIsInputMode(true);
          setFormattedEdiDisplay('');
          setParsedResult({ data: null, error: null });
          setHierarchicalNodes([]);
          setRawEdi(fileContent); // Triggers effect below
          if (targetInput) { targetInput.value = ''; }
        } catch (readError: any) {
          appLogger(`Error processing file content: ${readError?.message || readError}`, 'error');
          setParsedResult({ data: null, error: `Error reading file: ${readError?.message || 'Unknown error'}` });
          if (targetInput) { targetInput.value = ''; }
        }
      };
      reader.onerror = (_e) => {
        appLogger(`Error reading file ${file.name}: ${reader.error}`, 'error');
        setParsedResult({ data: null, error: `Error reading file: ${reader.error?.message || 'Unknown error'}` });
        if (targetInput) { targetInput.value = ''; }
      };
      reader.readAsText(file);
    } else {
      if (targetInput) { targetInput.value = ''; }
    }
  };

  const handleLoadSample = useCallback((sampleKey: string) => {
    const selectedSample = availableSamples.find(s => s.key === sampleKey);
    if (selectedSample) {
      appLogger(`Loading sample file: ${selectedSample.name}`, 'info');
      if (debounceTimeoutRef.current) { clearTimeout(debounceTimeoutRef.current); }
      // Reset state *before* setting rawEdi
      setIsInputMode(true);
      setFormattedEdiDisplay('');
      setParsedResult({ data: null, error: null });
      setHierarchicalNodes([]);
      setRawEdi(selectedSample.content); // Triggers effect below
    } else {
      appLogger(`Sample with key "${sampleKey}" not found.`, 'warn');
    }
  }, [availableSamples, appLogger]); // Stable

  // --- Effect for triggering parse on input change ---
  useEffect(() => {
    const cleanup = () => { if (debounceTimeoutRef.current) { clearTimeout(debounceTimeoutRef.current); } };

    if (rawEdi.trim()) {
      if (schema && !isSchemaLoading) {
        // Schema ready, trigger debounced parse
        triggerParseAndBuildDebounced(rawEdi);
      } else {
        // Schema not ready (loading or not selected)
        if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current); // Clear pending parse

        // Only set error if relevant and no error exists
        if (!isSchemaLoading && !schema) {
          setParsedResult(prev => {
            if (prev.error) return prev; // Don't overwrite existing error
            const newError = availableSchemas.length > 0
              ? `Cannot process EDI: Select a schema first.`
              : `Cannot process EDI: No schemas found.`;
            return { data: null, error: newError };
          });
          // Reset structure view states only when setting the error
          setHierarchicalNodes([]);
          setFormattedEdiDisplay('');
          setIsInputMode(true);
        }
      }
    } else {
      // Raw EDI is empty, treat as clear
      handleClearInput();
    }

    return cleanup;
    // Dependencies: React to input, schema readiness. Callbacks are memoized.
  }, [rawEdi, schema, isSchemaLoading, availableSchemas.length, triggerParseAndBuildDebounced, handleClearInput]);


  // --- Other Handlers ---
  const toggleLogConsole = () => setIsLogConsoleOpen(prev => !prev);
  const clearLogs = () => { appLogger("Logs cleared by user.", 'info'); setLogMessages([]); };
  const handleUploadClick = () => { fileInputRef.current?.click(); };

  // Filtered Samples Memo
  const filteredSamples = useMemo(() => {
    if (!selectedSchemaKey) return [];
    return availableSamples.filter(sample => sample.schemaKey === selectedSchemaKey);
  }, [selectedSchemaKey, availableSamples]);

  // --- Render Logic ---
  const currentSchemaInfo = availableSchemas.find(s => s.key === selectedSchemaKey);
  const titleVersion = currentSchemaInfo ? `(${currentSchemaInfo.name} ${currentSchemaInfo.version})` : '(No Schema Selected)';
  const combinedDisplayValue = isInputMode ? rawEdi : formattedEdiDisplay;
  const isSchemaSelectDisabled = availableSchemas.length === 0 || isSchemaLoading;
  const isCombinedViewDisabled = isBusy || (availableSchemas.length > 0 && !selectedSchemaKey);
  const isStructureViewLoading = isBusy;

  return (
    <div className="flex flex-col h-screen bg-brand-bg text-brand-text-primary">
      {/* Header */}
      <header className="py-2 px-4 border-b border-brand-border flex-shrink-0 bg-brand-surface flex justify-between items-center flex-wrap gap-y-2">
        {/* Left Side */}
        <div className="flex items-center gap-3 md:gap-4 flex-wrap">
          <h1 className="text-lg md:text-xl font-semibold text-brand-accent flex-shrink-0">
            EDI Lens
            <span className="text-sm font-normal text-brand-text-secondary hidden sm:inline"> - X12 Viewer {titleVersion}</span>
          </h1>
          <div>
            <label htmlFor="schema-select" className="sr-only">Select Schema:</label>
            <select
              id="schema-select"
              value={selectedSchemaKey}
              onChange={handleSchemaChange}
              disabled={isSchemaSelectDisabled}
              className="text-xs bg-brand-surface-alt border border-brand-border rounded py-1 px-2 focus:ring-brand-accent focus:border-brand-accent text-brand-text-secondary disabled:opacity-70 min-w-[180px] md:min-w-[240px]"
            >
              {isSchemaLoading && <option value="" disabled>Loading Schemas...</option>}
              {!isSchemaLoading && availableSchemas.length === 0 && <option value="" disabled>No Schemas Found</option>}
              {!isSchemaLoading && availableSchemas.length > 0 && <option value="" disabled>Select Schema...</option>}
              {!isSchemaLoading && availableSchemas.map((sInfo) => (
                <option key={sInfo.key} value={sInfo.key}>
                  {sInfo.name} ({sInfo.version})
                </option>
              ))}
            </select>
          </div>
        </div>
        {/* Right Side: GitHub Link */}
        <div className="flex items-center space-x-3 md:space-x-4">
          <a
            href="https://github.com/kreddys/edi-lens"
            target="_blank"
            rel="noopener noreferrer"
            title="View project on GitHub"
            aria-label="View project on GitHub"
            className="text-brand-text-secondary hover:text-brand-text-primary transition-colors duration-200"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="currentColor"
              className="w-5 h-5"
              aria-hidden="true" >
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
            </svg>
            <span className="sr-only">GitHub Repository</span>
          </a>
        </div>
      </header>

      {/* Main Content Area */}
      <main className={`flex-grow flex flex-col md:flex-row gap-2 overflow-hidden p-2 md:p-3 transition-padding duration-300 ease-in-out ${isLogConsoleOpen ? 'pb-60' : 'pb-[34px]'}`}>
        {/* Left Column */}
        <div className="flex flex-col w-full md:w-1/2 h-full overflow-hidden">
          <div className="flex-grow h-full min-h-0">
            <CombinedEdiView
              displayValue={combinedDisplayValue}
              onValueChange={handleCombinedEdiChange}
              isInputMode={isInputMode}
              isProcessing={isProcessing} // Pass down actual processing state
              placeholder={!selectedSchemaKey && availableSchemas.length > 0 ? "Select a schema first..." : "Paste EDI data or Upload/Load Sample..."}
              onClear={handleClearInput}
              onUploadClick={handleUploadClick}
              isDisabled={isCombinedViewDisabled}
              samples={filteredSamples}
              onLoadSample={handleLoadSample}
            />
            <input
              type="file" ref={fileInputRef} onChange={handleFileChange}
              accept=".edi,.txt,text/plain,application/EDI-X12,application/edi"
              style={{ display: 'none' }}
              disabled={isCombinedViewDisabled}
            />
          </div>
        </div>

        {/* Right Column */}
        <div className="w-full md:w-1/2 h-full overflow-hidden">
          <StructuredEdiView
            parsedData={parsedResult.data}
            schema={schema}
            isLoading={isStructureViewLoading}
            error={parsedResult.error}
            hierarchicalNodes={hierarchicalNodes}
            activeView={activeStructuredView}
            onViewChange={setActiveStructuredView}
          />
        </div>
      </main>

      {/* Log Console */}
      <LogConsole
        messages={logMessages}
        isOpen={isLogConsoleOpen}
        onToggle={toggleLogConsole}
        onClear={clearLogs}
      />
    </div>
  );
}

export default App;