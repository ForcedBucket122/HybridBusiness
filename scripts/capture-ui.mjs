import { chromium } from '../frontend/node_modules/playwright/index.mjs'
const browser=await chromium.launch({channel:'msedge',headless:true})
try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}})
  await page.goto('http://127.0.0.1:8000')
  await page.getByRole('button',{name:/Zatwierdzenia/}).first().click()
  await page.getByRole('heading',{name:'Wykonanie testów na komputerze'}).waitFor()
  await page.screenshot({path:'logs/approvals.png',fullPage:true})
  await page.getByRole('button',{name:'Dashboard',exact:true}).click()
  await page.setViewportSize({width:390,height:844})
  await page.screenshot({path:'logs/mobile-dashboard.png',fullPage:true})
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)
  if(overflow) throw new Error('Mobile layout has horizontal overflow')
  console.log('Approval screenshot captured; mobile 390px: no horizontal overflow.')
} finally { await browser.close() }
