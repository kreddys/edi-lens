import { test, expect } from '@playwright/test';

const APP_URL = 'http://localhost:5173'; // Or your dev server URL

const sample837P = `ISA*00*          *00*          *ZZ*123456789      *ZZ*11111         *240115*1000*^*00501*000000101*1*P*:~GS*HC*123456789*11111*20240115*1000*101*X*005010X222A1~ST*837*1001*005010X222A1~BHT*0019*00*REF01*20240115*1000*CH~NM1*41*2*TEST SUBMITTER*****46*SUB123~PER*IC*BOB SMITH*TE*5551234567~HL*1**20*1~NM1*85*2*BILLING PROVIDER*****XX*1122334455~N3*100 MAIN ST~N4*ANYTOWN*CA*90210~HL*2*1*22*0~SBR*P*18*******CI~NM1*IL*1*PATIENT*DOE****MI*MEMBERID123~CLM*CLAIM1*550***11:B:1*Y*A*Y*Y*P~LX*1~SV1*HC:99213*150*UN*1~SE*14*1001~GE*1*101~IEA*1*000000101~`;

test.beforeEach(async ({ page }) => {
    await page.goto(APP_URL);
    // Wait for schema dropdown to be populated and potentially initial load
    await expect(page.locator('#schema-select')).not.toBeDisabled();
    // Wait for initial schema load potentially
    await expect(page.locator('text=Loading...')).toHaveCount(0, { timeout: 10000 });
});

test.describe('EDI Lens Basic Flow', () => {
    test('should load, parse EDI, and display structure', async ({ page }) => {
        // 1. Ensure default schema is selected (adjust if default changes)
        await expect(page.locator('#schema-select')).toHaveValue('837P.5010.X222.A1'); // Assumes filename is key

        // 2. Paste EDI into input
        await page.locator('textarea#ediTextArea').fill(sample837P);

        // 3. Wait for processing to finish (check for a specific element in structured view)
        await expect(page.locator('.text-brand-segment-id:text("CLM")')).toBeVisible({ timeout: 10000 }); // Wait for CLM segment header

        // 4. Verify structured view content
        await expect(page.locator('span:text("Billing Provider Loop")')).toBeVisible();
        await expect(page.locator('span:text("Subscriber Loop")')).toBeVisible();
        await expect(page.locator('span:text("Claim Loop")')).toBeVisible();

        // Check a specific segment's presence
        await expect(page.locator('.text-brand-segment-id:text("NM1")')).toHaveCount(3); // Submitter, Billing, Subscriber

        // 5. Verify Raw EDI view content
        await expect(page.locator('.ace_content')).toContainText('ISA*00*');
        await expect(page.locator('.ace_content')).toContainText('SV1*HC:99213*150*UN*1');

        // 6. Check initial state (loops expanded, segments collapsed)
        // Segment header should be visible
        await expect(page.locator('.text-brand-segment-id:text("NM1")').first()).toBeVisible();
        // Element within segment should *not* be visible
        await expect(page.locator('[data-testid="element-NM101"]')).toHaveCount(0); // Assuming ElementDisplay adds testid

        // Expand a segment
        await page.locator('.text-brand-segment-id:text("NM1")').first().click(); // Click first NM1 (submitter)
        await expect(page.locator('[data-testid="element-NM101"]')).toBeVisible(); // Check if element appears
    });

    test('should switch to Schema Definition view', async ({ page }) => {
        await page.locator('button:text("Schema Definition")').click();

        // Verify some schema elements are shown
        await expect(page.locator('span.text-brand-accent:text("ISA_LOOP")')).toBeVisible(); // Loop definition
        await expect(page.locator('span.text-brand-segment-id:text("ISA")')).toBeVisible(); // Segment link
        await expect(page.locator('span.text-brand-segment-id:text("GS")')).toBeVisible();

        // Click to expand a schema segment link
        await page.locator('span.text-brand-segment-id:text("ISA")').click();
        await expect(page.locator('span:text("Authorization Information Qualifier")')).toBeVisible(); // Check element name

        await page.locator('button:text("Parsed Data")').click();
        await expect(page.locator('h3:text("File Delimiters")')).toHaveCount(0); // Should be hidden until data parsed
        await page.locator('textarea#ediTextArea').fill(sample837P);
        await expect(page.locator('h3:text("File Delimiters")')).toBeVisible(); // Check data view reappears
    });

    test('should handle log console interactions', async ({ page }) => {
        await expect(page.locator('div:text("[INFO] App component mounted")')).not.toBeVisible(); // Console closed initially

        // Show logs
        await page.locator('button:text("Show Logs")').click();
        await expect(page.locator('div:text("[INFO] App component mounted")')).toBeVisible();
        await expect(page.locator('div:text("Processing complete")')).not.toBeVisible(); // No processing yet

        // Parse some data
        await page.locator('textarea#ediTextArea').fill(sample837P);
        await expect(page.locator('div:text("Processing complete")')).toBeVisible({ timeout: 10000 });

        // Clear logs
        await page.locator('button:text("Clear")').click();
        await expect(page.locator('div:text("[INFO] App component mounted")')).toHaveCount(0);
        await expect(page.locator('p:text("No log messages yet.")')).toBeVisible();

        // Hide logs
        await page.locator('button:text("Minimize")').click();
        await expect(page.locator('p:text("No log messages yet.")')).not.toBeVisible();
    });

    // Add more E2E tests: schema selection, error states, clearing input, attribution modal, etc.
});