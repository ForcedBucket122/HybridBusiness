// Read-only inspection of the real UI; never sends a task or approves code.
import { chromium } from '../frontend/node_modules/playwright/index.mjs'
const browser = await chromium.launch({channel:'msedge',headless:true})
try {
  const page = await browser.newPage({viewport:{width:1440,height:1050}})
  await page.goto('http://127.0.0.1:8000')
  await page.getByRole('button',{name:'Zadania',exact:true}).click()
  if (process.env.LOCALAI_E2E_PROJECT) await page.getByLabel('Filtr projektu').selectOption(process.env.LOCALAI_E2E_PROJECT)
  const failed = page.locator('article.task').filter({hasText:process.env.LOCALAI_E2E_ERROR || 'IndentationError'})
  await failed.getByText('Historia prób i zapisane etapy',{exact:true}).click()
  await failed.getByText(/rejected_proposal ·/).waitFor()
  const screenshot = `logs/e2e-evidence-${Date.now()}.png`
  await page.screenshot({path:screenshot,fullPage:true})
  console.log('Verified visible failure, attempts history and rejected_proposal in real UI: '+screenshot)
} finally { await browser.close() }
