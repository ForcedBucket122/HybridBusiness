import { test, expect } from '@playwright/test'

test('QA shows actual failure separately from review and loads persisted history', async ({page}) => {
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/stream')) return route.abort()
    let data: unknown = []
    if (path === '/api/health') data = {ollama:{online:true,models:[],missing:[]},mode:'HYBRID'}
    if (path === '/api/tasks') data = [{id:'qa1',project_id:'p',title:'Weryfikacja',agent:'qa',status:'REVIEWED',attempts:1,iteration:1,error:null,dependencies:[],result:{
      qa_report:{test_state:'failed',outcome:'changes_requested',issues:[{file:'main.py',line:23,kind:'AttributeError',message:'dict has no append',source:'runner'}]},
      tests:{test_count:4,exit_code:1,passed:false,output:'FAILED (errors=3)'}
    }}]
    if (path.endsWith('/checkpoints')) data = [{stage:'tests_executed',updated_at:'2026-11-02T19:00:00Z',payload:{test_count:4}}]
    if (path.endsWith('/runs')) data = [{id:'run1',status:'REVIEWED',started_at:'2026-11-02T19:00:00Z'}]
    await route.fulfill({json:data})
  })
  await page.goto('/')
  await page.getByRole('button',{name:'Zadania',exact:true}).click()
  await expect(page.getByText('Testy: niezaliczone',{exact:true})).toBeVisible()
  await expect(page.getByText('Przekazano do poprawek',{exact:true})).toBeVisible()
  await page.getByText('Problemy QA (1)',{exact:true}).click()
  await expect(page.getByText('main.py:23 · AttributeError')).toBeVisible()
  await page.getByText('Historia prób i zapisane etapy',{exact:true}).click()
  await expect(page.getByText(/tests_executed ·/)).toBeVisible()
})

test('dashboard, project creation, chat and task status use API data', async ({page}) => {
  let projects: unknown[] = [{id:'old',name:'Previous project',status:'FAILED',description:'',created_at:new Date().toISOString()}]
  let messages: unknown[] = []
  let tasks: unknown[] = []
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (path.endsWith('/stream')) return route.abort()
    let data: unknown = []
    if (path === '/api/health') data = { ollama:{online:true,models:['qwen3:4b'],missing:[]},mode:'HYBRID',active_task:null }
    if (path === '/api/projects') {
      if (route.request().method()==='POST') projects=[{ id:'a'.repeat(32),name:'Browser project',status:'IDLE',description:'',created_at:new Date().toISOString() }]
      data = route.request().method()==='POST'?projects[0]:projects
    }
    if (path === '/api/projects/'+'a'.repeat(32)) data = {...projects[0] as object,files:[],artifacts:[]}
    if (path.endsWith('/chat')) {
      if (route.request().method()==='POST') {
        const body=route.request().postDataJSON()
        expect(body.request_id).toBeTruthy()
        messages=[{id:'msg',role:'user',content:body.content,created_at:new Date().toISOString()}]
        tasks=[{id:'t1',project_id:'a'.repeat(32),title:'Plan testowy',agent:'ceo',status:'PENDING',attempts:0,iteration:0,error:null,result:{},dependencies:[]}]
      }
      data=route.request().method()==='POST'?tasks[0]:messages
    }
    if (path==='/api/tasks') data=tasks
    await route.fulfill({json:data})
  })
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Twoja firma. Lokalnie.'})).toBeVisible()
  await page.getByRole('button',{name:'Nowy projekt',exact:true}).click()
  await page.getByLabel('Nazwa projektu').fill('Browser project')
  await page.getByRole('button',{name:'Utwórz projekt',exact:true}).click()
  await expect(page.getByLabel('Projekt rozmowy')).toHaveValue('a'.repeat(32))
  await page.getByLabel('Wiadomość do CEO').fill('Build the application')
  await page.getByRole('button',{name:'Wyślij',exact:true}).click()
  await expect(page.getByText('Build the application', {exact:true})).toBeVisible()
  await expect(page.getByText('Plan testowy',{exact:true})).toBeVisible()
  await expect(page.getByText('W kolejce',{exact:true})).toBeVisible()
})

test('backend failure is visible and approval requires explicit acknowledgement', async ({page}) => {
  await page.route('**/api/**', route => route.abort())
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('Brak połączenia z backendem')
})

test('approval cannot execute without acknowledgement', async ({page}) => {
  let approved=false
  await page.route('**/api/**', async route => {
    const path=new URL(route.request().url()).pathname
    if(path.endsWith('/stream')) return route.abort()
    let data:unknown=[]
    if(path==='/api/health') data={ollama:{online:true,models:[],missing:[]},mode:'HYBRID'}
    if(path==='/api/approvals') data=[{id:'approval',project_id:'p',task_id:'t',kind:'host_tests',status:approved?'APPROVED':'PENDING',details:{warning:'To NIE jest sandbox.',hashes:{'main.py':'abc'},command:['python','-m','unittest']}}]
    if(path==='/api/approvals/approval') {
      expect(route.request().postDataJSON()).toEqual({approve:true,acknowledge_host_execution:true})
      approved=true; data={status:'APPROVED'}
    }
    await route.fulfill({json:data})
  })
  await page.goto('/')
  await page.getByRole('button',{name:/Zatwierdzenia/}).first().click()
  await expect(page.getByRole('button',{name:'Zatwierdź tę operację'})).toBeDisabled()
  await page.getByRole('checkbox').check()
  await page.getByRole('button',{name:'Zatwierdź tę operację'}).click()
  await expect(page.getByText('Zatwierdzone',{exact:true})).toBeVisible()
})
