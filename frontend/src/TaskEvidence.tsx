import { useState } from 'react'
import { api } from './api'
import type { Task } from './types'

type Issue = { file?: string; line?: number; kind: string; message: string; expected?: string; actual?: string; suggestion?: string; source: string }
type Report = { test_state: string; outcome: string; issues: Issue[] }
type Tests = { test_count: number; exit_code: number; passed: boolean; output: string }
type Saved = { stage: string; updated_at: string; payload: Record<string, unknown> }
type Run = { id: string; status: string; started_at: string; error?: string }

export function TaskEvidence({ task }: { task: Task }) {
  const [saved, setSaved] = useState<Saved[] | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const report = task.result.qa_report as Report | undefined
  const tests = task.result.tests as Tests | undefined
  const changed = task.result.changed_files as string[] | undefined
  async function history() {
    setLoading(true); setError('')
    try {
      const [points, attempts] = await Promise.all([api<Saved[]>('/tasks/' + task.id + '/checkpoints'), api<Run[]>('/tasks/' + task.id + '/runs')])
      setSaved(points); setRuns(attempts)
    } catch (e) { setError((e as Error).message) } finally { setLoading(false) }
  }
  return <div className="task-evidence">
    {report && <p><strong>Testy: {({ not_run: 'nie uruchomiono', passed: 'zaliczone', failed: 'niezaliczone' } as Record<string,string>)[report.test_state]}</strong>
      {' · '}{report.outcome === 'changes_requested' ? 'QA zgłosił poprawki' : report.outcome === 'verified' ? 'Zweryfikowano tę wersję plików' : 'Zakończono tylko przegląd kodu'}</p>}
    {tests && <details><summary>Wynik runnera: {tests.test_count} testów, kod wyjścia {tests.exit_code}</summary><pre>{tests.output}</pre></details>}
    {report?.issues.length ? <details><summary>Problemy QA ({report.issues.length})</summary>{report.issues.map((i, n) => <div className="qa-issue" key={n}>
      <strong>{i.file || 'Projekt'}{i.line ? ':' + i.line : ''} · {i.kind}</strong><small>Źródło: {i.source === 'model' ? 'opinia modelu' : i.source === 'runner' ? 'wykonane testy' : 'analiza statyczna'}</small>
      <p>{i.message}</p>{i.expected && <p>Oczekiwano: {i.expected}</p>}{i.actual && <p>Zaobserwowano: {i.actual}</p>}{i.suggestion && <p>Propozycja: {i.suggestion}</p>}
    </div>)}</details> : null}
    {changed && <p>Zapisane zmiany: {changed.join(', ') || 'brak nowych zmian podczas wznowienia'}.</p>}
    {!!task.result.no_progress && <p className="inline-error">Zatrzymano: propozycja nie wprowadzała rzeczywistej poprawki.</p>}
    <details onToggle={e => { if (e.currentTarget.open && saved === null && !loading) void history() }}>
      <summary>Historia prób i zapisane etapy</summary>
      {loading && <p>Ładowanie…</p>}{error && <p role="alert">{error}</p>}
      {runs.map(r => <p key={r.id}>{new Date(r.started_at).toLocaleString('pl-PL')} · {r.status}{r.error && ' · ' + r.error}</p>)}
      {saved?.map(p => <details key={p.stage}><summary>{p.stage} · {new Date(p.updated_at).toLocaleString('pl-PL')}</summary><pre>{JSON.stringify(p.payload,null,2)}</pre></details>)}
      {saved?.length === 0 && <p>Brak checkpointów dla tego historycznego zadania.</p>}
      <button className="text-button" disabled={loading} onClick={() => void history()}>Odśwież historię</button>
    </details>
  </div>
}
