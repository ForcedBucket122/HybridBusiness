// This starts a real local-model workflow through the browser. It NEVER approves execution.
import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs/promises'
const browser = await chromium.launch({channel:'msedge',headless:true})
try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}})
  await page.goto('http://127.0.0.1:8000')
  await page.getByRole('heading',{name:'Twoja firma. Lokalnie.'}).waitFor()
  await page.screenshot({path:'logs/dashboard.png',fullPage:true})
  await page.getByRole('button',{name:'Nowy projekt',exact:true}).click()
  await page.getByLabel('Nazwa projektu').fill('Praktyczny E2E — Lista zadań')
  await page.getByRole('button',{name:'Utwórz projekt',exact:true}).click()
  const prompt='Utwórz prostą aplikację konsolową Python do zarządzania listą zadań. Aplikacja ma pozwalać dodawać zadania, usuwać zadania, oznaczać je jako wykonane i zapisywać dane w pliku JSON. Przygotuj testy jednostkowe oraz instrukcję uruchomienia.'
  await page.getByLabel('Wiadomość do CEO').fill(prompt)
  const response=page.waitForResponse(r=>r.url().endsWith('/chat')&&r.request().method()==='POST')
  await page.getByRole('button',{name:'Wyślij',exact:true}).click()
  const task=await (await response).json()
  if(!task.id) throw new Error(JSON.stringify(task))
  await fs.writeFile('data/live-e2e.json',JSON.stringify({project_id:task.project_id,task_id:task.id,prompt},null,2))
  await page.screenshot({path:'logs/live-chat.png',fullPage:true})
  console.log(JSON.stringify({project_id:task.project_id,task_id:task.id,status:task.status}))
} finally { await browser.close() }
