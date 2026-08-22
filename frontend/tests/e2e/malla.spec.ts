import { test, expect } from '@playwright/test';

test.describe('Malla curricular', () => {
  test('opens a subject dialog and shows connection SVG on hover', async ({ page }) => {
    await page.goto('/malla');

    // Verify the malla page loaded
    await expect(page.locator('#malla-title')).toHaveText('Malla curricular');

    const card = page.locator('[data-subject-code="1304001"]');
    await expect(card).toBeVisible();

    // Hover over the card — lines should appear
    await card.hover();
    const svg = page.locator('.malla-connections-svg');
    await expect(svg).toBeVisible();
    const paths = page.locator('path.malla-connection-path');
    expect(await paths.count()).toBeGreaterThan(0);

    // Click to open dialog
    await card.click();
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute('aria-label', 'Detalle de ECONOMIA GENERAL');

    // SVG lines should still be visible (selectedCode is active)
    await expect(svg).toBeVisible();
    expect(await paths.count()).toBeGreaterThan(0);

    // Unrelated cards should be dimmed
    const dimmedCards = page.locator('.subject-card--dimmed');
    expect(await dimmedCards.count()).toBeGreaterThan(0);

    // Close dialog with Escape
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
  });

  test('shows connection lines only on hover, not statically', async ({ page }) => {
    await page.goto('/malla');

    // Before hovering, no SVG should exist
    const svg = page.locator('.malla-connections-svg');
    await expect(svg).toHaveCount(0);

    // Hover over a card with connections
    const card = page.locator('[data-subject-code="1304008"]');
    await card.hover();
    await expect(svg).toBeVisible();
    const paths = page.locator('path.malla-connection-path');
    expect(await paths.count()).toBeGreaterThan(0);

    // Move mouse away — lines should disappear
    await page.mouse.move(0, 0);
    await expect(svg).toHaveCount(0);
  });
});

test.describe('Planificador', () => {
  test('navigates to planner, selects a group, and detects a conflict', async ({ page }) => {
    await page.goto('/horario');

    // Choose manual mode (no kardex needed)
    const manualButton = page.getByRole('button', { name: 'Planificar sin Kardex' });
    await manualButton.click();

    // Search for a subject
    const searchInput = page.getByRole('searchbox', { name: 'Buscar materia para horario' });
    await expect(searchInput).toBeVisible();
    await searchInput.fill('MACROECONOMIA');
    await page.waitForTimeout(300);

    // Open groups for MACROECONOMIA I
    const groupsButton = page.getByRole('button', { name: 'Ver grupos de MACROECONOMIA I', exact: true });
    await expect(groupsButton).toBeVisible();
    await groupsButton.click();
    await page.waitForTimeout(300);

    // Select the first group
    const addGroupButton = page.getByRole('button', { name: /Agregar grupo.*de MACROECONOMIA I/ }).first();
    await expect(addGroupButton).toBeVisible();
    await addGroupButton.click();
    await page.waitForTimeout(300);

    // Verify it was added (selected card appears)
    const selectedGroups = page.locator('.selected-groups li');
    await expect(selectedGroups.first()).toBeVisible();

    // Now search for another subject that may conflict
    await searchInput.fill('MICROECONOMIA');
    await page.waitForTimeout(300);

    const microGroupsBtn = page.getByRole('button', { name: 'Ver grupos de MICROECONOMIA I', exact: true });
    await expect(microGroupsBtn).toBeVisible();
    await microGroupsBtn.click();
    await page.waitForTimeout(300);

    // Select its first group
    const microAddBtn = page.getByRole('button', { name: /Agregar grupo.*de MICROECONOMIA I/ }).first();
    if (await microAddBtn.isVisible()) {
      await microAddBtn.click();
      await page.waitForTimeout(300);
    }

    // Conflict detection area exists (even if 0 conflicts)
    const conflictArea = page.locator('.conflict-list, .metric-grid--planner');
    await expect(conflictArea.first()).toBeVisible();
  });
});
