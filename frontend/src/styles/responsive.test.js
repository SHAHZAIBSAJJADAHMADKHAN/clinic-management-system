import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, test } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/styles/global.css'), 'utf8')

describe('mobile responsive layout contract', () => {
  test('keeps dashboard navigation and content usable at the mobile breakpoint', () => {
    expect(css).toContain('body { min-width:320px')
    expect(css).toContain('@media(max-width:800px){.foundation-grid{grid-template-columns:1fr}.dashboard-shell{grid-template-columns:1fr}')
    expect(css).toContain('.sidebar nav{display:flex;margin:0;overflow:auto}')
    expect(css).toContain('.dashboard-content{padding:1rem}')
  })

  test('stacks booking, doctor, and admin controls instead of hiding them on mobile', () => {
    expect(css).toContain('.form-grid{grid-template-columns:1fr}')
    expect(css).toContain('.filter-row .field{min-width:0}')
    expect(css).toContain('.admin-form{grid-template-columns:1fr}')
    expect(css).toContain('.search-row{align-items:stretch;flex-direction:column}')
    expect(css).toContain('.auth-shell{grid-template-columns:1fr}')
  })
})
