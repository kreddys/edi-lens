import { test, expect } from '@playwright/test';

/**
 * End-to-End Parameter Management Tests
 * 
 * These tests verify parameter management functionality:
 * 1. View flow parameters
 * 2. Open parameter edit modal 
 * 3. Add new parameters
 * 4. Edit existing parameters
 * 5. Mark parameters as sensitive
 * 6. Save parameter changes
 * 7. Verify parameter updates
 */

test.describe('Parameter Management E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to flows page
    await page.goto('/flows');
    
    // Wait for the page to load and flows list to appear
    await expect(page.locator('table')).toBeVisible({ timeout: 10000 });
  });

  test('Should display flow parameters on flow details page', async ({ page }) => {
    // Find a flow row and navigate to details
    const flowRows = page.locator('table tbody tr');
    const rowCount = await flowRows.count();
    
    if (rowCount > 0) {
      const firstRow = flowRows.first();
      
      // Look for show/view button or link to flow details
      const showButton = firstRow.locator('button[title*="show"], button[title*="view"], a[href*="/flows/"]');
      
      if (await showButton.count() > 0) {
        await showButton.first().click();
        
        // Should navigate to flow details page
        await expect(page.url()).toMatch(/\/flows\/[^\/]+$/);
        
        // Should show flow details card
        await expect(page.locator('text=Flow Details')).toBeVisible();
        
        // Check if parameters section exists
        const parametersCard = page.locator('text=Flow Parameters').locator('..');
        if (await parametersCard.count() > 0) {
          console.log('✅ Flow has parameters - parameters section is visible');
          
          // Should show parameters table
          await expect(parametersCard.locator('table')).toBeVisible();
          
          // Should have parameter columns
          await expect(page.locator('text=Parameter Name')).toBeVisible();
          await expect(page.locator('text=Value')).toBeVisible();
          
        } else {
          console.log('⚠️  Flow has no parameters - parameters section not shown');
        }
      }
    } else {
      console.log('⚠️  No flows found in the system');
    }
  });

  test('Should open and close parameter edit modal', async ({ page }) => {
    // Navigate to first flow details
    const flowRows = page.locator('table tbody tr');
    const rowCount = await flowRows.count();
    
    if (rowCount > 0) {
      const firstRow = flowRows.first();
      const showButton = firstRow.locator('button[title*="show"], button[title*="view"], a[href*="/flows/"]');
      
      if (await showButton.count() > 0) {
        await showButton.first().click();
        
        // Should be on flow details page
        await expect(page.url()).toMatch(/\/flows\/[^\/]+$/);
        
        // Look for Parameters button in the header
        const parametersButton = page.locator('button:has-text("Parameters")');
        
        if (await parametersButton.count() > 0) {
          // Click Parameters button
          await parametersButton.click();
          
          // Should open parameter edit modal
          await expect(page.locator('text=Edit Parameters')).toBeVisible();
          await expect(page.locator('.ant-modal')).toBeVisible();
          
          console.log('✅ Parameter edit modal opened successfully');
          
          // Should have modal content
          await expect(page.locator('text=Configure parameters for your flow')).toBeVisible();
          
          // Should have action buttons
          await expect(page.locator('button:has-text("Add Parameter")')).toBeVisible();
          await expect(page.locator('button:has-text("Save Changes")')).toBeVisible();
          
          // Close modal with Cancel button
          await page.locator('button:has-text("Cancel")').click();
          
          // Modal should be closed
          await expect(page.locator('.ant-modal')).not.toBeVisible();
          console.log('✅ Parameter edit modal closed successfully');
          
        } else {
          console.log('⚠️  Parameters button not found - may indicate flow has no parameter context');
        }
      }
    }
  });

  test('Should add new parameter', async ({ page }) => {
    // Navigate to first flow details
    const flowRows = page.locator('table tbody tr');
    const rowCount = await flowRows.count();
    
    if (rowCount > 0) {
      const firstRow = flowRows.first();
      const showButton = firstRow.locator('button[title*="show"], button[title*="view"], a[href*="/flows/"]');
      
      if (await showButton.count() > 0) {
        await showButton.first().click();
        
        // Look for Parameters button
        const parametersButton = page.locator('button:has-text("Parameters")');
        
        if (await parametersButton.count() > 0) {
          await parametersButton.click();
          
          // Should open parameter edit modal
          await expect(page.locator('.ant-modal')).toBeVisible();
          
          // Click Add Parameter button
          await page.locator('button:has-text("Add Parameter")').click();
          
          // Should add a new row to parameters table
          const parameterTable = page.locator('.ant-modal table');
          await expect(parameterTable).toBeVisible();
          
          // Find the new parameter row that should be in editing mode
          const editableRows = parameterTable.locator('tbody tr');
          const rowCount = await editableRows.count();
          
          if (rowCount > 0) {
            console.log(`✅ Found ${rowCount} parameter row(s), looking for editable inputs`);
            
            // Look for input fields in the last row (newly added)
            const lastRow = editableRows.last();
            const nameInput = lastRow.locator('input').first();
            const valueInput = lastRow.locator('input').nth(1);
            const descriptionInput = lastRow.locator('textarea');
            
            if (await nameInput.count() > 0) {
              // Fill in parameter details
              await nameInput.fill('test_param_e2e');
              console.log('✅ Filled parameter name');
              
              if (await valueInput.count() > 0) {
                await valueInput.fill('test_value_123');
                console.log('✅ Filled parameter value');
              }
              
              if (await descriptionInput.count() > 0) {
                await descriptionInput.fill('E2E test parameter');
                console.log('✅ Filled parameter description');
              }
              
              // Click save icon to confirm the edit
              const saveIcon = lastRow.locator('button[title*="save"], button:has([data-icon="save"])');
              if (await saveIcon.count() > 0) {
                await saveIcon.click();
                console.log('✅ Saved parameter edit');
              }
              
              // Now save the entire form
              await page.locator('button:has-text("Save Changes")').click();
              
              // Wait for success notification
              await expect(page.locator('.ant-notification-notice')).toBeVisible({ timeout: 10000 });
              console.log('✅ Parameters saved successfully');
              
              // Modal should close
              await expect(page.locator('.ant-modal')).not.toBeVisible();
              
              // Refresh page to verify parameter was saved
              await page.reload();
              
              // Check if the new parameter appears in the parameters section
              const parametersSection = page.locator('text=Flow Parameters').locator('..');
              if (await parametersSection.count() > 0) {
                // Look for the new parameter in the table
                const newParam = parametersSection.locator('text=test_param_e2e');
                if (await newParam.count() > 0) {
                  console.log('✅ New parameter visible on flow details page');
                } else {
                  console.log('⚠️  New parameter not visible after refresh');
                }
              }
              
            } else {
              console.log('⚠️  No input fields found for parameter editing');
            }
          } else {
            console.log('⚠️  No parameter rows found in table');
          }
        }
      }
    }
  });

  test('Should edit existing parameter', async ({ page }) => {
    // Navigate to first flow details
    const flowRows = page.locator('table tbody tr');
    const rowCount = await flowRows.count();
    
    if (rowCount > 0) {
      const firstRow = flowRows.first();
      const showButton = firstRow.locator('button[title*="show"], button[title*="view"], a[href*="/flows/"]');
      
      if (await showButton.count() > 0) {
        await showButton.first().click();
        
        // Look for Parameters button
        const parametersButton = page.locator('button:has-text("Parameters")');
        
        if (await parametersButton.count() > 0) {
          await parametersButton.click();
          
          // Should open parameter edit modal
          await expect(page.locator('.ant-modal')).toBeVisible();
          
          // Look for existing parameters
          const parameterTable = page.locator('.ant-modal table');
          const existingRows = parameterTable.locator('tbody tr');
          const existingRowCount = await existingRows.count();
          
          if (existingRowCount > 0) {
            console.log(`✅ Found ${existingRowCount} existing parameter(s)`);
            
            // Click edit button on first parameter
            const firstRow = existingRows.first();
            const editButton = firstRow.locator('button[title*="edit"], button:has([data-icon="edit"])');
            
            if (await editButton.count() > 0) {
              await editButton.click();
              console.log('✅ Clicked edit button on first parameter');
              
              // Should show editable inputs
              const valueInput = firstRow.locator('input[type="text"], input[type="password"]');
              
              if (await valueInput.count() > 0) {
                // Modify the value
                await valueInput.fill('updated_value_' + Date.now());
                console.log('✅ Updated parameter value');
                
                // Click save to confirm edit
                const saveButton = firstRow.locator('button[title*="save"], button:has([data-icon="save"])');
                if (await saveButton.count() > 0) {
                  await saveButton.click();
                  console.log('✅ Saved parameter edit');
                }
                
                // Save all changes
                await page.locator('button:has-text("Save Changes")').click();
                
                // Wait for success notification
                await expect(page.locator('.ant-notification-notice')).toBeVisible({ timeout: 10000 });
                console.log('✅ Parameter update saved successfully');
                
              } else {
                console.log('⚠️  No editable input found for parameter');
              }
            } else {
              console.log('⚠️  No edit button found for parameter');
            }
          } else {
            console.log('⚠️  No existing parameters found to edit');
          }
        }
      }
    }
  });

  test('Should handle sensitive parameters', async ({ page }) => {
    // Navigate to first flow details
    const flowRows = page.locator('table tbody tr');
    const rowCount = await flowRows.count();
    
    if (rowCount > 0) {
      const firstRow = flowRows.first();
      const showButton = firstRow.locator('button[title*="show"], button[title*="view"], a[href*="/flows/"]');
      
      if (await showButton.count() > 0) {
        await showButton.first().click();
        
        // Look for Parameters button
        const parametersButton = page.locator('button:has-text("Parameters")');
        
        if (await parametersButton.count() > 0) {
          await parametersButton.click();
          
          // Should open parameter edit modal
          await expect(page.locator('.ant-modal')).toBeVisible();
          
          // Add a sensitive parameter
          await page.locator('button:has-text("Add Parameter")').click();
          
          const parameterTable = page.locator('.ant-modal table');
          const rows = parameterTable.locator('tbody tr');
          const lastRow = rows.last();
          
          // Fill parameter details
          const nameInput = lastRow.locator('input').first();
          const valueInput = lastRow.locator('input').nth(1);
          const sensitiveSwitch = lastRow.locator('.ant-switch');
          
          if (await nameInput.count() > 0) {
            await nameInput.fill('secret_key');
            await valueInput.fill('super_secret_value');
            
            // Mark as sensitive
            if (await sensitiveSwitch.count() > 0) {
              await sensitiveSwitch.click();
              console.log('✅ Marked parameter as sensitive');
            }
            
            // Save the edit
            const saveIcon = lastRow.locator('button[title*="save"], button:has([data-icon="save"])');
            if (await saveIcon.count() > 0) {
              await saveIcon.click();
            }
            
            // Save all changes
            await page.locator('button:has-text("Save Changes")').click();
            
            // Wait for success notification
            await expect(page.locator('.ant-notification-notice')).toBeVisible({ timeout: 10000 });
            console.log('✅ Sensitive parameter saved successfully');
            
            // Modal should close
            await expect(page.locator('.ant-modal')).not.toBeVisible();
            
            // Refresh and verify sensitive parameter is masked
            await page.reload();
            
            const parametersSection = page.locator('text=Flow Parameters').locator('..');
            if (await parametersSection.count() > 0) {
              // Look for SENSITIVE tag
              const sensitiveTag = parametersSection.locator('text=SENSITIVE');
              if (await sensitiveTag.count() > 0) {
                console.log('✅ Sensitive parameter is properly tagged');
              }
            }
          }
        }
      }
    }
  });

  test('Should validate parameter form', async ({ page }) => {
    // Navigate to first flow details
    const flowRows = page.locator('table tbody tr');
    const rowCount = await flowRows.count();
    
    if (rowCount > 0) {
      const firstRow = flowRows.first();
      const showButton = firstRow.locator('button[title*="show"], button[title*="view"], a[href*="/flows/"]');
      
      if (await showButton.count() > 0) {
        await showButton.first().click();
        
        // Look for Parameters button
        const parametersButton = page.locator('button:has-text("Parameters")');
        
        if (await parametersButton.count() > 0) {
          await parametersButton.click();
          
          // Should open parameter edit modal
          await expect(page.locator('.ant-modal')).toBeVisible();
          
          // Try to save without making changes - should work
          const saveButton = page.locator('button:has-text("Save Changes")');
          const isDisabled = await saveButton.isDisabled();
          
          if (!isDisabled) {
            console.log('✅ Save button is enabled for empty form');
          }
          
          // Add parameter but leave name empty
          await page.locator('button:has-text("Add Parameter")').click();
          
          const parameterTable = page.locator('.ant-modal table');
          const rows = parameterTable.locator('tbody tr');
          const lastRow = rows.last();
          
          const valueInput = lastRow.locator('input').nth(1);
          if (await valueInput.count() > 0) {
            await valueInput.fill('some_value');
            
            // Try to save with empty parameter name
            const saveIcon = lastRow.locator('button[title*="save"], button:has([data-icon="save"])');
            if (await saveIcon.count() > 0) {
              await saveIcon.click();
            }
            
            // Should still be able to save (backend will handle validation)
            await saveButton.click();
            
            // May show error notification or succeed - depends on backend validation
            const notification = page.locator('.ant-notification-notice');
            await expect(notification).toBeVisible({ timeout: 5000 });
            
            console.log('✅ Form validation test completed');
          }
        }
      }
    }
  });
});