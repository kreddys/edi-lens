import { expect, Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

export interface RegistryBucket {
  id: string;
  name: string;
  description?: string;
}

export const API_BASE_URL = process.env.VITE_API_URL ?? 'http://localhost:8000';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(currentDir, '../../../../../');

export function getRepoRoot(): string {
  return repoRoot;
}

export async function waitForProcessorControls(page: Page, flowId?: string): Promise<void> {
  const startStopButton = page
    .locator('button:has(span.anticon-play-circle), button:has(span.anticon-pause-circle)')
    .first();

  await expect(startStopButton).toBeVisible({ timeout: 15000 });

  const maxAttempts = 6;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const buttonText = await startStopButton.textContent();

    if (!buttonText?.includes('No Processors')) {
      console.log(`Attempt ${attempt}: start/stop button text is "${buttonText?.trim()}"`);
      return;
    }

    console.warn(`Attempt ${attempt}: start/stop button still reports "No Processors"`);

    if (flowId) {
      const detailResponse = await page.request.get(`${API_BASE_URL}/api/v1/flows/${flowId}`);
      if (detailResponse.ok()) {
        const detailJson = await detailResponse.json();
        console.warn(`Flow API processor count: ${detailJson?.processor_count ?? 'unknown'}`);
      } else {
        console.warn(`Failed to fetch flow API details for flow ${flowId}: status ${detailResponse.status()}`);
      }
    }

    if (attempt < maxAttempts) {
      await page.waitForTimeout(3000);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(startStopButton).toBeVisible({ timeout: 15000 });
    }
  }

  await page.screenshot({ path: `test-results/no-processors-${Date.now()}.png`, fullPage: true });
  throw new Error('Start/Stop control never exposed processors; flow remains in "No Processors" state');
}

export async function ensureRegistryBucket(page: Page): Promise<RegistryBucket> {
  const listResponse = await page.request.get(`${API_BASE_URL}/api/v1/registry/buckets/`);
  expect(listResponse.ok()).toBeTruthy();

  const buckets = await listResponse.json();

  if (Array.isArray(buckets) && buckets.length > 0) {
    const bucket = buckets[0] as RegistryBucket;
    console.log(`Using existing registry bucket: ${bucket.name} (${bucket.id})`);
    return bucket;
  }

  const bucketName = `playwright-e2e-bucket-${Date.now()}`;
  console.log(`No registry buckets found. Creating bucket: ${bucketName}`);

  const createResponse = await page.request.post(`${API_BASE_URL}/api/v1/registry/buckets/`, {
    data: {
      name: bucketName,
      description: 'Temporary registry bucket created by Playwright E2E tests.',
    },
  });

  if (!createResponse.ok()) {
    const errorBody = await createResponse.text();
    throw new Error(`Failed to create registry bucket. Status: ${createResponse.status()} Body: ${errorBody}`);
  }

  const createdBucket = (await createResponse.json()) as RegistryBucket;
  console.log(`Created registry bucket for tests: ${createdBucket.name} (${createdBucket.id})`);

  return createdBucket;
}

function isCodexEnvironment(): boolean {
  return (
    fs.existsSync('/opt/codex') ||
    fs.existsSync('/.codex') ||
    (process.env.CODEX ?? '').toLowerCase() === 'true'
  );
}

export interface FileProcessingPaths {
  host: {
    base: string;
    input: string;
    output: string;
    error: string;
  };
  nifi: {
    input: string;
    output: string;
    error: string;
  };
}

export function createFileProcessingPaths(testId: string): FileProcessingPaths {
  const codex = isCodexEnvironment();
  const baseDir = path.join('/tmp/nifi-working/e2e_playwright', testId);

  const hostInput = path.join(baseDir, 'input');
  const hostOutput = path.join(baseDir, 'output');
  const hostError = path.join(baseDir, 'error');

  [baseDir, hostInput, hostOutput, hostError].forEach((dir) => {
    fs.mkdirSync(dir, { recursive: true, mode: 0o777 });
    try {
      fs.chmodSync(dir, 0o777);
    } catch (error) {
      console.warn(`Failed to chmod test directory ${dir}:`, error);
    }
  });

  const normalize = (p: string): string => (codex ? p : p.replace(/\\/g, '/'));

  return {
    host: {
      base: baseDir,
      input: hostInput,
      output: hostOutput,
      error: hostError,
    },
    nifi: {
      input: normalize(hostInput),
      output: normalize(hostOutput),
      error: normalize(hostError),
    },
  };
}

export function cleanupFileProcessingPaths(paths: FileProcessingPaths): void {
  try {
    fs.rmSync(paths.host.base, { recursive: true, force: true });
  } catch (error) {
    console.warn(`Failed to cleanup test directories at ${paths.host.base}:`, error);
  }
}

export async function dismissNotifications(page: Page): Promise<void> {
  const notificationWrapper = page.locator('.ant-notification-notice-wrapper');
  const closeButtons = page.locator('.ant-notification-notice-close');

  try {
    const buttonCount = await closeButtons.count();
    for (let i = 0; i < buttonCount; i += 1) {
      await closeButtons.nth(i).click({ timeout: 1000 });
    }
  } catch (error) {
    console.warn('Failed to click notification close buttons:', error);
  }

  try {
    await notificationWrapper.waitFor({ state: 'detached', timeout: 3000 });
  } catch {
    await page.waitForTimeout(250);
  }
}

export async function waitForFlowStatus(
  page: Page,
  flowId: string,
  expected: 'running' | 'stopped',
  timeoutMs = 30000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  const acceptableRunning = new Set(['running', 'partially_running']);
  const acceptableStopped = new Set(['stopped', 'partially_stopped']);

  while (Date.now() < deadline) {
    const response = await page.request.get(`${API_BASE_URL}/api/v1/flows/${flowId}`);
    if (response.ok()) {
      const json = await response.json();
      const status = String(json?.status ?? '').toLowerCase();
      if (
        (expected === 'running' && acceptableRunning.has(status)) ||
        (expected === 'stopped' && acceptableStopped.has(status))
      ) {
        return;
      }
    }

    await page.waitForTimeout(2000);
  }

  throw new Error(`Flow ${flowId} did not reach ${expected} status within ${timeoutMs}ms`);
}

export async function waitForFile(
  filePath: string,
  shouldExist: boolean,
  timeoutMs = 20000,
  pollIntervalMs = 1000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const exists = fs.existsSync(filePath);
    if (exists === shouldExist) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
  }

  const condition = shouldExist ? 'appear' : 'disappear';
  throw new Error(`File ${filePath} did not ${condition} within ${timeoutMs}ms`);
}

