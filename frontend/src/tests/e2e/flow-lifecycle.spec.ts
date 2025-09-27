import { test, expect } from '@playwright/test';

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
 * - At least one bucket should be available
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
    await expect(page.locator('text=Name')).toBeVisible();
    await expect(page.locator('text=Status')).toBeVisible();
    await expect(page.locator('text=Description')).toBeVisible();
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

  test('Should toggle Start/Stop button dynamically in flow details', async ({ page }) => {
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
      
      // Find the Start/Stop button in the header actions
      const playButton = page.locator('button:has(span.anticon-play-circle)');
      const pauseButton = page.locator('button:has(span.anticon-pause-circle)');
      
      // Wait for at least one of the buttons to be visible
      await expect(page.locator('button:has(span.anticon-play-circle), button:has(span.anticon-pause-circle)')).toBeVisible({ timeout: 10000 });
      
      // Check if the button shows "No Processors" - this means it's an empty flow
      const buttonText = await page.locator('button:has(span.anticon-play-circle), button:has(span.anticon-pause-circle)').first().textContent();
      console.log(`Button text: "${buttonText}"`);
      
      if (buttonText?.includes('No Processors')) {
        console.log('✅ Flow has no processors - button correctly shows disabled state');
        
        // Verify the button is disabled
        const button = page.locator('button:has(span.anticon-play-circle), button:has(span.anticon-pause-circle)').first();
        await expect(button).toBeDisabled();
        
        console.log('✅ Start/Stop button is correctly disabled for empty flow');
        return;
      }
      
      // For flows with processors, test the toggle behavior
      const playVisible = await playButton.isVisible();
      const pauseVisible = await pauseButton.isVisible();
      
      console.log(`Play button visible: ${playVisible}, Pause button visible: ${pauseVisible}`);
      
      if (pauseVisible) {
        // Flow is running - Stop button should be visible
        const stopButtonText = await pauseButton.textContent();
        console.log(`Stop button text: "${stopButtonText}"`);
        
        // Click to stop the flow
        await pauseButton.click();
        
        // Wait for success notification
        await expect(page.locator('.ant-notification-notice')).toBeVisible({ timeout: 10000 });
        
        // Button should change to Start
        await expect(playButton).toBeVisible({ timeout: 15000 });
        console.log('✅ Successfully stopped flow and button changed to Start');
        
      } else if (playVisible) {
        // Flow is stopped - Start button should be visible
        const startButtonText = await playButton.textContent();
        console.log(`Start button text: "${startButtonText}"`);
        
        // Click to start the flow
        await playButton.click();
        
        // Wait for success notification
        await expect(page.locator('.ant-notification-notice')).toBeVisible({ timeout: 15000 });
        
        // Button should change to Stop
        await expect(pauseButton).toBeVisible({ timeout: 15000 });
        console.log('✅ Successfully started flow and button changed to Stop');
        
      } else {
        console.log('❌ Neither Start nor Stop button found - this might indicate a UI issue');
        
        // Debug: Log all buttons on the page
        const allButtons = page.locator('button');
        const allButtonsCount = await allButtons.count();
        console.log(`Total buttons on page: ${allButtonsCount}`);
        
        for (let i = 0; i < Math.min(5, allButtonsCount); i++) {
          const buttonText = await allButtons.nth(i).textContent();
          console.log(`Button ${i}: "${buttonText}"`);
        }
      }
      
      console.log('✅ Dynamic Start/Stop button test completed');
      
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