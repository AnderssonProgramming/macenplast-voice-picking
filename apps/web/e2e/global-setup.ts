import { execFileSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { apiPython } from '../playwright.config.js'

const dirname = path.dirname(fileURLToPath(import.meta.url))

export interface TestOrderLine {
  expected_qty: number
  location_barcode: string
  sku_barcode: string
}

export interface TestOrderFixture {
  order_id: string
  order_code: string
  lines: TestOrderLine[]
}

export const FIXTURE_PATH = path.resolve(dirname, '.e2e-fixture.json')

/**
 * Creates a fresh, unassigned order via `scripts/create_test_order.py`
 * (real seeded SKUs/stock, brand new order) and writes it to a JSON file
 * the specs read from. Not derived from "any seeded order" — this suite
 * can run repeatedly against the same dev database without seeded orders
 * running out (see the same fix in apps/api/tests/test_api_full_flow.py).
 */
export default function globalSetup(): void {
  const apiDir = path.resolve(dirname, '../../api')
  const output = execFileSync(apiPython, ['scripts/create_test_order.py', '2'], {
    cwd: apiDir,
    encoding: 'utf-8',
  })
  const fixture = JSON.parse(output.trim()) as TestOrderFixture
  writeFileSync(FIXTURE_PATH, JSON.stringify(fixture, null, 2))
}
