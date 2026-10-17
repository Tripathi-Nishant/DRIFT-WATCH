import { test, expect } from '@playwright/test';

test('login screen is reachable from the production app', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await expect(page.getByPlaceholder('Email')).toBeVisible();
});

test('registration validation is visible', async ({ page }) => {
  await page.goto('/');
  await page.getByText('Create an account').click();
  await expect(page.getByRole('heading', { name: 'Create workspace' })).toBeVisible();
  await expect(page.getByPlaceholder('Organization')).toBeVisible();
});
