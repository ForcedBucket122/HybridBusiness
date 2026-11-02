# Analiza źródeł open-source — 2026-11-02

Analiza statyczna rzeczywiście pobranych źródeł; nie uruchamiano ich aplikacji,
instalatorów, testów ani zależności. Brak deklaracji, że całe repozytoria działają.
Kopie tylko w `%TEMP%/LocalAICompany-analysis-20261102`, poza LocalAICompany.

| Repozytorium | Przejrzany commit | Licencja / ograniczenie |
| --- | --- | --- |
| [CrossWave](https://github.com/guish7423/polsia-fork) | b3f8385eaa6b0a65953f7e85f05e66e02006dfeb | LICENSE: MIT, copyright 2025–2026 guish7423; zgodność praw do odziedziczonego kodu nie jest tu potwierdzona |
| [Babber](https://github.com/okhmat-anton/babber) | a06add68c3405da34c87f4ce0ecafb9dd92bea2f | LICENSE: Apache-2.0; prywatnego submodułu addons_private nie pobierano |
| [Open Polsia](https://github.com/AI-Builder-Club/open-polsia) | c62ba0be3368815dc9011848d96875ef228f1607 | LICENSE: MIT, copyright 2026 open-polsia contributors |
| [PolsiaAI/Polsia](https://github.com/PolsiaAI/Polsia) | 9cd1521b428933db1394b793549be23ac9ad7620 | Brak LICENSE i deklaracji licencji w sprawdzonym pyproject.toml; nie przenosimy kodu |

Adaptacja dotyczy wyłącznie koncepcji. Stan rzeczywiście wdrożony i testy opisuje
[IMPROVEMENTS.md](IMPROVEMENTS.md); poniższa tabela jest porównaniem i decyzją projektową.
Kod LocalAICompany pisany samodzielnie; żadnego
modułu ani fragmentu implementacji nie skopiowano. Źródłowe noty licencyjne pozostają
w niezmienionych klonach. Nie dodajemy Claude CLI, usług płatnych, Redis ani MongoDB.

## Porównanie implementacji

Ścieżki są względne do podanego repozytorium i przypiętego powyżej commita.

| Funkcja | LocalAICompany przed zmianą | Źródło i rzeczywista implementacja | Korzyść | Zmiana lokalna | Ryzyko | Licencja | Decyzja |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Kontekst zadania | tekst celu, opisu, plików; wcześniej dołączana historia modelu | Babber `skills/task_context_build/main.py`: task, komentarze, related_files, parent/subtasks; `skills/project_context_build/main.py`: goals/success_criteria i drzewo | Rozdzielenie celu od zadania i dowodów | Typed ContextBuilder, aktualne pliki, ostatnie testy, błędy, budżet, pozostałe próby | Babber używa `str.startswith` do ścieżek — nie przejmujemy tej ochrony | Apache-2.0 | Dostosować koncepcję |
| Współpraca kroków | zależności w SQLite, raport błędów w opisie | CrossWave `app/services/workflow_engine.py`: kolejność topologiczna, node_states, upstream outputs | Selektywne przekazanie wyników bez całej rozmowy | Dane bezpośrednich zależności i ostatni rzeczywisty raport | W `_execute_agent_node` upstream pobierany przez `get_upstream_outputs(node_id, [], {})`; w tym miejscu wynik jest pusty! | MIT | Dostosować zamiar, nie kopiować implementacji |
| Checkpoint | result.phase / effects_committed, raport testów przed LLM QA | CrossWave `app/core/checkpoint.py`: run/load/save oraz save_to_db/restore_from_db | Nie powtarzać kosztownego LLM ani skutków przy retry | Trwały punkt przed zapisem plików, po testach i przed analizą QA; związany z hashami | Fallback CrossWave w pamięci procesu nie jest trwały; Redis zbędny | MIT | Dostosować do SQLite |
| Supervisor | CEO schema Plan, deterministyczna kolejka | CrossWave `app/agents/supervisor/agent.py`: goal -> decompose_goal -> create_tasks_from_plan -> dependency_graph | Jasna rola planera i zapis planu | Zachować istniejące rozdzielenie; doprecyzować kryteria w kontekście | Sama deklaracja modelu nie sprawdza realizacji | MIT | Zachować lokalny silnik |
| Rejestr narzędzi | jawna lista, Pydantic, uprawnienia roli | CrossWave `app/services/tool_runner.py`: allowlist przy budowie definicji, parser arguments, sekwencyjny dispatcher | Typowane edycje z czytelnym błędem | Exact-match edit_file i kontrola wersji/zmian; brak arbitrary dispatch | Dostępność narzędzia w prompt nie zastępuje autoryzacji wykonania | MIT | Dostosować |
| Ollama | asyncio.Lock, lokalny endpoint, JSON Schema, timeout | Babber `backend/app/llm/ollama.py`: semaphore(1) dla chat, GenerationParams, token metrics | Mniejsze ryzyko kolejki GPU, telemetryka | Zachować pojedynczą inferencję; mierzyć prompt i output, lepsze retry JSON | Stream w tym źródle nie korzysta z tego samego semafora | Apache-2.0 | Dostosować metryki, zachować lokalne ograniczenia |
| Pamięć | nieustrukturyzowane MemoryEntries, substring search | Babber `backend/app/mongodb/services.py:MemoryService`: filtrowanie po agencie i limity; `skills/memory_search/main.py` zawiera tylko komentarz | Typy i selekcja informacji | SQLite: preferencje, obserwowane błędy, próby, sprawdzone rozwiązania; wyszukiwanie tekstowe | Nie ma dowodu działania rozbudowanego search w samym pliku skillu | Apache-2.0 | Własna mała implementacja |
| Autonomia | APScheduler, dzienny limit propozycji, domyślnie off | Babber `backend/app/services/autonomous_runner.py`: persisted run, max_cycles dla trybu cycles, obsługa cancel/error | Stan i ograniczenia cyklu | Wykrywanie braku postępu; nie zwiększać autonomii przed E2E | Tryb continuous nie ma takiego limitu cykli; nie przejmować while True | Apache-2.0 | Tylko ograniczenia i monitoring |
| Ukończenie / kontynuacja | każdy zwrócony wynik etapu bywa COMPLETED | Open Polsia `src/core/worker.ts`: needs_continuation, runToCompletion(maxRuns=5), zachowanie workspace; `src/tools/tasks.ts`: complete/resume/fail | Brak fikcyjnego ukończenia | QA REVIEWED dla uwag; testy not_run/passed/failed osobno; Developer wymagane dowody zmian | complete_task ufa przekazanym artefaktom; lokalnie wymagamy rzeczywistej weryfikacji plików | MIT | Dostosować i zaostrzyć |
| CEO / zakres uprawnień | plany z rozmowy, okresowe propozycje Research | Open Polsia `src/agents/ceo.ts`: read_state, propose, write_report; `src/tools/tasks.ts`: suggested oddzielne od todo | Oddzielenie propozycji od działania | Zachować lokalne zatwierdzenia i limity; żadnego automatycznego wykonania kodu | Reguła z promptu o zgodzie wynikającej z milczenia nie nadaje uprawnień | MIT | Zachować istniejące bramki |
| Pamięć firmy | historia projektowa | Open Polsia `src/core/memory.ts`: company profile/documents/context_graph osobno od rozmowy | Preferencje odseparowane od logów | Typowane lokalne preferencje projektu; wykluczyć stare werdykty QA z bieżącego kontekstu | Brak widocznego ograniczenia objętości loadCompanyContext | MIT | Dostosować |
| Oryginalna orkiestracja | lokalne rzeczywiste pliki i runner | Polsia `celery_app/tasks/agent_tasks.py`: context, run, duration, status/log; `celery_app/worker.py`: Celery | Pomiar etapów i zapis historii | Już obecne, rozwinąć dowody/metryki | status completed po samym return; importowane `app.*` nieobecne w tym drzewie; placeholder w social sweep | Brak deklaracji | Nie kopiować |
| Role biznesowe / harmonogram Polsia | 7 agentów i APScheduler | Polsia `celery_app/tasks/agent_tasks.py`: social/support/ads/finance sweeps; test `tests/unit/test_base_agent.py` odwołuje się do Claude CLI | Potwierdzenie rozdzielenia ról | Zachować lokalne role | To wywołania, nie dowód kompletnych implementacji; kod płatności/social poza zakresem | Brak deklaracji | Pominąć |

## Audyt LocalAICompany i decyzja

Punkt bazowy Git: `fd7c03e`, czyste drzewo przed pracą. Tag:
`checkpoint/before-open-source-improvements-20261102`. Kopia SQLite przez backup API,
źródła i dane w `data/backups/20261102T190826470092Z` (manifest SHA256, integrity_check=ok).
Testy bazowe uruchomione: 55 passed, 2 skipped. Dane i logi zachowano.

Dowód problemu: zatwierdzone testy rzeczywiście wykazały 3 błędy w 4 testach; kolejne
generacje napraw powtarzały kod. Samo wykluczenie pamięci nie zapewniło naprawy — po
przywróceniu Ollama pierwotny plan zatrzymał się na limicie 5. Hipoteza o zakotwiczeniu
w historii jest uzasadniona konstrukcją promptu, ale nie jest jedyną udowodnioną przyczyną.
Nie zachowano tokenizacji dawnych promptów, więc nie twierdzimy, że doszło do ucięcia.

Priorytet implementacji: zadaniowy kontekst z aktualnymi hashami, edycje fragmentów,
strukturalny raport błędów, wykrywanie braku rzeczywistych zmian, checkpointy i dowody
w istniejącym panelu. Duża rozbudowa autonomii odłożona do zaliczenia prawdziwego E2E.
