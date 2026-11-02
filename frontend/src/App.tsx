import { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, ArrowDownToLine, ArrowRight, Bot, Boxes, Check, ChevronRight, Circle, FileCode2, Folder, LayoutDashboard, ListTodo, MessageSquare, Plus, Radio, RefreshCw, Send, Settings2, ShieldCheck, Sparkles, Terminal, X } from 'lucide-react'
import { api } from './api'
import { TaskEvidence } from './TaskEvidence'
import type { Agent, Approval, Event, Health, Message, Project, Settings, Task } from './types'

const navigation = [ ['Dashboard', LayoutDashboard], ['CEO Chat', MessageSquare], ['Projekty', Folder], ['Zadania', ListTodo], ['Agenci', Bot], ['Zatwierdzenia', ShieldCheck], ['Ustawienia', Settings2] ] as const
const labels: Record<string,string> = { PENDING: 'W kolejce', RUNNING: 'W trakcie', COMPLETED: 'Zakończone', FAILED: 'Błąd', WAITING_APPROVAL: 'Wymaga zgody', CANCELLED: 'Anulowane', INTERRUPTED: 'Przerwane', IDLE: 'Gotowy', ACTIVE: 'Aktywny', APPROVED: 'Zatwierdzone', CONSUMED: 'Wykorzystane', REJECTED: 'Odrzucone', EXPIRED: 'Wygasłe' }
const date = (s: string) => new Date(s).toLocaleString('pl-PL', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' })
function Badge({ status }: { status: string }) { return <span className={'badge ' + status.toLowerCase()}><Circle size={6} fill="currentColor" />{status === 'REVIEWED' ? 'Przekazano do poprawek' : labels[status] || status}</span> }

export default function App() {
  const [page, setPage] = useState('Dashboard')
  const [projects, setProjects] = useState<Project[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [events, setEvents] = useState<Event[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [selected, setSelected] = useState(localStorage.getItem('localai-project') || '')
  const [detail, setDetail] = useState<Project | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [draft, setDraft] = useState('')
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [connected, setConnected] = useState(false)
  const [file, setFile] = useState<{ path: string; content: string } | null>(null)
  const [ack, setAck] = useState<Record<string,boolean>>({})
  const [agentFilter, setAgentFilter] = useState('')
  const end = useRef<HTMLDivElement>(null)
  const selectedRef = useRef(selected)
  const refreshSequence = useRef(0)
  selectedRef.current = selected

  const refresh = useCallback(async () => {
    const sequence = ++refreshSequence.current
    const requestedProject = selectedRef.current
    try {
      const [p,t,a,g,e] = await Promise.all([api<Project[]>('/projects'), api<Task[]>('/tasks'), api<Approval[]>('/approvals'), api<Agent[]>('/agents'), api<Event[]>('/events')])
      if (sequence !== refreshSequence.current || requestedProject !== selectedRef.current) return
      setProjects(p); setTasks(t); setApprovals(a); setAgents(g); setEvents(e)
      const id = selectedRef.current
      if (id && p.some(x => x.id === id)) {
        const [d,m] = await Promise.all([api<Project>('/projects/' + id), api<Message[]>('/projects/' + id + '/chat')])
        if (selectedRef.current === id) { setDetail(d); setMessages(m) }
      } else if (p.length) { setSelected(p[0].id) }
    } catch (e) { setError((e as Error).message) }
  }, [])
  useEffect(() => {
    void refresh()
    const updateHealth = () => api<Health>('/health').then(setHealth).catch(e => { setHealth(null); setError(e.message) })
    void updateHealth()
    let timer: ReturnType<typeof setTimeout> | undefined
    const stream = new EventSource('/api/events/stream')
    stream.onopen = () => setConnected(true)
    stream.onerror = () => setConnected(false)
    stream.onmessage = () => { if (timer) clearTimeout(timer); timer = setTimeout(() => { void refresh(); void updateHealth() }, 200) }
    const polling = setInterval(() => { void refresh(); void updateHealth() }, 15000)
    return () => { stream.close(); clearInterval(polling); if (timer) clearTimeout(timer) }
  }, [refresh])
  useEffect(() => { localStorage.setItem('localai-project', selected); setDetail(null); setMessages([]); void refresh() }, [selected, refresh])
  useEffect(() => { if (page === 'Ustawienia') api<Settings>('/settings').then(setSettings).catch(e => setError(e.message)) }, [page])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [messages.length])
  async function action(fn: () => Promise<unknown>) {
    setBusy(true); setError(''); setNotice('')
    try { await fn(); await refresh() } catch(e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  function selectProject(id: string, target = 'CEO Chat') { selectedRef.current = id; setSelected(id); setPage(target) }
  const pending = approvals.filter(a => a.status === 'PENDING')
  const running = tasks.find(t => t.status === 'RUNNING')
  const projectTasks = tasks.filter(t => t.project_id === selected)
  const openProjects = projects.filter(p => ['ACTIVE','WAITING_APPROVAL'].includes(p.status))
  const submitChat = () => action(async () => {
    if (!selected) throw new Error('Najpierw utwórz lub wybierz projekt.')
    await api('/projects/' + selected + '/chat', 'POST', { content: draft.trim(), request_id: crypto.randomUUID() }); setDraft('')
  })
  const taskCards = (items: Task[]) => items.length ? <div className="task-list">{items.map(t => <article className="task" key={t.id}>
    <div className={'avatar small ' + t.agent}>{t.agent.slice(0,2).toUpperCase()}</div>
    <div className="task-content"><div className="row"><strong>{t.title}</strong><Badge status={t.status}/></div><div className="muted">{t.agent} <span>·</span> próba {t.attempts} <span>·</span> poprawka {t.iteration}</div>
      {t.error && <p className="inline-error">{t.error}</p>}
      <TaskEvidence task={t}/>
      {Object.keys(t.result).length > 0 && <details><summary>Rezultat etapu</summary><pre>{JSON.stringify(t.result,null,2)}</pre></details>}
      {t.dependencies.length > 0 && <small>Zależności: {t.dependencies.map(id => tasks.find(x => x.id === id)?.title || id.slice(0,8)).join(', ')}</small>}
    </div><div className="task-actions">
      {['FAILED','INTERRUPTED'].includes(t.status) && <button aria-label={'Ponów ' + t.title} disabled={busy} onClick={() => void action(() => api('/tasks/'+t.id+'/retry','POST'))}><RefreshCw size={15}/></button>}
      {t.status === 'PENDING' && health?.mode === 'MANUAL' && <button disabled={busy} onClick={() => void action(() => api('/tasks/'+t.id+'/run','POST'))}>Uruchom</button>}
      {['PENDING','RUNNING','WAITING_APPROVAL','INTERRUPTED'].includes(t.status) && <button aria-label={'Anuluj ' + t.title} disabled={busy} onClick={() => void action(() => api('/tasks/'+t.id+'/cancel','POST'))}><X size={15}/></button>}
    </div></article>)}</div> : <Empty text="Nie ma jeszcze zadań. Polecenie w CEO Chat utworzy plan pracy."/>

  return <div className="shell">
    <aside className="sidebar"><a className="brand" href="#" onClick={e => { e.preventDefault(); setPage('Dashboard') }}><span className="brand-mark"><Boxes size={24}/></span><span>LocalAI<span className="brand-light">Company</span><small>YOUR LOCAL AI WORKSPACE</small></span></a>
      <div className="workspace-label">PRZESTRZEŃ ROBOCZA</div><nav>{navigation.map(([name,Icon]) => <button key={name} className={page === name ? 'nav-item active' : 'nav-item'} onClick={() => { setPage(name); setAgentFilter('') }}><Icon size={19}/>{name}{name === 'Zatwierdzenia' && pending.length > 0 && <b className="count">{pending.length}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="local-card"><span className={'status-dot ' + (health?.ollama.online ? 'online' : '')}/><div><strong>{health?.ollama.online ? 'Ollama połączona' : 'Ollama niedostępna'}</strong><small>Lokalna inferencja · 1 zadanie</small></div></div><div className="footnote"><ShieldCheck size={14}/> Twoje dane. Twój komputer.</div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/><span>{page}</span></div><div className="top-status"><span className="mode">{health?.mode || 'LOCAL'}</span><span className={'status-dot '+(connected?'online':'')}/>{connected ? 'Aktualizacje na żywo' : 'Ponowne łączenie…'}</div></header>
    <main><div className="page-heading"><div><div className="eyebrow">LOCAL OPERATIONS / {page === 'Dashboard' ? 'OVERVIEW' : page.toUpperCase()}</div><h1>{page === 'Dashboard' ? 'Twoja firma. Lokalnie.' : page}</h1><p>{({Dashboard:'Od pierwszego pomysłu do sprawdzonego produktu. Wszystko pod Twoją kontrolą.', 'CEO Chat':'Określ cel. CEO przygotuje plan i przekaże pracę zespołowi.', Projekty:'Pliki, wyniki i historia każdego produktu w jednym miejscu.', Zadania:'Rzeczywisty stan kolejki i rezultat każdego etapu.', Agenci:'Siedem ról. Lokalne modele. Jasny podział odpowiedzialności.', Zatwierdzenia:'Sprawdź przygotowaną operację, zanim pozwolisz ją wykonać.', Ustawienia:'Modele, limity i zakres autonomii Twojego zespołu.'} as Record<string,string>)[page]}</p></div><button className="primary" onClick={() => setCreating(true)}><Plus size={17}/> Nowy projekt</button></div>
    {error && <div role="alert" className="alert error"><span>{error}</span><button aria-label="Zamknij błąd" onClick={() => setError('')}><X size={16}/></button></div>}
    {notice && <div role="status" className="alert success">{notice}</div>}
    {pending.length > 0 && page !== 'Zatwierdzenia' && <button className="approval-banner" onClick={() => setPage('Zatwierdzenia')}><ShieldCheck size={18}/><span>{pending.length} operacji czeka na Twoją decyzję</span><ArrowRight size={17}/></button>}

    {page === 'Dashboard' && <>
      <div className="stats">{[[Folder,'Projekty',projects.length,`${openProjects.length} aktywnych`],[Activity,'Aktywne zadania',tasks.filter(t => ['RUNNING','PENDING'].includes(t.status)).length,'Trwała kolejka SQLite'],[Check,'Zakończone zadania',tasks.filter(t => t.status === 'COMPLETED').length,'Zapisane rezultaty'],[Bot,'Aktywny agent',running?.agent || '—',running ? 'Wykonuje zadanie' : 'Zespół gotowy do pracy']].map(([Icon,title,value,sub]) => { const I = Icon as typeof Folder; return <div className="stat" key={String(title)}><div className="stat-label">{String(title)}<I size={18}/></div><div className="stat-value">{String(value)}</div><small>{String(sub)}</small></div> })}</div>
      <div className="dashboard-grid"><section className="panel"><div className="section-title"><h2>Projekty w przestrzeni</h2><button className="text-button" onClick={() => setPage('Projekty')}>Wszystkie <ArrowRight size={14}/></button></div>{projects.length ? projects.slice(0,4).map(p => <button className="project-row" key={p.id} onClick={() => selectProject(p.id)}><span className="folder-icon"><Folder size={21}/></span><span className="grow"><strong>{p.name}</strong><small>{date(p.created_at)}</small></span><Badge status={p.status}/><ChevronRight size={17}/></button>) : <div className="welcome"><div className="welcome-icon"><Sparkles size={28}/></div><h3>Wszystko zaczyna się od pomysłu</h3><p>Utwórz projekt i opisz, co chcesz zbudować.<br/>Twój lokalny zespół zajmie się kolejnymi etapami.</p><button className="primary" onClick={() => setCreating(true)}>Utwórz pierwszy projekt <ArrowRight size={16}/></button></div>}</section>
      <section className="panel activity"><div className="section-title"><h2>Dziennik aktywności</h2><Radio size={17}/></div>{events.length ? events.slice(0,7).map(e => <div className="event" key={e.id}><span className="event-dot"/><div><p>{e.message}</p><small>{date(e.created_at)} · {e.kind}</small></div></div>) : <Empty text="Tutaj pojawią się zdarzenia zapisane przez backend."/>}</section></div>
      <section className="panel team-panel"><div className="section-title"><h2>Twój zespół AI</h2><span className="muted">Modele ładowane sekwencyjnie</span></div><div className="team-strip">{agents.map(a => <button key={a.id} onClick={() => { setPage('Agenci'); setAgentFilter(a.id) }}><span className={'avatar '+a.id}>{a.name.slice(0,2).toUpperCase()}</span><strong>{a.name}</strong><small>{running?.agent === a.id ? 'Pracuje' : 'Gotowy'}</small></button>)}</div></section>
    </>}

    {page === 'CEO Chat' && <div className="chat-layout"><section className="panel chat-panel"><div className="chat-header"><div className="avatar ceo">CE</div><div><strong>CEO Agent</strong><small>Planowanie · {agents.find(a => a.id === 'ceo')?.model}</small></div><select aria-label="Projekt rozmowy" value={selected} onChange={e => setSelected(e.target.value)}><option value="" disabled>Wybierz projekt</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
      <div className="messages">{!messages.length && <div className="chat-empty"><MessageSquare size={32}/><h3>Co dziś zbudujemy?</h3><p>Opisz rezultat i kryteria ukończenia. Model przygotuje plan, a silnik zapisze zadania i pliki.</p><button className="suggestion" onClick={() => setDraft('Utwórz prostą aplikację konsolową Python do zarządzania listą zadań. Aplikacja ma pozwalać dodawać zadania, usuwać zadania, oznaczać je jako wykonane i zapisywać dane w pliku JSON. Przygotuj testy jednostkowe oraz instrukcję uruchomienia.')}>Aplikacja do listy zadań w Pythonie <ArrowRight size={14}/></button></div>}{messages.map(m => <article className={'message '+(m.role === 'user' ? 'user' : '')} key={m.id}><div className="message-meta">{m.role === 'user' ? 'Ty' : m.role.toUpperCase()}<time>{date(m.created_at)}</time></div><div className="message-body">{m.content}</div></article>)}<div ref={end}/></div>
      <form className="composer" onSubmit={e => { e.preventDefault(); if (draft.trim()) void submitChat() }}><textarea aria-label="Wiadomość do CEO" placeholder="Opisz swój pomysł lub zadanie…" value={draft} onChange={e => setDraft(e.target.value)} maxLength={12000}/><div><small><ShieldCheck size={13}/> Kod uruchamia się dopiero po Twojej zgodzie</small><button className="primary" disabled={busy || !selected || !draft.trim()} type="submit"><Send size={16}/> Wyślij</button></div></form></section><section className="panel chat-plan"><div className="section-title"><h2>Plan i wykonanie</h2><ListTodo size={18}/></div>{taskCards([...projectTasks].reverse())}</section></div>}

    {page === 'Projekty' && <div className="projects-layout"><section className="panel project-picker"><div className="section-title"><h2>Wszystkie projekty</h2><span className="count">{projects.length}</span></div>{projects.map(p => <button className={'project-row '+(selected===p.id?'selected':'')} key={p.id} onClick={() => setSelected(p.id)}><Folder size={19}/><div className="grow"><strong>{p.name}</strong><small>{labels[p.status] || p.status}</small></div><ChevronRight size={16}/></button>)}{!projects.length && <Empty text="Utwórz pierwszy projekt."/>}</section><section className="panel">{detail ? <><div className="section-title"><h2>{detail.name}</h2><Badge status={detail.status}/></div><p className="muted">{detail.description || 'Cel projektu jest zapisany w rozmowie z CEO.'}</p><button className="text-button" onClick={() => setPage('CEO Chat')}>Otwórz rozmowę <ArrowRight size={14}/></button><h3 className="subheading">Pliki projektu</h3><div className="file-list">{detail.files?.map(path => <button key={path} onClick={() => void action(async () => setFile(await api('/projects/'+selected+'/files?path='+encodeURIComponent(path))))}><FileCode2 size={17}/>{path}<ChevronRight size={14}/></button>)}</div>{!detail.files?.length && <Empty text="Pliki pojawią się po wykonaniu zadania Developera."/>}<h3 className="subheading">Wydania</h3>{detail.artifacts?.map(a => <a className="artifact" href={'/api/artifacts/'+a.id+'/download'} key={a.id}><ArrowDownToLine size={22}/><div><strong>{a.name}</strong><small>SHA256: {a.sha256.slice(0,24)}…</small></div></a>)}{!detail.artifacts?.length && <p className="muted">Brak gotowych paczek ZIP.</p>}<h3 className="subheading">Historia projektu</h3>{events.filter(e => e.project_id === selected).slice(0,10).map(e => <div className="event" key={e.id}><span className="event-dot"/><div><p>{e.message}</p><small>{date(e.created_at)}</small></div></div>)}</> : <Empty text="Wybierz projekt, aby zobaczyć pliki i wyniki."/>}</section></div>}

    {page === 'Zadania' && <section className="panel"><div className="section-title"><h2>Kolejka zadań</h2><select aria-label="Filtr projektu" value={agentFilter} onChange={e => setAgentFilter(e.target.value)}><option value="">Wszystkie projekty</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>{taskCards(agentFilter ? tasks.filter(t => t.project_id === agentFilter) : tasks)}</section>}

    {page === 'Agenci' && <><div className="agent-grid">{agents.map(a => <button className={'panel agent-card '+(agentFilter===a.id?'chosen':'')} key={a.id} onClick={() => setAgentFilter(a.id)}><div className="row"><span className={'avatar '+a.id}>{a.name.slice(0,2).toUpperCase()}</span><Badge status={running?.agent===a.id?'RUNNING':'IDLE'}/></div><h2>{a.name}</h2><p>{a.role}</p><code>{a.model}</code><small>{a.tools.length ? a.tools.length+' dozwolonych narzędzi' : 'Ustrukturyzowana odpowiedź JSON'}</small></button>)}</div>{agentFilter && <section className="panel"><div className="section-title"><h2>Historia: {agentFilter}</h2></div>{taskCards(tasks.filter(t => t.agent===agentFilter))}</section>}</>}

    {page === 'Zatwierdzenia' && <div className="approval-list">{!approvals.length && <section className="panel"><Empty text="Brak operacji do zatwierdzenia. Zgody pojawią się po przygotowaniu konkretnych plików."/></section>}{approvals.map(a => <section className="panel approval-card" key={a.id}><div className="section-title"><h2><ShieldCheck size={20}/> {a.kind === 'host_tests' ? 'Wykonanie testów na komputerze' : 'Nadpisanie zmienionych plików'}</h2><Badge status={a.status}/></div><p>{a.details.warning}</p><small>Projekt: {projects.find(p => p.id===a.project_id)?.name || a.project_id}</small>{a.details.command && <pre>{a.details.command.join(' ')}</pre>}<details><summary>Pliki objęte zgodą ({Object.keys(a.details.hashes).length})</summary>{Object.entries(a.details.hashes).map(([path,hash]) => <button className="hash-file" key={path} onClick={() => void action(async () => setFile(await api('/projects/'+a.project_id+'/files?path='+encodeURIComponent(path))))}><FileCode2 size={15}/>{path}<code>{hash.slice(0,16)}</code></button>)}{a.details.diffs && <pre>{JSON.stringify(a.details.diffs,null,2)}</pre>}</details>{a.status === 'PENDING' && <><label className="checkbox"><input type="checkbox" checked={!!ack[a.id]} onChange={e => setAck({...ack,[a.id]:e.target.checked})}/>{a.kind==='host_tests'?'Rozumiem: kod działa z moimi uprawnieniami, bez sandboxa. Sprawdziłem pliki.':'Sprawdziłem proponowane zmiany i zgadzam się na nadpisanie.'}</label><div className="approval-actions"><button className="danger" disabled={busy} onClick={() => void action(() => api('/approvals/'+a.id,'POST',{approve:false}))}><X size={16}/> Odrzuć</button><button className="primary" disabled={busy || !ack[a.id]} onClick={() => void action(() => api('/approvals/'+a.id,'POST',{approve:true,acknowledge_host_execution:!!ack[a.id]}))}><Check size={16}/> Zatwierdź tę operację</button></div></>}</section>)}</div>}

    {page === 'Ustawienia' && settings && <form onSubmit={e => { e.preventDefault(); void action(async () => { await api('/settings','PUT',settings); setNotice('Ustawienia zapisane. Nowe limity dotyczą kolejnych zadań.') }) }}><div className="settings-grid"><section className="panel"><h2>Środowisko lokalne</h2><label>Adres Ollama<input value={settings.ollama_url} onChange={e => setSettings({...settings,ollama_url:e.target.value})}/></label><label>Tryb pracy<select value={settings.mode} onChange={e => setSettings({...settings,mode:e.target.value})}><option>MANUAL</option><option>HYBRID</option><option>AUTONOMOUS</option></select></label><p className="muted">MANUAL: uruchamiasz każdy etap. HYBRID i AUTONOMOUS kontynuują plan zlecony w rozmowie; ryzykowne operacje zawsze wymagają zgody.</p><label className="checkbox"><input type="checkbox" checked={settings.scheduler_enabled} onChange={e => setSettings({...settings,scheduler_enabled:e.target.checked})}/> Okresowe propozycje badawcze</label><p className="muted">Domyślnie wyłączone. Nie uruchamiają implementacji ani kodu. Internetowy research jest niedostępny w tej wersji.</p>{[['schedule_minutes','Odstęp (minuty)',15,1440],['daily_limit','Limit propozycji dziennie',1,10],['max_active_tasks','Limit aktywnych zadań',10,100]].map(([key,title,min,max]) => <label key={String(key)}>{title}<input type="number" min={Number(min)} max={Number(max)} value={Number(settings[key as keyof Settings])} onChange={e => setSettings({...settings,[key]:Number(e.target.value)})}/></label>)}</section><section className="panel"><h2>Modele i generowanie</h2>{Object.entries(settings.models).map(([role,model]) => <label key={role} className="model-setting"><span>{role}</span><input list="models" value={model} onChange={e => setSettings({...settings,models:{...settings.models,[role]:e.target.value}})}/></label>)}<datalist id="models">{health?.ollama.models.map(m => <option key={m} value={m}/>)}</datalist><div className="limits">{[['timeout','Timeout (s)',10,600,1],['max_tokens','Limit tokenów',256,12000,1],['context_size','Kontekst',2048,16384,1],['temperature','Temperatura',0,1,0.1],['max_attempts','Próby zadania / zapytania',1,3,1],['max_iterations','Iteracje poprawek',1,5,1]].map(([key,title,min,max,step]) => <label key={String(key)}>{title}<input type="number" min={Number(min)} max={Number(max)} step={Number(step)} value={Number(settings[key as keyof Settings])} onChange={e => setSettings({...settings,[key]:Number(e.target.value)})}/></label>)}</div><p className="muted">Jedno zapytanie LLM naraz. Modele nie są pobierane automatycznie.</p></section></div><button className="primary save-settings" disabled={busy} type="submit"><Check size={16}/> Zapisz ustawienia</button></form>}
    <footer>LocalAICompany <span>·</span> Lokalna przestrzeń pracy <span>·</span> v0.1</footer>
    </main></div>
    {creating && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="new-project-title"><div className="section-title"><h2 id="new-project-title">Nowy projekt</h2><button aria-label="Zamknij" onClick={() => setCreating(false)}><X size={18}/></button></div><p>Nadaj projektowi nazwę. Cel i wymagania ustalisz w rozmowie z CEO.</p><form onSubmit={e => { e.preventDefault(); void action(async () => { const p=await api<Project>('/projects','POST',{name:newName.trim()}); setNewName(''); setCreating(false); selectProject(p.id) }) }}><label>Nazwa projektu<input autoFocus required maxLength={100} value={newName} onChange={e => setNewName(e.target.value)} placeholder="np. Osobisty menedżer zadań"/></label><button className="primary" type="submit" disabled={busy || !newName.trim()}>Utwórz projekt <ArrowRight size={16}/></button></form></section></div>}
    {file && <div className="modal-backdrop"><section className="modal file-modal" role="dialog" aria-modal="true" aria-label="Podgląd pliku"><div className="section-title"><h2><FileCode2 size={18}/>{file.path}</h2><button aria-label="Zamknij podgląd" onClick={() => setFile(null)}><X size={18}/></button></div><pre>{file.content}</pre></section></div>}
  </div>
}

function Empty({text}:{text:string}) { return <div className="empty"><Terminal size={23}/><p>{text}</p></div> }
