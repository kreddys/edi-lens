import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import {
  API_BASE_URL,
  createFileProcessingPaths,
  cleanupFileProcessingPaths,
  ensureRegistryBucket,
  getRepoRoot,
  waitForFile,
  waitForFlowStatus,
  waitForProcessorControls,
  dismissNotifications,
} from './utils/flow-helpers';

test.describe('Template-driven file processing flow', () => {
  test.describe.configure({ timeout: 180000 });

  test('creates, edits, updates parameters, and processes files end-to-end', async ({ page }) => {
    test.slow();
    const testId = `tpl-${Date.now()}`;
    const templateName = `Playwright File Processing Template ${testId}`;
    const flowName = `playwright-template-flow-${testId}`;
    const updatedFlowName = `${flowName}-edited`;
    const updatedDescription = 'Playwright updated description for template-based flow';
    const updatedPattern = `^playwright-${testId}-.*\\.txt$`;

    const repoRoot = getRepoRoot();
    const templatesDir = path.join(repoRoot, 'data', 'flows');
    const templateFilename = `playwright-template-${testId}.json`;
    const templatePath = path.join(templatesDir, templateFilename);

    const filePaths = createFileProcessingPaths(testId);
    const bucket = await ensureRegistryBucket(page);

    const templateDefinition = {
      name: templateName,
      description: 'Playwright generated template for file processing validation',
      processors: [
        {
          identifier: 'getfile-template',
          name: 'GetFile Playwright Input',
          type: 'org.apache.nifi.processors.standard.GetFile',
          position: { x: 0.0, y: 0.0 },
          properties: {
            'Input Directory': '#{input_directory}',
            'File Filter': '#{input_pattern}',
            'Keep Source File': 'false',
            'Minimum File Age': '0 sec',
            'Polling Interval': '1 sec',
          },
          schedulingPeriod: '1 sec',
          schedulingStrategy: 'TIMER_DRIVEN',
          executionNode: 'ALL',
          concurrentlySchedulableTaskCount: 1,
          autoTerminatedRelationships: ['failure'],
        },
        {
          identifier: 'updateattr-template',
          name: 'UpdateAttribute Playwright Rename',
          type: 'org.apache.nifi.processors.attributes.UpdateAttribute',
          position: { x: 300.0, y: 0.0 },
          properties: {
            filename: 'processed_${filename}',
            'processing.timestamp': "${now():format('yyyy-MM-dd HH:mm:ss')}",
          },
          schedulingPeriod: '0 sec',
          schedulingStrategy: 'TIMER_DRIVEN',
          executionNode: 'ALL',
          concurrentlySchedulableTaskCount: 1,
          autoTerminatedRelationships: ['failure'],
        },
        {
          identifier: 'putfile-template',
          name: 'PutFile Playwright Output',
          type: 'org.apache.nifi.processors.standard.PutFile',
          position: { x: 600.0, y: 0.0 },
          properties: {
            Directory: '#{output_directory}',
            'Create Missing Directories': 'true',
            'Conflict Resolution Strategy': 'replace',
          },
          schedulingPeriod: '0 sec',
          schedulingStrategy: 'TIMER_DRIVEN',
          executionNode: 'ALL',
          concurrentlySchedulableTaskCount: 1,
          autoTerminatedRelationships: ['success', 'failure'],
        },
      ],
      connections: [
        {
          identifier: 'connection-template-1',
          name: 'GetFile to UpdateAttribute',
          source: { id: 'getfile-template', type: 'PROCESSOR' },
          destination: { id: 'updateattr-template', type: 'PROCESSOR' },
          selectedRelationships: ['success'],
          backPressureObjectThreshold: 1000,
          backPressureDataSizeThreshold: '1 GB',
          flowFileExpiration: '0 sec',
        },
        {
          identifier: 'connection-template-2',
          name: 'UpdateAttribute to PutFile',
          source: { id: 'updateattr-template', type: 'PROCESSOR' },
          destination: { id: 'putfile-template', type: 'PROCESSOR' },
          selectedRelationships: ['success'],
          backPressureObjectThreshold: 1000,
          backPressureDataSizeThreshold: '1 GB',
          flowFileExpiration: '0 sec',
        },
      ],
      parameters: {
        input_directory: {
          description: 'Directory to monitor for incoming files',
          default: '/tmp/nifi-working/input',
        },
        output_directory: {
          description: 'Directory to store processed files',
          default: '/tmp/nifi-working/output',
        },
        input_pattern: {
          description: 'Regex pattern for files to ingest',
          default: '.*\\.txt$',
        },
      },
    };

    fs.mkdirSync(templatesDir, { recursive: true });
    fs.writeFileSync(templatePath, JSON.stringify(templateDefinition, null, 2));

    let flowId: string | undefined;

    try {
      await page.goto('/flows');
      await expect(page.locator('table')).toBeVisible({ timeout: 15000 });

      await page.click('a[href="/flows/create"]');
      await expect(page.url()).toContain('/flows/create');

      const templateCard = page.locator('.ant-card').filter({ hasText: templateName }).first();
      await expect(templateCard).toBeVisible({ timeout: 15000 });
      await templateCard.click();

      await expect(page.locator('text=Flow Configuration')).toBeVisible({ timeout: 10000 });

      const nameInput = page.locator('#name');
      await expect(nameInput).toBeVisible({ timeout: 5000 });
      await nameInput.fill(flowName);

      const descriptionInput = page.locator('textarea[name="description"]');
      if (await descriptionInput.count()) {
        await descriptionInput.fill('Template-based file processing flow created by Playwright');
      }

      const bucketFormItem = page.locator('.ant-form-item').filter({ hasText: 'Storage Bucket' }).first();
      const bucketSelector = bucketFormItem.locator('.ant-select-selector');
      await bucketSelector.click();
      const bucketOption = page
        .locator('.ant-select-item-option-content')
        .filter({ hasText: bucket.name })
        .first();
      if (await bucketOption.count()) {
        await bucketOption.click();
      } else {
        await page.locator('.ant-select-item').first().click();
      }

      const inputDirectoryField = page.getByRole('textbox', { name: /^input_directory/i });
      await expect(inputDirectoryField).toBeVisible({ timeout: 10000 });
      await inputDirectoryField.fill(filePaths.nifi.input);

      const outputDirectoryField = page.getByRole('textbox', { name: /^output_directory/i });
      await expect(outputDirectoryField).toBeVisible({ timeout: 10000 });
      await outputDirectoryField.fill(filePaths.nifi.output);

      const inputPatternField = page.getByRole('textbox', { name: /^input_pattern/i });
      await expect(inputPatternField).toBeVisible({ timeout: 10000 });
      await inputPatternField.fill('.*\\.txt$');

      await page.getByRole('button', { name: /^Next$/ }).click();
      await expect(page.locator('text=Review Flow Configuration')).toBeVisible({ timeout: 10000 });

      await page.getByRole('button', { name: /^Create Flow$/ }).click();

      await page.waitForURL('**/flows', { timeout: 20000 });
      await expect(page.locator('.ant-table-tbody')).toBeVisible({ timeout: 10000 });

      let createdFlowRow = page.locator('.ant-table-row').filter({ hasText: flowName });
      if (await createdFlowRow.count() === 0) {
        const paginationNext = page.locator('.ant-pagination-next').first();
        let pageCount = 0;
        while (pageCount < 5 && (await createdFlowRow.count()) === 0) {
          if (await paginationNext.isVisible() && await paginationNext.isEnabled()) {
            await paginationNext.click();
            await page.waitForTimeout(1500);
            createdFlowRow = page.locator('.ant-table-row').filter({ hasText: flowName });
          }
          pageCount += 1;
        }
      }

      await expect(createdFlowRow).toBeVisible({ timeout: 10000 });
      flowId = (await createdFlowRow.first().getAttribute('data-row-key')) ?? undefined;
      expect(flowId).toBeDefined();

      const showButton = createdFlowRow.first().locator('button').first();
      await showButton.click();
      await page.waitForURL(/\/flows\//, { timeout: 10000 });
      await expect(page.locator('text=Flow Details')).toBeVisible({ timeout: 10000 });

      await waitForProcessorControls(page, flowId);

      let editButton = page.getByRole('button', { name: /^Edit$/ });
      if ((await editButton.count()) === 0) {
        editButton = page.getByRole('link', { name: /^Edit$/ });
      }
      if ((await editButton.count()) === 0) {
        editButton = page.locator('button, a').filter({ hasText: /^Edit$/i });
      }
      await expect(editButton.first()).toBeVisible({ timeout: 5000 });
      await editButton.first().click();

      await page.waitForURL(/\/flows\/[^/]+\/edit$/, { timeout: 10000 });
      const editNameInput = page.locator('#name');
      await expect(editNameInput).toBeVisible({ timeout: 5000 });
      await editNameInput.fill(updatedFlowName);

      const editDescriptionInput = page.locator('textarea[name="description"]');
      if (await editDescriptionInput.count()) {
        await editDescriptionInput.fill(updatedDescription);
      }

      const saveButton = page.getByRole('button', { name: /save/i }).first();
      await expect(saveButton).toBeVisible({ timeout: 5000 });
      await saveButton.click();

      await page.waitForURL(/\/flows\//, { timeout: 10000 });

      if (!/\/flows\/[^/]+$/.test(page.url())) {
        await expect(page.locator('.ant-table-tbody')).toBeVisible({ timeout: 10000 });
        let updatedRow = page.locator('.ant-table-row').filter({ hasText: updatedFlowName });

        if ((await updatedRow.count()) === 0) {
          const paginationNext = page.locator('.ant-pagination-next').first();
          let pageNumber = 0;
          while (pageNumber < 5 && (await updatedRow.count()) === 0) {
            if (await paginationNext.isVisible() && await paginationNext.isEnabled()) {
              await paginationNext.click();
              await page.waitForTimeout(1500);
              updatedRow = page.locator('.ant-table-row').filter({ hasText: updatedFlowName });
            }
            pageNumber += 1;
          }
        }

        await expect(updatedRow).toBeVisible({ timeout: 10000 });
        const showButtonAfterEdit = updatedRow.first().locator('button').first();
        await showButtonAfterEdit.click();
        await page.waitForURL(/\/flows\/[^/]+$/, { timeout: 10000 });
      }

      await expect(page.locator('text=Flow Details')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('body')).toContainText(updatedFlowName, { timeout: 10000 });

      if (flowId) {
        const postEditDetailResponse = await page.request.get(`${API_BASE_URL}/api/v1/flows/${flowId}`);
        expect(postEditDetailResponse.ok()).toBeTruthy();
        const postEditDetailJson = await postEditDetailResponse.json();
        expect(postEditDetailJson?.name).toBe(updatedFlowName);
        if (postEditDetailJson?.description) {
          expect(typeof postEditDetailJson.description).toBe('string');
        }
      }

      const parametersButton = page.locator('button:has-text("Parameters")').first();
      await expect(parametersButton).toBeVisible({ timeout: 10000 });
      await parametersButton.click();

      const modal = page.getByRole('dialog');
      await expect(modal).toBeVisible({ timeout: 10000 });

      const patternRow = modal.locator('tbody tr').filter({ hasText: 'input_pattern' }).first();
      await expect(patternRow).toBeVisible({ timeout: 5000 });

      const rowEditButton = patternRow.locator('button.ant-btn-text').first();
      await rowEditButton.click();

      const valueInput = patternRow.locator('input[placeholder="Parameter value"]').first();
      await expect(valueInput).toBeVisible({ timeout: 5000 });
      await valueInput.fill(updatedPattern);

      const rowSaveButton = patternRow.locator('button.ant-btn-text').first();
      await rowSaveButton.click();

      const modalSave = modal.locator('button:has-text("Save Changes")').first();
      await modalSave.click();

      await expect(page.locator('.ant-notification-notice-message')).toContainText('Parameters Updated', {
        timeout: 15000,
      });
      await dismissNotifications(page);
      await expect(modal).not.toBeVisible({ timeout: 15000 });

      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.locator('text=Flow Details')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('body')).toContainText(updatedPattern.replace('^', '').replace('$', ''));

      const detailResponse = await page.request.get(`${API_BASE_URL}/api/v1/flows/${flowId}`);
      expect(detailResponse.ok()).toBeTruthy();
      const detailJson = await detailResponse.json();
      const patternValue = detailJson?.parameters?.input_pattern;
      const resolvedPattern =
        patternValue && typeof patternValue === 'object' ? patternValue.value : patternValue;
      expect(resolvedPattern).toBe(updatedPattern);

      await waitForProcessorControls(page, flowId);

      let startButton = page.locator('button:has(span.anticon-play-circle)').first();
      if (await startButton.count()) {
        await startButton.click();
      }

      await waitForFlowStatus(page, flowId!, 'running');
      await dismissNotifications(page);

      const firstFileName = `playwright-${testId}-1.txt`;
      const firstHostInput = path.join(filePaths.host.input, firstFileName);
      const firstOutput = path.join(filePaths.host.output, `processed_${firstFileName}`);
      fs.writeFileSync(firstHostInput, 'Playwright E2E file payload 1');

      await waitForFile(firstOutput, true, 40000, 2000);
      await waitForFile(firstHostInput, false, 20000, 2000);

      const pauseButton = page.locator('button:has(span.anticon-pause-circle)').first();
      await expect(pauseButton).toBeVisible({ timeout: 10000 });
      await dismissNotifications(page);
      await pauseButton.click();

      await waitForFlowStatus(page, flowId!, 'stopped');
      await dismissNotifications(page);

      const secondFileName = `playwright-${testId}-2.txt`;
      const secondHostInput = path.join(filePaths.host.input, secondFileName);
      const secondOutput = path.join(filePaths.host.output, `processed_${secondFileName}`);
      fs.writeFileSync(secondHostInput, 'Playwright E2E file payload 2');

      await page.waitForTimeout(5000);
      expect(fs.existsSync(secondHostInput)).toBeTruthy();
      expect(fs.existsSync(secondOutput)).toBeFalsy();

      startButton = page.locator('button:has(span.anticon-play-circle)').first();
      await expect(startButton).toBeVisible({ timeout: 10000 });
      await dismissNotifications(page);
      await startButton.click();

      await waitForFlowStatus(page, flowId!, 'running');
      await dismissNotifications(page);
      await waitForFile(secondOutput, true, 40000, 2000);
      await waitForFile(secondHostInput, false, 20000, 2000);

      const stopButton = page.locator('button:has(span.anticon-pause-circle)').first();
      if (await stopButton.count()) {
        await stopButton.click();
        await waitForFlowStatus(page, flowId!, 'stopped');
      }
    } finally {
      if (flowId) {
        try {
          await page.request.post(`${API_BASE_URL}/api/v1/flows/${flowId}/executions/stop`);
        } catch (error) {
          console.warn(`Failed to stop flow ${flowId} during cleanup:`, error);
        }

        try {
          await page.request.delete(`${API_BASE_URL}/api/v1/flows/${flowId}`);
        } catch (error) {
          console.warn(`Failed to delete flow ${flowId} during cleanup:`, error);
        }
      }

      try {
        if (fs.existsSync(templatePath)) {
          fs.unlinkSync(templatePath);
        }
      } catch (error) {
        console.warn(`Failed to remove template file ${templatePath}:`, error);
      }

      cleanupFileProcessingPaths(filePaths);
    }
  });
});

