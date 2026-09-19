import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { FIXTURE_PATH, type TestOrderFixture } from './global-setup.js'

const fixture = JSON.parse(readFileSync(FIXTURE_PATH, 'utf-8')) as TestOrderFixture

test('completes a full order offline, then syncs on reconnect', async ({
  page,
  context,
  request,
}) => {
  await page.goto('/')

  // --- Login and start a BASELINE shift on the fresh test order ---
  await page.getByLabel('Badge').fill('0001')
  await page.getByLabel('PIN').fill('1234')
  await page.getByRole('button', { name: 'Ingresar' }).click()

  await expect(page.getByText(fixture.order_code)).toBeVisible()
  await page.getByRole('radio', { name: /BASELINE/ }).check()
  const orderRow = page.locator('li', { hasText: fixture.order_code })
  await orderRow.getByRole('button', { name: 'Iniciar turno' }).click()

  await expect(page.getByTestId('mode-indicator')).toHaveText('BASELINE')

  // --- Go offline: the rest of the picking flow must work with no network ---
  await context.setOffline(true)

  const [firstLine, secondLine] = fixture.lines

  // Line 1: scan location, scan SKU, confirm quantity — fully offline.
  await completeLine(page, firstLine)
  await expect(page.getByTestId('pending-sync-count')).not.toHaveText(
    'Pendientes por sincronizar: 0',
  )

  // Line 2: scan location and SKU, but stop before confirming quantity —
  // proves the outbox has more than one queued event while still offline.
  await scanInput(page, secondLine.location_barcode)
  await scanInput(page, secondLine.sku_barcode)
  await expect(page.getByLabel('qty-input')).toBeVisible()

  const pendingWhileOffline = await page.getByTestId('pending-sync-count').textContent()
  expect(pendingWhileOffline).not.toBe('Pendientes por sincronizar: 0')

  // --- Reconnect: the outbox should flush without any user action ---
  await context.setOffline(false)
  await expect(page.getByTestId('pending-sync-count')).toHaveText('Pendientes por sincronizar: 0', {
    timeout: 15_000,
  })

  // Finish line 2 now that we're back online.
  await page.getByLabel('qty-input').fill(String(secondLine.expected_qty))
  await page.getByRole('button', { name: 'Confirmar' }).click()

  // Order complete -> back to the login screen.
  await expect(page.getByLabel('Badge')).toBeVisible({ timeout: 10_000 })

  // --- Verify server-side state actually reflects both picks ---
  // (DONE is only reachable once the server has replayed the queued SCAN/QTY
  // events through the real pick machine, WMS commit included — see
  // macenplast.api.events.apply_event.)
  // Absolute URLs: `request`'s baseURL is the frontend (127.0.0.1:5173,
  // for page.goto convenience), not the API (127.0.0.1:8000).
  const loginResponse = await request.post('http://127.0.0.1:8000/auth/login', {
    data: { badge_code: '0001', pin: '1234' },
  })
  const { access_token: token } = (await loginResponse.json()) as { access_token: string }

  const linesResponse = await request.get(
    `http://127.0.0.1:8000/orders/${fixture.order_id}/lines`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  const lines = (await linesResponse.json()) as Array<{ state: string }>
  expect(lines).toHaveLength(fixture.lines.length)
  expect(lines.every((line) => line.state === 'DONE')).toBe(true)
})

async function scanInput(page: import('@playwright/test').Page, code: string): Promise<void> {
  const input = page.getByLabel('scan-input')
  await expect(input).toBeVisible()
  // Not .fill(): the scanner-input hook (useScannerInput) builds its
  // buffer from individual keydown events, which .fill() never fires.
  await input.pressSequentially(code)
  await input.press('Enter')
}

async function completeLine(
  page: import('@playwright/test').Page,
  line: TestOrderFixture['lines'][number],
): Promise<void> {
  await scanInput(page, line.location_barcode)
  await scanInput(page, line.sku_barcode)
  await expect(page.getByLabel('qty-input')).toBeVisible()
  await page.getByLabel('qty-input').fill(String(line.expected_qty))
  await page.getByRole('button', { name: 'Confirmar' }).click()
}
