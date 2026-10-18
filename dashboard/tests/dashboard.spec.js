import { test, expect } from '@playwright/test';

test('login screen is reachable from the production app', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  await expect(page.getByPlaceholder('you@company.com')).toBeVisible();
});

test('authenticated workspace exposes monitoring workflows', async ({ page }) => {
  await page.goto('/');
  await page.getByText('Create an account').click();
  await page.getByPlaceholder('you@company.com').fill(`e2e-${Date.now()}@example.com`);
  await page.getByPlaceholder('••••••••').fill('test-password-123');
  await page.getByPlaceholder('Acme ML').fill('E2E Workspace');
  await page.getByRole('button', {name: 'Create workspace'}).click();
  await expect(page.getByRole('heading', {name: 'Overview'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Run analysis'})).toBeVisible();
  await page.getByRole('button', {name: 'Run analysis'}).click();
  await expect(page.getByRole('heading', {name: 'Run analysis'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Analyze data'})).toBeVisible();
});

test('registration validation is visible', async ({ page }) => {
  await page.goto('/');
  await page.getByText('Create an account').click();
  await expect(page.getByRole('heading', { name: 'Create your workspace' })).toBeVisible();
  await expect(page.getByPlaceholder('Acme ML')).toBeVisible();
});
