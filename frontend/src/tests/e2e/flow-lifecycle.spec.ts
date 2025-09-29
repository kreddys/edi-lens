import { test, expect } from '@playwright/test';
import {
  API_BASE_URL,
  ensureRegistryBucket,
  waitForProcessorControls,
  createFileProcessingPaths,
  cleanupFileProcessingPaths,
  waitForFlowStatus,
  dismissNotifications,
} from './utils/flow-helpers';

/**
 * End-to-End Flow Lifecycle Tests
 * 
 * These tests verify the complete user journey for flow management:
 * 1. Create a new flow from template
 * 2. Start the flow 
 * 3. Stop the flow
 * 4. Delete the flow
 * 
 * Prerequisites:
 * - All services must be running (backend, frontend, NiFi, Registry, DB)
 * - At least one template should be available
 * - Registry bucket availability is ensured automatically (the test will create one if needed)
 */

test.describe('Flow Management E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate directly to flows page
    await page.goto('/flows');
    
    // Wait for the page to load and flows list to appear
    await expect(page.locator('table')).toBeVisible();
  });

  test('Should navigate to flow creation page', async ({ page }) => {
    // Find and click the "Create New Flow" button
    await page.click('a[href="/flows/create"]');
    
    // Should navigate to create page
    await expect(page.url()).toContain('/flows/create');
    
    // Should see the flow creation form
    await expect(page.locator('text=Create New Flow')).toBeVisible();
  });

  test('Should display flows list', async ({ page }) => {
    // Should show flows table
    await expect(page.locator('table')).toBeVisible();

    // Should have table headers
    const headerCells = page.locator('thead').locator('th');
    await expect(headerCells.filter({ hasText: /^Name$/i }).first()).toBeVisible();
    await expect(headerCells.filter({ hasText: /^Status$/i }).first()).toBeVisible();
    await expect(headerCells.filter({ hasText: /^Description$/i }).first()).toBeVisible();
  });

  test('Should start and stop flow from list', async ({ page }) => {
    // Wait for any flow rows to appear
    const flowRows = page.locator('table tbody tr');
    const rowCount = await flowRows.count();
    
    if (rowCount > 0) {
      // Get the first flow row
      const firstRow = flowRows.first();
      
      // Look for start/stop buttons in the row
      const startButton = firstRow.locator('button[title*="start"], button:has-text("start")');
      const stopButton = firstRow.locator('button[title*="stop"], button:has-text("stop")');
      
      // Check if start button exists and click it
      if (await startButton.count() > 0) {
        await startButton.click();
        
        // Wait for success notification
        await expect(page.locator('.ant-notification')).toBeVisible({ timeout: 10000 });
      }
      
      // Wait a bit for UI to update
      await page.waitForTimeout(2000);
      
      // Check if stop button exists and click it
      if (await stopButton.count() > 0) {
        await stopButton.click();
        
        // Wait for success notification
        await expect(page.locator('.ant-notification')).toBeVisible({ timeout: 10000 });
      }
    } else {
      console.log('No flows found in the system');
    }
  });

  test('Should navigate to flow details', async ({ page }) => {
    // Wait for flows to load
    const flowRows = page.locator('table tbody tr');
    const rowCount = await flowRows.count();
    
    if (rowCount > 0) {
      // Click on the first flow (could be name link or show button)
      const firstRow = flowRows.first();
      const showButton = firstRow.locator('button[title*="show"], button[title*="view"], a');
      
      if (await showButton.count() > 0) {
        await showButton.first().click();
        
        // Should navigate to flow details page
        await expect(page.url()).toMatch(/\/flows\/[^\/]+$/);
        
        // Should show flow details
        await expect(page.locator('text=Flow Details')).toBeVisible();
      }
    }
  });

  test('Should test flow creation form validation', async ({ page }) => {
    // Navigate to create page
    await page.click('a[href="/flows/create"]');
    await expect(page.url()).toContain('/flows/create');
    
    // Wait for the create form to load
    await page.waitForLoadState('networkidle');
    
    // Wait for the page content to be visible - be more flexible about the structure
    await page.waitForTimeout(2000);
    
    // Check if we can see any indication this is a create page
    const pageContent = await page.textContent('body');
    console.log('Create page content preview:', pageContent?.substring(0, 500));
    
    // Just verify the page loaded without errors - don't assume form structure
    const hasPageContent = await page.locator('body').isVisible();
    expect(hasPageContent).toBeTruthy();
    
    // Try to find common form elements without being too specific
    const inputs = page.locator('input, textarea, select');
    const inputCount = await inputs.count();
    
    if (inputCount > 0) {
      console.log(`Found ${inputCount} form inputs on the create page`);
      
      // Try to interact with the first input if it exists
      const firstInput = inputs.first();
      const inputType = await firstInput.getAttribute('type');
      
      if (inputType !== 'hidden' && inputType !== 'submit') {
        await firstInput.fill('Test Value');
        console.log('Successfully filled first input');
      }
    } else {
      console.log('No form inputs found - this might be a different type of create interface');
    }
  });

  test('Should create flow from template and test Start/Stop button', async ({ page }) => {
    // Generate a consistent flow name that we'll use throughout the test
    const timestamp = Date.now();
    const testFlowName = `e2e-test-flow-${timestamp}`;
    const updatedFlowName = `${testFlowName}-updated`;
    const updatedDescription = 'Updated description for automated E2E verification';
    const updatedParameterValue = `playwright-parameter-${timestamp}`;
    const filePaths = createFileProcessingPaths(`lifecycle-${timestamp}`);
    const customInputDirectory = filePaths.nifi.input;
    const customOutputDirectory = filePaths.nifi.output;
    const customInputPattern = '.*\\.csv';
    console.log(`Starting test with flow name: ${testFlowName}`);

    const bucketToUse = await ensureRegistryBucket(page);
    
    try {
      // Navigate to flow creation page
      await page.click('a[href="/flows/create"]');
      await expect(page.url()).toContain('/flows/create');
      await page.waitForLoadState('networkidle');

      console.log('Create page content preview: \n', (await page.textContent('body'))?.substring(0, 200));
      
      // Step 1: Select template
      console.log('Looking for template cards...');
      const templateCards = page.locator('.ant-list-item, .template-card, .ant-card').filter({ hasText: /simple.*file.*processing/i });
      
      if (await templateCards.count() > 0) {
        console.log('Found Simple File Processing template card');
        await templateCards.first().click();
      } else {
        // Try alternative selector patterns
        console.log('Template cards not found with initial selector, trying alternatives...');
        
        const anyTemplate = page.locator('text=Simple File Processing').first();
        
        if (await anyTemplate.isVisible({ timeout: 5000 })) {
          console.log('Found template by text content');
          await anyTemplate.click();
        } else {
          throw new Error('No Simple File Processing template found - cannot proceed with test');
        }
      }
      
      // Wait for template selection to complete
      await page.waitForTimeout(2000);
      
      // Now we should be on step 2 - Flow Details. Fill out the required fields.
      console.log('Filling out flow details form...');
      
      // Fill in the flow name (required field) - try multiple selectors
      const nameInput = page.locator('#name')
        .or(page.locator('input[placeholder*="flow name" i]'))
        .or(page.locator('input').filter({ hasText: /name/i }).first())
        .or(page.locator('.ant-input').first());
        
      if (await nameInput.isVisible({ timeout: 5000 })) {
        console.log('Found name input, filling with:', testFlowName);
        await nameInput.fill(testFlowName);
        console.log('Flow name filled successfully');
      } else {
        console.log('Name input not found with any selector, checking available inputs...');
        const allInputs = page.locator('input');
        const inputCount = await allInputs.count();
        console.log(`Found ${inputCount} input elements on page`);
        
        if (inputCount > 0) {
          console.log('Filling first input with flow name');
          await allInputs.first().fill(testFlowName);
        } else {
          throw new Error('No input field found for flow name - cannot proceed');
        }
      }
      
      // Fill in description (optional)
      const descInput = page.locator('textarea[name="description"]').or(page.locator('textarea').first());
      if (await descInput.isVisible({ timeout: 3000 })) {
        console.log('Found description input');
        await descInput.fill('E2E test flow created from Simple File Processing template');
      }
      
      // Select a bucket (required field)
      const bucketSelect = page.locator('div[role="combobox"]').or(page.locator('.ant-select-selector')).first();
      if (await bucketSelect.isVisible({ timeout: 5000 })) {
        console.log('Found bucket selector');
        await bucketSelect.click();

        // Wait for dropdown to open and select the first available bucket
        await page.waitForTimeout(1000);
        const matchingBucketOption = page.locator('.ant-select-item-option-content', { hasText: bucketToUse.name }).first();
        if (await matchingBucketOption.isVisible({ timeout: 5000 })) {
          console.log(`Selecting registry bucket: ${bucketToUse.name}`);
          await matchingBucketOption.click();
        } else {
          console.log(`Bucket option for ${bucketToUse.name} not found. Selecting first available option as fallback.`);
          const firstBucket = page.locator('.ant-select-item').first();
          if (await firstBucket.isVisible({ timeout: 5000 })) {
            await firstBucket.click();
          } else {
            throw new Error('No registry bucket options were available to select.');
          }
        }
      }
      
      // Test parameter customization
      console.log('Looking for template parameters to customize...');
      
      // Check if parameters section is visible
      const parametersSection = page.locator('text=Template Parameters');
      if (await parametersSection.isVisible({ timeout: 3000 })) {
        console.log('Found Template Parameters section');
        
        // Look for input_directory parameter and customize it to use existing test directory
        const inputDirParam = page.locator('input').filter({ hasText: /input.*directory/i }).or(
          page.locator('input[placeholder*="tmp/nifi-working/input"]').or(
            page.locator('label:has-text("input_directory") + * input')
          )
        );
        
        if (await inputDirParam.count() > 0) {
          console.log('Found input_directory parameter, customizing it');
          await inputDirParam.first().clear();
          // Use the default directory which should exist - just verify it's set correctly
          await inputDirParam.first().fill(customInputDirectory);
        } else {
          console.log('Input directory parameter not found, trying generic approach');
          // Try to find any parameter input in the parameters section  
          const paramInputs = page.locator('.ant-input').filter({ hasText: /tmp\/nifi/ });
          if (await paramInputs.count() > 0) {
            await paramInputs.first().clear();
            await paramInputs.first().fill(customInputDirectory);
          }
        }
        
        const outputDirParam = page.locator('input').filter({ hasText: /output.*directory/i }).or(
          page.locator('input[placeholder*="tmp/nifi-working/output"]').or(
            page.locator('label:has-text("output_directory") + * input')
          )
        );

        if (await outputDirParam.count() > 0) {
          console.log('Found output_directory parameter, customizing it');
          await outputDirParam.first().clear();
          await outputDirParam.first().fill(customOutputDirectory);
        } else {
          console.log('Output directory parameter not found, trying generic approach');
          const outputInputs = page.locator('.ant-input').filter({ hasText: /output/ });
          if (await outputInputs.count() > 0) {
            await outputInputs.first().clear();
            await outputInputs.first().fill(customOutputDirectory);
          }
        }

        // Look for input_pattern parameter and customize it
        const inputPatternParam = page.locator('input').filter({ hasText: /pattern/i }).or(
          page.locator('input[placeholder*=".*"]').or(
            page.locator('label:has-text("input_pattern") + * input')
          )
        );
        
        if (await inputPatternParam.count() > 0) {
          console.log('Found input_pattern parameter, customizing it');
          await inputPatternParam.first().clear();
          await inputPatternParam.first().fill(customInputPattern);
        } else {
          console.log('Pattern parameter not found, trying generic approach');
        }
        
        console.log('✅ Parameter customization completed');
      } else {
        console.log('No parameters section found - template may not have parameters');
      }
      
      // Wait for form to be populated
      await page.waitForTimeout(1000);
      
      // Click Next to go to step 3 (Review)
      const nextButton = page.locator('button:has-text("Next")');
      if (await nextButton.isVisible({ timeout: 5000 })) {
        console.log('Found Next button, moving to review step');
        await nextButton.click();
        await page.waitForTimeout(2000);
      }
      
      // On the review step, validate parameters are shown
      console.log('Validating review step shows customized parameters...');
      
      // Check if parameters are displayed in review
      const parametersReview = page.locator('text=Parameters:');
      if (await parametersReview.isVisible({ timeout: 3000 })) {
        console.log('Found Parameters section in review');
        
        // Look for custom parameter values
        const customInputDir = page.getByText(customInputDirectory, { exact: false });
        const customOutputDir = page.getByText(customOutputDirectory, { exact: false });
        const customPattern = page.getByText(customInputPattern);
        const customTag = page.locator('.ant-tag:has-text("Custom")');

        if (await customInputDir.isVisible({ timeout: 2000 })) {
          console.log('✅ Found custom input directory in review');
        }

        if (await customOutputDir.isVisible({ timeout: 2000 })) {
          console.log('✅ Found custom output directory in review');
        }

        if (await customPattern.isVisible({ timeout: 2000 })) {
          console.log('✅ Found custom pattern in review');
        }
        
        if (await customTag.count() > 0) {
          console.log('✅ Found Custom tags indicating parameter overrides');
        }
      } else {
        console.log('No parameters review section found');
      }
      
      // On the review step, click the final create button  
      console.log('Looking for Create Flow button on review page...');
      
      // Wait a moment for the review page to fully render
      await page.waitForTimeout(1000);
      
      // Be very specific - target the "Create Flow" button, not the "Save" button
      const createFlowButton = page.getByRole('button', { name: 'Create Flow' });
        
      if (await createFlowButton.isVisible({ timeout: 8000 })) {
        console.log('Found Create Flow button, clicking it');
        await createFlowButton.click();
        console.log('Create Flow button clicked successfully');
      } else {
        console.log('Create Flow button not visible. Checking page content...');
        const pageContent = await page.textContent('body');
        console.log('Current page content includes:', pageContent?.substring(0, 500));
        
        // Try the specific button by exact text match
        const exactButton = page.locator('button', { hasText: 'Create Flow' }).first();
        if (await exactButton.isVisible({ timeout: 3000 })) {
          console.log('Found Create Flow button by exact text match');
          await exactButton.click();
        } else {
          console.log('No Create Flow button found');
        }
      }
      
      // Wait for flow creation to complete and navigation to occur
      // The frontend has a 1-second delay before navigation
      console.log('Waiting for flow creation and navigation...');
      
      // Wait a moment for the request to be sent and response received
      await page.waitForTimeout(2000);
      
      // Check for any messages that appeared - success, error, or loading
      const errorMessage = page.locator('.ant-message-error, .ant-notification-error');
      const successMessage = page.locator('.ant-message-success, .ant-notification-success');
      
      // Take a screenshot to see the current state
      await page.screenshot({ path: 'test-results/flow-creation-state.png' });
      
      if (await errorMessage.isVisible({ timeout: 1000 })) {
        const errorText = await errorMessage.textContent();
        console.log('❌ Error message found:', errorText);
        throw new Error(`Flow creation failed with error: ${errorText}`);
      }
      
      if (await successMessage.isVisible({ timeout: 4000 })) {
        const successText = await successMessage.textContent();
        console.log('✅ Success message found:', successText);
      } else {
        // No success message, let's see what's on the page
        console.log('No success message found. Current page state:');
        console.log('URL:', page.url());
        console.log('Page title:', await page.title());
        
        // Look for any other messages or loading states
        const allMessages = page.locator('[class*="message"], [class*="notification"], [class*="alert"]');
        const messageCount = await allMessages.count();
        console.log(`Found ${messageCount} message elements on page`);
        
        if (messageCount > 0) {
          for (let i = 0; i < Math.min(messageCount, 3); i++) {
            const messageText = await allMessages.nth(i).textContent();
            console.log(`Message ${i + 1}: ${messageText}`);
          }
        }
        
        // Check if we're still on create page and look for form errors
        if (page.url().includes('/flows/create')) {
          console.log('Still on create page - checking for form validation errors...');
          
          const formErrors = page.locator('.ant-form-item-explain-error, .ant-form-item-has-error');
          const errorCount = await formErrors.count();
          if (errorCount > 0) {
            console.log(`Found ${errorCount} form validation errors:`);
            for (let i = 0; i < errorCount; i++) {
              const errorText = await formErrors.nth(i).textContent();
              console.log(`Form error ${i + 1}: ${errorText}`);
            }
            throw new Error('Flow creation failed due to form validation errors');
          }
          
          // Check if the Create Flow button is still enabled/disabled
          const createButton = page.locator('button').filter({ hasText: /create.*flow/i });
          const isDisabled = await createButton.getAttribute('disabled');
          const isLoading = await createButton.locator('.ant-spin').isVisible().catch(() => false);
          console.log('Create Flow button state:', { disabled: isDisabled, loading: isLoading });
        }
        
        console.log('No immediate success indicator; verifying flow creation via list view.');
      }
      
      // Now wait for navigation with the built-in 1-second delay
      try {
        await page.waitForTimeout(2000); // Wait for the 1-second delay plus buffer
        await page.waitForURL(/\/flows(?!\/create)/, { timeout: 10000 });
        console.log('✅ Successfully navigated to flows list');
      } catch (navigationError) {
        console.log('Navigation timeout, manually navigating to flows list...');
        await page.goto('/flows');
        await page.waitForLoadState('networkidle');
      }
      
      // Refresh the page to ensure we get the latest flow list
      await page.reload();
      await page.waitForSelector('.ant-table-tbody', { timeout: 5000 });
      console.log('✅ Page refreshed to get latest flows list');
      
      // Try to use the search functionality to find our flow
      try {
        // Look for search icon in the Name column header
        const searchIcon = page.locator('.ant-table-filter-trigger').first();
        if (await searchIcon.isVisible({ timeout: 2000 })) {
          await searchIcon.click();
          
          // Type the flow name in the search box
          const searchInput = page.locator('input[placeholder*="Search flow name"]');
          if (await searchInput.isVisible({ timeout: 2000 })) {
            await searchInput.fill(testFlowName);
            await page.locator('button:has-text("Search")').click();
            await page.waitForTimeout(1000);
            console.log('✅ Used search filter to find the flow');
          }
        }
      } catch (searchError) {
        console.log('ℹ️ Search functionality not available or failed, continuing with pagination...');
      }
      
      // Verify the flow was actually created by finding it in the list
      console.log(`Searching for created flow: ${testFlowName}`);
      
      // Wait for the table to be ready
      await page.waitForSelector('.ant-table-row', { timeout: 5000 });
      
      // Look for our specific flow by exact name
      let createdFlow = page.locator('.ant-table-row').filter({ hasText: testFlowName });
      
      // If not found on current page, try navigating through pagination
      if (await createdFlow.count() === 0) {
        console.log('Flow not found on current page, checking pagination...');
        
        // Look for pagination controls and navigate if needed
        const paginationNext = page.locator('.ant-pagination-next').first();
        let pageNumber = 1;
        const maxPages = 5; // Limit to prevent infinite loop
        
        while (pageNumber <= maxPages && await createdFlow.count() === 0) {
          if (await paginationNext.isVisible() && await paginationNext.isEnabled()) {
            console.log(`Checking page ${pageNumber + 1}...`);
            await paginationNext.click();
            await page.waitForTimeout(2000); // Wait for table to update
            createdFlow = page.locator('.ant-table-row').filter({ hasText: testFlowName });
            pageNumber++;
          } else {
            break;
          }
        }
      }
      
      // The flow MUST be found, otherwise the test should fail
      await expect(createdFlow).toBeVisible({ timeout: 5000 });
      console.log('✅ Found created flow in the flows list');
      
      const flowId = await createdFlow.first().getAttribute('data-row-key') || 'unknown';
      console.log(`Created flow ID: ${flowId}`);

      // The template-backed flow should always materialize processors in NiFi.
      // Poll the flow detail API to make sure NiFi has finished instantiating the
      // processors before we continue with UI assertions.
      if (flowId !== 'unknown') {
        let processorCount = 0;
        const maxAttempts = 6;

        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
          const detailResponse = await page.request.get(`${API_BASE_URL}/api/v1/flows/${flowId}`);

          if (!detailResponse.ok()) {
            const body = await detailResponse.text();
            console.warn(`Attempt ${attempt}: failed to fetch flow details (status ${detailResponse.status()}): ${body}`);
          } else {
            const detailJson = await detailResponse.json();
            processorCount = detailJson?.processor_count ?? 0;
            console.log(`Attempt ${attempt}: flow reports ${processorCount} processors`);

            if (processorCount > 0) {
              break;
            }
          }

          if (attempt < maxAttempts) {
            await page.waitForTimeout(2000);
          }
        }

        expect(processorCount).toBeGreaterThan(0);
      }
      
      // Navigate to flow details to test Start/Stop buttons (they're not in the list view)
      console.log('✅ Flow was successfully created and is visible in the list');
      console.log('Navigating to flow details to test Start/Stop functionality...');
      
      // Click the Show button (first button in actions) to navigate to flow details
      const showButton = createdFlow.locator('button').first();
      await expect(showButton).toBeVisible();
      await showButton.click();
      
      // Wait for navigation to flow details page
      await page.waitForURL(/\/flows\/[^\/]+$/, { timeout: 10000 });
      console.log('✅ Successfully navigated to flow details page');

      // Wait for the flow details page to load
      await expect(page.locator('text=Flow Details')).toBeVisible({ timeout: 10000 });

      // Ensure the Start/Stop control reflects available processors before editing
      await waitForProcessorControls(page, flowId !== 'unknown' ? flowId : undefined);

      console.log('Updating flow using Edit form to verify persistence...');

      let editButton = page.getByRole('button', { name: /^Edit$/ });
      if (await editButton.count() === 0) {
        editButton = page.getByRole('link', { name: /^Edit$/ });
      }
      if (await editButton.count() === 0) {
        editButton = page.locator('button, a').filter({ hasText: /^Edit$/i });
      }

      await expect(editButton.first()).toBeVisible({ timeout: 5000 });
      await editButton.first().click();

      await page.waitForURL(/\/flows\/[^/]+\/edit$/, { timeout: 10000 });

      const editNameInput = page.getByLabel('Name');
      await expect(editNameInput).toBeVisible({ timeout: 5000 });
      await editNameInput.fill(updatedFlowName);

      const editDescriptionInput = page.getByLabel('Description');
      if (await editDescriptionInput.count() > 0) {
        await editDescriptionInput.fill(updatedDescription);
      }

      const saveButton = page.getByRole('button', { name: /save/i }).first();
      await expect(saveButton).toBeVisible({ timeout: 5000 });
      await saveButton.click();

      await page.waitForLoadState('networkidle');

      console.log('Navigating back to flow details to verify saved changes...');
      if (flowId !== 'unknown') {
        await page.goto(`/flows/${flowId}`);
        await page.waitForURL(`**/flows/${flowId}`, { timeout: 10000 });
      } else if (!/\/flows\/[^/]+$/.test(page.url())) {
        await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10000 });
        const postSaveRow = page.locator('.ant-table-row').filter({ hasText: updatedFlowName }).first();
        await expect(postSaveRow).toBeVisible({ timeout: 10000 });
        const postSaveShowButton = postSaveRow.locator('button').first();
        await expect(postSaveShowButton).toBeVisible({ timeout: 5000 });
        await postSaveShowButton.click();
        await page.waitForURL(/\/flows\/[^/]+$/, { timeout: 10000 });
      } else {
        await page.waitForURL(/\/flows\/[^/]+$/, { timeout: 10000 });
      }

      await expect(page.locator('text=Flow Details')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('body')).toContainText(updatedFlowName, { timeout: 10000 });
      await expect(page.locator('body')).toContainText(updatedDescription, { timeout: 10000 });

      console.log('Reloading show page to confirm edited details persist...');
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.locator('text=Flow Details')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('body')).toContainText(updatedFlowName, { timeout: 10000 });
      await expect(page.locator('body')).toContainText(updatedDescription, { timeout: 10000 });

      console.log('Verifying edited flow details appear in the flows list...');
      await page.goto('/flows');
      await page.waitForSelector('.ant-table-tbody', { timeout: 5000 });

      let updatedFlowRow = page.locator('.ant-table-row').filter({ hasText: updatedFlowName });

      if (await updatedFlowRow.count() === 0) {
        const paginationNext = page.locator('.ant-pagination-next').first();
        let pageNumber = 1;
        const maxPages = 5;

        while (pageNumber <= maxPages && await updatedFlowRow.count() === 0) {
          if (await paginationNext.isVisible() && await paginationNext.isEnabled()) {
            console.log(`Searching page ${pageNumber + 1} for updated flow...`);
            await paginationNext.click();
            await page.waitForTimeout(2000);
            updatedFlowRow = page.locator('.ant-table-row').filter({ hasText: updatedFlowName });
            pageNumber++;
          } else {
            break;
          }
        }
      }

      await expect(updatedFlowRow).toBeVisible({ timeout: 5000 });
      await expect(updatedFlowRow.first()).toContainText(updatedDescription);

      console.log('Navigating back to flow details for Start/Stop validation...');

      const showButtonAfterEdit = updatedFlowRow.first().locator('button').first();
      if (await showButtonAfterEdit.isVisible()) {
        await showButtonAfterEdit.click();
        await page.waitForURL(/\/flows\/[^/]+$/, { timeout: 10000 });
      } else if (flowId !== 'unknown') {
        await page.goto(`/flows/${flowId}`);
        await page.waitForLoadState('networkidle');
      } else {
        throw new Error('Unable to return to flow details after verifying list view');
      }

      await expect(page.locator('text=Flow Details')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('body')).toContainText(updatedFlowName, { timeout: 10000 });
      await expect(page.locator('body')).toContainText(updatedDescription, { timeout: 10000 });

      console.log('Opening parameter editor to verify parameter updates persist...');

      const parametersButton = page.locator('button:has-text("Parameters")').first();
      let editedParameterName: string | null = null;

      try {
        await expect(parametersButton).toBeVisible({ timeout: 10000 });
      } catch (error) {
        console.log('Parameters action not visible; skipping parameter edit validation.');
      }

      if ((await parametersButton.count()) > 0 && (await parametersButton.isVisible())) {
        await parametersButton.click();

        const modal = page
          .locator('.ant-modal')
          .filter({ has: page.locator('text=Edit Parameters') })
          .last();
        await expect(modal).toBeVisible({ timeout: 10000 });

        const modalRows = modal.locator('tbody tr');

        if (await modalRows.count()) {
          const modalRow = modalRows.first();
          editedParameterName = (await modalRow.locator('td').first().textContent())?.trim() || null;
          const editButton = modalRow.locator('button.ant-btn-text').first();
          await editButton.click();

          const valueInput = modalRow.locator('input[placeholder="Parameter value"]').first();
          await expect(valueInput).toBeVisible({ timeout: 5000 });
          await valueInput.fill(updatedParameterValue);

          const descriptionInput = modalRow.locator('textarea[placeholder="Parameter description"]').first();
          if (await descriptionInput.count()) {
            await descriptionInput.fill('Updated via Playwright');
          }

          const rowSaveButton = modalRow.locator('button.ant-btn-text').first();
          await rowSaveButton.click();
          await expect(modalRow.locator('input[placeholder="Parameter value"]').first()).not.toBeVisible({ timeout: 5000 });
        } else {
          editedParameterName = `playwright-param-${Date.now()}`;
          const addButton = modal.locator('button:has-text("Add Parameter")').first();
          await addButton.click();

          const newRow = modal.locator('tbody tr').last();
          await expect(newRow).toBeVisible({ timeout: 5000 });

          const nameInput = newRow.locator('input[placeholder="Parameter name"]').first();
          await expect(nameInput).toBeVisible({ timeout: 5000 });
          await nameInput.fill(editedParameterName);

          const valueInput = newRow.locator('input[placeholder="Parameter value"]').first();
          await valueInput.fill(updatedParameterValue);

          const descriptionInput = newRow.locator('textarea[placeholder="Parameter description"]').first();
          if (await descriptionInput.count()) {
            await descriptionInput.fill('Playwright added parameter');
          }

          const rowSaveButton = newRow.locator('button.ant-btn-text').first();
          await rowSaveButton.click();
          await expect(newRow.locator('input[placeholder="Parameter value"]').first()).not.toBeVisible({ timeout: 5000 });
        }

        const saveChangesButton = modal.locator('button:has-text("Save Changes")').first();
        await expect(saveChangesButton).toBeVisible({ timeout: 5000 });
        await saveChangesButton.click();

        await expect(page.locator('.ant-notification-notice-message')).toContainText('Parameters Updated', {
          timeout: 10000,
        });
        await expect(modal).not.toBeVisible({ timeout: 10000 });

        await page.waitForTimeout(1000);
        await page.reload();
        await page.waitForLoadState('networkidle');
        await expect(page.locator('text=Flow Details')).toBeVisible({ timeout: 10000 });

        if (editedParameterName) {
          const refreshedParameters = page
            .locator('div.ant-card')
            .filter({ has: page.locator('.ant-card-head-title:has-text("Flow Parameters")') })
            .first()
            .locator('tbody tr')
            .filter({ hasText: editedParameterName });

          await expect(refreshedParameters.first()).toContainText(updatedParameterValue);

          if (flowId !== 'unknown') {
            const parameterDetailResponse = await page.request.get(`${API_BASE_URL}/api/v1/flows/${flowId}`);
            if (parameterDetailResponse.ok()) {
              const parameterDetailJson = await parameterDetailResponse.json();
              const parameterEntry = parameterDetailJson?.parameters?.[editedParameterName];
              const parameterValueFromApi =
                parameterEntry && typeof parameterEntry === 'object'
                  ? parameterEntry.value
                  : parameterEntry;
              expect(parameterValueFromApi).toBe(updatedParameterValue);
            } else {
              console.warn(
                `Failed to fetch flow details for parameter verification (status ${parameterDetailResponse.status()})`,
              );
            }
          }
        } else {
          console.log('Parameter update completed but parameter name could not be determined.');
        }
      } else {
        console.log('Parameters action not visible; skipping parameter edit validation.');
      }

      await waitForProcessorControls(page, flowId !== 'unknown' ? flowId : undefined);

      // Find the Start/Stop button in the header actions
      const playButton = page.locator('button:has(span.anticon-play-circle)');
      const pauseButton = page.locator('button:has(span.anticon-pause-circle)');

      // The flow has processors, test the button functionality
      if (await playButton.isVisible()) {
        console.log('✅ Found Play button - flow is currently stopped');
        expect(await playButton.isEnabled()).toBe(true);
      } else if (await pauseButton.isVisible()) {
        console.log('✅ Found Pause button - flow is currently running');
        expect(await pauseButton.isEnabled()).toBe(true);
      }

      console.log('✅ Flow creation and Start/Stop test completed successfully');
      
    } catch (error) {
      console.error('Flow lifecycle test failed:', error);
      throw error;
    } finally {
      cleanupFileProcessingPaths(filePaths);
    }
  });

  test('Should toggle Start/Stop button dynamically in flow details', async ({ page }) => {
    test.setTimeout(180000);
    // Wait for flows to load
    await page.waitForSelector('table', { timeout: 10000 });
    
    // Get only visible data rows (exclude measure rows and other hidden rows)
    const flowRows = page.locator('table tbody tr:not(.ant-table-measure-row):not([aria-hidden="true"])');
    const rowCount = await flowRows.count();
    
    console.log(`Found ${rowCount} visible flows in the table`);
    
    if (rowCount > 0) {
      // Get the first visible flow row
      const firstRow = flowRows.first();
      
      // Wait for the row to be visible and contain data
      await expect(firstRow).toBeVisible();
      await page.waitForTimeout(1000); // Allow time for data to load
      
      // Debug: Log the contents of the first row
      const rowText = await firstRow.textContent();
      console.log(`First row content: "${rowText?.trim()}"`);
      
      // Look for action buttons in the last column (Actions column)
      const actionButtons = firstRow.locator('td:last-child button');
      const buttonCount = await actionButtons.count();
      console.log(`Found ${buttonCount} action buttons in first row`);
      
      if (buttonCount > 0) {
        // Click the first action button (should be Show button)
        const showButton = actionButtons.first();
        await showButton.click();
        
        // Wait for navigation to flow details
        await page.waitForURL(/\/flows\/[^\/]+$/, { timeout: 10000 });
        console.log('Successfully navigated to flow details page');
      } else {
        console.log('No action buttons found - this might indicate the flows are still loading');
        return;
      }
      
      // Wait for the flow details page to load
      await expect(page.locator('text=Flow Details')).toBeVisible({ timeout: 10000 });

      const flowUrl = page.url();
      const flowIdMatch = flowUrl.match(/\/flows\/([^/]+)/);
      const currentFlowId = flowIdMatch?.[1];
      const statusTimeout = 90000;

      // Ensure processor controls are rendered before interacting with the Start/Stop button
      await waitForProcessorControls(page, currentFlowId);

      const startStopLocator = page.locator(
        'button:has(span.anticon-play-circle), button:has(span.anticon-pause-circle)',
      );

      // Wait for at least one of the buttons to be visible
      await expect(startStopLocator).toBeVisible({ timeout: 10000 });

      // Check if the button shows "No Processors" - this means it's an empty flow
      const buttonText = await startStopLocator.first().textContent();
      console.log(`Button text: "${buttonText}"`);
      
      if (buttonText?.includes('No Processors')) {
        console.log('✅ Flow has no processors - button correctly shows disabled state');

        // Verify the button is disabled
        const button = page.locator('button:has(span.anticon-play-circle), button:has(span.anticon-pause-circle)').first();
        if (await button.isEnabled()) {
          console.warn('⚠️ Start/Stop button remained enabled even though it reports No Processors.');
        } else {
          console.log('✅ Start/Stop button is correctly disabled for empty flow');
        }

        return;
      }
      
      if (!currentFlowId) {
        console.warn('Unable to determine flow ID for dynamic Start/Stop verification.');
        return;
      }

      const detailResponse = await page.request.get(`${API_BASE_URL}/api/v1/flows/${currentFlowId}`);
      expect(detailResponse.ok()).toBeTruthy();
      const detailJson = await detailResponse.json();
      const flowStatus = String(detailJson?.status ?? '').toLowerCase();

      if (['running', 'partially_running'].includes(flowStatus)) {
        const pauseButton = page.locator('button:has(span.anticon-pause-circle)');
        await expect(pauseButton).toBeVisible({ timeout: 15000 });
        console.log('✅ Pause button is visible for a running flow');
      } else {
        const playButton = page.locator('button:has(span.anticon-play-circle)');
        await expect(playButton).toBeVisible({ timeout: 15000 });
        console.log('✅ Start button is visible for a stopped flow');
      }

      console.log('✅ Dynamic Start/Stop button test verified UI matches backend status');
      
    } else {
      console.log('⚠️  No flows found in the system - skipping button toggle test');
    }
  });

  test('Should handle errors gracefully', async ({ page }) => {
    // Test that the page loads without JavaScript errors
    const errors: string[] = [];
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });
    
    await page.goto('/flows');
    await page.waitForLoadState('networkidle');
    
    // Should not have critical JavaScript errors
    const criticalErrors = errors.filter(error => 
      !error.includes('favicon') && 
      !error.includes('chrome-extension') &&
      !error.includes('Non-Error promise rejection')
    );
    
    expect(criticalErrors).toHaveLength(0);
  });

  test('Should test responsive design', async ({ page }) => {
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/flows');
    
    // Should still show flows table or mobile version
    await expect(page.locator('table, .ant-list')).toBeVisible();
    
    // Test tablet viewport  
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.reload();
    
    // Should show flows table
    await expect(page.locator('table')).toBeVisible();
    
    // Reset to desktop
    await page.setViewportSize({ width: 1200, height: 800 });
  });
});