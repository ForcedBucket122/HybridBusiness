# Postęp LocalAICompany

Aktualizacja: 2026-11-03 (Europe/Warsaw). Projekt powstał w A:\HybridBusiness.

## 2026-11-03 — deterministyczna bramka QA i nowa próba E2E

**Stan bieżący: poprawki i regresje zakończone; rzeczywisty E2E oczekuje na zgodę
użytkownika na wykonanie konkretnego kodu. Użytkownik zażądał najpierw analizy
bezpieczeństwa i polecił nie wykonywać jeszcze testów. Brak wykonanych testów
tego produktu i ZIP.**

### Diagnoza potwierdzona kodem i zachowanym przebiegiem

- `evidence.qa_report` wcześniej dodawał wszystkie findings/luźne issues modelu do
  listy błędów. Samo `acceptable=false` wystarczało do `changes_requested`, a
  Orchestrator wywoływał `repair()` przed utworzeniem zgody na pierwsze testy.
- `logs/e2e-plain-source-result.json`: QA najpierw zakwestionował
  `LatestTestResult: null`, później podał identyczne expected/actual dla list_tasks.
  Żadnej z tych opinii nie potwierdzał runner. Developer nie mógł formalnie odmówić:
  RepairResult wymagał przynajmniej jednej edycji, a prompt nakazywał poprawianie.
- Bezpośrednie źródło historycznego NO_PROGRESS to `repairs.validate_batch`:
  identyczny hash AST plików Python i brak zmian innych plików. Ta ochrona działała
  prawidłowo; nieprawidłowa była wcześniejsza decyzja o zleceniu naprawy.
- Istniały deduplikacja wewnątrz raportu i limit iteracji, ale brakowało sprawdzenia
  dowodów QA oraz rozpoznania tego samego błędu/kodu w poprzednim cyklu napraw.
- H1–H4 potwierdzono w powyższym zakresie. H5 (JSON utrudnia analizę) i H6
  (pojemność modelu jako przyczyna) nie zostały dowiedzione. Nie zmieniano formatu
  źródeł w kontekście, modeli ani temperatury na podstawie tych hipotez.

### Zmiany

- `backend/app/evidence.py`: osobne `issues` (tylko statyczne/runner), `hypotheses`
  oraz `rejected_findings` z przyczyną odrzucenia. Walidacja expected==actual,
  istniejącego pliku i zakresu linii, normalnego braku LatestTestResult przed
  wykonaniem. Model nie może podszyć się pod source=runner/static. Gdy findings
  istnieją, legacy issues stanowi ich podsumowanie; pełna surowa opinia pozostaje
  zapisana w model_review. Nie stosuje się strip do porównania expected/actual:
  różnica białych znaków może być rzeczywistym błędem.
- `backend/app/orchestrator.py`: automatyczne naprawy tylko dla potwierdzonych
  błędów. Przed testami hipotezy trafiają do zgody wraz z raportem. Po zaliczonych
  testach nierozstrzygnięta hipoteza kończy etap błędem QA_REVIEW_REQUIRED,
  zachowuje wyniki i blokuje Release; jawne retry jest ograniczone i nie wykonuje
  testów ponownie. Same testy nie unieważniają zasadnych uwag QA.
- Identyczny zestaw potwierdzonych błędów przy tym samym AST w tej samej gałęzi
  planu zatrzymuje się z NO_PROGRESS także po restarcie i kosmetycznych zmianach
  README. Fingerprint jest trwały; przegląd zależności ma limit 80. Zachowano
  dotychczasowy limit iteracji, ochronę testów, checkpointy i kontrolę własności.
- `schemas.py`, `repairs.py`, `orchestrator.py`: Developer może zwrócić
  disposition=unconfirmed, edits=[] i uzasadnienie. Zapisuje się checkpoint
  repair_unconfirmed z hashami; etap zatrzymuje się bez zmiany plików i bez
  uznania błędu za naprawiony. Potwierdzony błąd runnera nadal blokuje wydanie.
- `context.py`, `agents.py`: jawny TestExecution z not_run/stale/passed/failed,
  przypomnienie o zgodzie i zakaz traktowania braku testów jako porażki.
  Historyczny wynik z innych hashów pozostaje widoczny jako nieaktualny.
- Dodatkowo ponowna kontrola hashów po odpowiedzi QA analizującej wykonane testy,
  aby zmiana plików podczas inferencji nie mogła zakończyć QA sukcesem.
- `ollama.py`: do checkpointów metryk dodano rzeczywisty load_duration oraz
  użyte num_ctx i keep_alive. Konfiguracja nadal 8192, keep_alive=0, stream=false,
  qwen3:4b / qwen2.5-coder:7b. Zero powoduje zwolnienie modelu po odpowiedzi
  ([dokumentacja Ollama](https://docs.ollama.com/api/chat)). W nowym E2E ładowanie
  trwało CEO 5,35 s, Developer 10,16 s, QA 5,61 s; całe requesty 12,18 / 23,11 /
  8,34 s. To koszt wydajności, nie dowód przyczyny błędów. Bez przełączenia na 30B
  ani zmiany globalnej konfiguracji Ollama; nie pobierano modeli.

### Rzeczywista weryfikacja

- Przed zmianami: **83 passed, 2 skipped**, 17,28 s.
- Testy celowane QA/flow/recovery/improvements/candidates/Ollama: **74 passed**,
  23,10 s. Następnie pełny backend: **99 passed, 2 skipped, 0 failed**, 23,67 s.
  Pominięte: opt-in live oraz tworzenie symlinków bez uprawnień Windows.
  Pozostało wcześniejsze ostrzeżenie Starlette/httpx; bez instalacji zależności.
- Dodano `tests/test_qa_evidence.py` (16 przypadków). Odtwarza sprzeczne raporty,
  brak pliku/linii, podszywanie się pod runner, brak i nieaktualność testów,
  niepotwierdzoną naprawę, identyczne cykle po odtworzeniu workera, zmianę plików
  podczas QA oraz blokadę Release przy nierozstrzygniętych hipotezach.
- Zaufana, jawnie napisana fixture przeszła prawdziwy runner: wykryte odejmowanie
  zamiast dodawania → naprawa → nowa zgoda/hash → test zaliczony → ZIP.
  **To test integracyjny z atrapą modelu, nie zaliczenie produktu z Ollama.**
- Zachowano testy limitu napraw i odtwarzania skutków po restarcie. Ich bodziec
  zmieniono z gołosłownej opinii modelu na rzeczywisty statyczny brak README
  (`tests/test_flow.py`, `tests/test_recovery_runner.py`).
- `npm.cmd run build`: zaliczony. `npm.cmd test`: **4 passed**, 3,9 s w Edge.
  Frontend bez zmian źródłowych. Pierwsze próby narzędzi frontendowych blokował
  systemowy dostęp do katalogów tymczasowych; po zatwierdzonym rozszerzeniu
  uprawnień polecenia przeszły. Stare raporty testów zachowano w
  `logs/frontend-test-results-before-qa-fix-20261103`.
- `git diff --check`: bez błędów. Kopia sprzed zmian z manifestem i SQLite:
  `data/backups/20261103T205631242904Z`. Nie usunięto dawnych projektów/historii.

### Punkt wznowienia rzeczywistego E2E

- Projekt `5685e12b142044d1a8b9c3b0029265bd`, „E2E QA evidence - integer adder”.
  CEO i Developer COMPLETED, QA WAITING_APPROVAL, Release PENDING. Jedna generacja
  Developera, bez korekt składni i bez automatycznych napraw z opinii QA.
- main.py i test_main.py przechodzą ast.parse; inspect_project nie wykazał błędów
  strukturalnych, znalazł 7 funkcji testowych oraz README. Model QA zgłosił trzy
  hipotezy dotyczące pokrycia CLI; są zapisane, nie zostały uznane za wynik testów.
- Ręczny przegląd statyczny wykazał prawdopodobne błędy produktu: testy wywołują
  main z argumentem, ale definicja go nie przyjmuje; assertLogs użyto do print;
  brak importu sys w obsłudze wyjątków; oczekiwanie kodu 1 zamiast typowego 2
  dla błędnych argumentów argparse. To ustalenia z kodu, nie wynik wykonania.
- Zgoda **7f34be7ce2884d8f8bd3b7d1b9f89e2c**, status PENDING, obejmuje:
  - main.py: `c2d66c86d111b2a787b28197d3c5584c5a6a052fcabb8a8409ee6b6a63693835`
  - test_main.py: `1aaf3f50953bd094115315737481448775b91587f1c15186236ab59b2d4da63b`
  - README.md: `342332abaac1e6f14a32ebadce62a6c3f149bc08bbb102450b371b62960e9731`
- Polecenie: projektowy Python `-I -B -m unittest discover -s . -p test*.py -v`,
  limit 120 s, migawka `workspace/runs/<approval-id>`, pełne prawa użytkownika,
  brak izolacji systemowej. Zapytano użytkownika o tę konkretną zgodę. Bez jego
  odpowiedzi nie wolno zatwierdzić API, uruchomić ani importować kodu projektu.
- Trwały stan: `data/qa-e2e-20261103.json`; pełny eksport plików, hashów, zadań,
  zgody, 9 checkpointów i metryk: `logs/qa-e2e-20261103-evidence.json`.
  Panel działa na http://127.0.0.1:8000. Nowy projekt ma 0 wykonanych testów i 0 ZIP.
- Po pytaniu o zgodę użytkownik zażądał najpierw audytu bezpieczeństwa. Wykonano
  wyłącznie odczyt, SHA256 i ast.parse, bez importowania/wykonywania tych plików.
  Ponownie potwierdzono dokładnie 3 pliki oraz zgodność wszystkich hashów.
  main.py importuje tylko argparse, test_main.py unittest i lokalny main.
  Brak jawnego odczytu/zapisu/usuwania plików, uruchamiania procesów, sieci,
  eval/exec/dynamicznych importów. Operacje obejmują arytmetykę, analizę argumentów,
  stdout/stderr, wyjątki i asercje. Zaufany runner uruchomi jeden proces Python
  oraz zapisze log w workspace/runs/<approval-id>-test-output.log (obok migawki);
  nie jest mechanizmem izolacji. Raport: `logs/qa-e2e-20261103-security.json`.
  API potwierdziło PENDING, brak wyników testów i brak katalogu wykonania zgody.
- **Następny krok:** po jawnej zgodzie na powyższy identyfikator i hashe użyć
  istniejącego API zatwierdzeń. W razie błędów zweryfikować wynik runnera i
  automatyczne naprawy; każda zmieniona wersja wymaga nowej zgody. Nie ogłaszać
  sukcesu E2E przed zaliczonymi testami właściwych hashów i rzeczywistym ZIP.

## 2026-11-03 — ograniczona próba bez JSON dla pojedynczego pliku

- Wykorzystano poprzednie wyniki; nie powtórzono serii temperatur ani porównań JSON.
  Jedna nowa próba `scripts/diagnose_generation.py --plain-source --task-id
  9b3e4398fda3421fa18f965a6d62af5e` zwróciła poprawny składniowo Python dla ostatniego
  wadliwego kandydata. Brak wykonania kodu. Wynik: 427 tokenów wejścia, 306 wyjścia,
  done_reason=stop, około 7,1 s. Dowód: `logs/generation-diagnosis-20261103T161412Z/`.
- Potwierdzona przyczyna bezpośrednia pozostaje po stronie generowanej treści:
  niekompletny Python pojawia się przed zapisem, przy niewyczerpanym limicie tokenów.
  Wynik nowej próby wskazuje na wpływ sposobu żądania odpowiedzi, ale nie dowodzi,
  że ograniczanie JSON jest jedyną przyczyną (zmieniła się też instrukcja odpowiedzi).
- W istniejącym candidates.py tylko fallback odtwarzający jeden plik otrzymuje
  zwykły Python, bez wymuszonej gramatyki JSON, z temperaturą 0. Silnik ustala ścieżkę;
  model nie wybiera miejsca zapisu. Pozostałe etapy i architektura bez zmian.
  Usuwana jest wyłącznie pełna zewnętrzna otoczka Markdown; ast.parse, kontrola
  hashów, testów, limit trzech korekt i zgoda na wykonanie pozostają obowiązkowe.
- Krótkie testy: `pytest tests/test_candidates.py tests/test_ollama.py
  tests/test_improvements.py -q`: **36 passed**, 6,86 s. Bez pełnej regresji i bez
  ponownego budowania niezmienionego frontendu.
- Jedyny nowy E2E: projekt `a82b8795a5d1496eaad3c87e00015581`. CEO i początkowy
  Developer zakończone; main.py i test_main.py przechodzą ast.parse na używanym Pythonie.
  W tym przebiegu korekty składni nie były potrzebne (candidate_state.corrections_used=0),
  więc działania fallbacku nie należy przypisywać sukcesowi składni tego konkretnego E2E.
- Przepływ nadal **niezaliczony**, tym razem blokada dotyczy QA, nie składni:
  QA 0 zgłosił `LatestTestResult: null` jako błąd, mimo że testy na tym etapie wymagają
  dopiero zgody. QA 1 zgłosił rzekomą różnicę spacji w test_list_tasks. Statyczne porównanie
  funkcji list_tasks i asercji assert_has_calls wskazuje ten sam format
  `0: Task 1 [Pending]` / `1: Task 2 [Done]`; również pola expected i actual w opinii
  modelu są identyczne. Nie jest to dowód wykonania ani zaliczenia testów.
- Developer 2 (`813ace0a87c24a29b89e4afb5f881863`) zakończył FAILED/NO_PROGRESS.
  QA 2 i Release pozostają PENDING za niespełnioną zależnością. Brak nowych zgód,
  wykonanych testów produktu i ZIP. Nie resetowano liczników i nie uruchomiono drugiego E2E.
  Zwięzły dowód, w tym porównane fragmenty: `logs/e2e-plain-source-result.json`.
- Następny krok: doprecyzować kontrakt QA przed testami (brak wyniku przed zgodą nie
  jest wadą kodu), odseparować opinię modelu od rzeczywistych wyników i weryfikować
  sprzeczne znaleziska względem wskazanych fragmentów. Jeśli problem pozostanie,
  wykonać ograniczone porównanie modeli dla QA, np. z już zainstalowanym
  qwen2.5-coder:7b; nie zakładać poprawy bez pomiaru i nie pobierać modeli bez zgody.

## 2026-11-03 — diagnostyka i niezawodność generowania

**Cel końcowy nadal nieosiągnięty. Dalsze próby modelowe zatrzymano zgodnie z limitem
użytkownika. Nie ma nowego zaliczonego wykonania testów produktu ani ZIP.**

### Zabezpieczenie i odtworzenie

- Punkt bazowy Git: `d26e77a` (poprzednie zmiany były już zapisane przez użytkownika;
  drzewo na początku czyste). Nie cofnięto kodu ani danych. Kopia źródeł, SQLite,
  projektów i logów: `data/backups/20261103T155202181235Z`, manifest SHA256,
  SQLite integrity_check=ok.
- Odczytano historyczny rejected_proposal zadania `6ebd39bb5a874c5d81836821a55af167`.
  Dokładny błąd: **unexpected unindent**, nie unexpected indent, `tasks.py:13`.
  Po `    @staticmethod` następowało `def generate_id():` bez wcięcia klasy;
  analogicznie wadliwa była metoda po `@classmethod`. Były też niedozwolone fizyczne
  nowe linie wewnątrz pojedynczo cytowanego napisu menu.
- Round-trip JSON → parser → SourceFile → Workspace.write/read zachował treść 1:1.
  Mechanizm zapisu i exact-match edits nie stosuje dedent ani strip do kodu. Brak
  dowodu, że zapis usuwa spacje. Surowej pierwotnej odpowiedzi sprzed poprzedniej
  sesji nie zachowano; nowe odpowiedzi diagnostyczne zapisano w całości.
- W parserze znaleziono niezależny błąd: globalne usuwanie `<think>...</think>` mogło
  zmienić takie napisy wewnątrz JSON/kodu. Teraz usuwana jest wyłącznie otoczka na
  początku odpowiedzi. To nie była przyczyna historycznego błędu wcięcia.
- ast.parse już istniało przed tą sesją. Brakowało automatycznego, ograniczonego
  powrotu od odrzuconej składni do Developera przed zakończeniem zadania.

### Pomiary prawdziwej Ollama

Backend i Ollama początkowo były wyłączone. Uruchomiono istniejącą instalację
`A:\AI\Ollama\app\ollama.exe`, loopback, istniejący katalog modeli. Nie pobierano,
nie przenoszono modeli i nie zmieniano ich szablonów ani globalnej konfiguracji.
Model: qwen2.5-coder:7b, Q4_K_M, 7.6B; kontekst 8192. Pięć sekwencyjnych prób
diagnostycznych tego samego historycznego pliku, bez wykonywania wygenerowanego kodu:

| Wariant | Wynik ast.parse | Tokeny wyjścia | done_reason |
| --- | --- | --- | --- |
| JSON z content, temperatura 0.2, seed 42 | ten sam unexpected unindent:13; identyczny plik | 641 | stop |
| Ten sam prompt, temperatura 0 | ten sam błąd; identyczny plik | 641 | stop |
| Temperatura 0, repeat_penalty=1.0 | ten sam błąd; identyczny plik | 641 | stop |
| Jawna instrukcja poza JSON, pełne content | nadal unexpected unindent:13 | 664 | stop |
| Jawna instrukcja, kod jako tablica pojedynczych linii | poprawna składnia, poprawione wcięcia | 772 | stop |

Dowody: `logs/generation-diagnosis-20261103T155325Z/` i
`logs/generation-diagnosis-20261103T155450Z/` zawierają report.json, surowe odpowiedzi,
historyczny odrzut i model-info.json. Skrypt: `scripts/diagnose_generation.py`.
To mała próbka diagnostyczna, nie dowód ogólnej skuteczności modelu. Temperatury
produkcyjnej 0.2 nie zmieniono — same zmiany temperatury nie poprawiły badanego przypadku.

### Zmiany ograniczone do naprawy generowania

- `ollama.py` / `schemas.py`: dla kodu Developera transport `path + lines` zastępuje
  długie pole content. Wcięcia zachowuje się dokładnie; jedna pozycja to jedna linia,
  bez osadzonych CR/LF. Wewnątrz aplikacji pozostaje dotychczasowy SourceFile/CodeResult.
  Usuwanie Markdown dotyczy tylko otoczki JSON; kod nie jest automatycznie przeformatowywany.
- `candidates.py` / `orchestrator.py`: pełna propozycja jest sprawdzana przed zapisem.
  SyntaxError wraca do Developera z nazwą pliku, typem, komunikatem, linią, offsetem,
  wadliwym wierszem i całą treścią tego pliku. Pierwsza korekta jest celowana, następne
  mogą zastąpić tylko ten jeden wadliwy plik. Poprawne pliki obok pozostają niezmienione.
- Najwyżej `min(3, max_iterations)` korekty składni na zadanie. Licznik jest zapisany
  przed requestem w candidate_state i nie zeruje się po retry/restart. Każda próba ma
  checkpoint candidate_attempt_N. Błędny kandydat nigdy nie nadpisuje działającego pliku.
  Zachowano kontrolę hashów, zgód, nazw testów, rozmiaru projektu i braku postępu.
- `context.py`: nowe QA nie dostaje starych opinii jako aktualnego ErrorSummary.
  Developer nadal dostaje błędy poprzedniego QA; rzeczywiste wyniki testów są zachowane.
  `tools.py`: wymaganie CLI wynika również z pierwotnego celu użytkownika, nawet jeśli
  CEO nie powtórzył słowa „konsolowa” w kryteriach akceptacji QA.
- Nie dodawano funkcji produktu, zależności, nowych modeli, usług ani większej autonomii.

### Rzeczywiste przebiegi E2E

1. Projekt `03285313dc5c4425b6a36a0099291a03`: CEO ukończył plan. Początkowy kod miał
   SyntaxError w task_manager.py:32 (`'[' was never closed`). Developer dostał dokładny
   odrzut i **naprawił go jedną celowaną korektą**, co potwierdziło ast.parse przed zapisem
   (task `2b909f941d714a47a08fdca6bb153ad0`, candidate_state.valid=true, corrections_used=1).
   Nie była to symulacja. Dalej QA zgłosił brak testów i README, a Developer je dodał.
   Następny QA powtórzył stare zarzuty mimo obecności plików — potwierdzony błąd kontekstu,
   opisany i poprawiony wyżej. Trzecia naprawa zakończyła się NO_PROGRESS. Zachowano plan,
   pliki i historię; nie zmieniono tego statusu na sukces.
2. Po konkretnej poprawce kontekstu QA uruchomiono drugi i ostatni przebieg:
   `6f34c66b00914e838d0395c52bf1e157`. CEO ukończył plan, Developer
   `9b3e4398fda3421fa18f965a6d62af5e` wygenerował niedokończony f-string w tasks.py:37.
   Jedna korekta celowana i dwie pełnego pojedynczego pliku nadal dawały SyntaxError:
   niedomknięty f-string, następnie `'(' was never closed`. Limit 3 zadziałał.
   Workspace tego projektu jest pusty; QA/Release PENDING za niespełnioną zależnością.

W drugim przebiegu wszystkie 4 odpowiedzi Developera zakończyły się `stop`, z liczbą
tokenów wyjścia 484, 87, 407, 405 przy limitach 5650/6000. Nie ma dowodu ucięcia przez
limit tokenów lub timeout. Model sam zakończył poprawny strukturalnie JSON zawierający
niekompletny Python. Zmiana reprezentacji pomogła w jednym badaniu, ale nie rozwiązała
niezawodności. Nie ustalono niskopoziomowej przyczyny zachowania wag/tokenizacji lub
wpływu ograniczania generacji JSON; nie należy przedstawiać jednej z tych hipotez jako faktu.

Eksport rzeczywistych zadań, odpowiedzi, checkpointów, metryk i hashów:
`logs/generation-e2e-20261103.json`. Oba nowe projekty mają **0 zgód i 0 artefaktów**.
Nie wykonano żadnego nowego kodu wygenerowanego przez model. Nie było poprawnego kompletnego
produktu, dla którego należałoby prosić o zgodę na wykonanie testów. Obejrzano rzeczywisty
panel: `logs/e2e-evidence-1793721971197.png`; pokazuje błąd i wszystkie trzy próby.

### Końcowa weryfikacja i granice

- `.venv/Scripts/python.exe -m pytest -q`: **82 passed, 2 skipped**, 16,37 s.
  Pominięte: uprawnienie symlink Windows i opt-in live. Zachowano istniejące testy.
  Nowe regresje odtwarzają wcięcia, trzy realne uszkodzenia f-string, JSON/Markdown,
  zachowanie wcięć w transporcie, dokładne błędy, wadliwe edycje, fallback jednego pliku,
  nietknięte poprawne pliki, zmianę użytkownika i trwały limit po retry.
- `npm.cmd run build`: zaliczony. `npm.cmd test`: **4 passed** w Edge.
- Poprawka zgłoszona podczas pracy: dodano `pyrightconfig.json` z extraPaths=backend
  i środowiskiem .venv, aby analizator edytora rozpoznawał importy app.ollama,
  app.schemas i app.security w scripts/diagnose_generation.py. Wszystkie trzy
  importy zweryfikowano przez runpy w .venv; `--help` działa. Bez wywołania modelu.
- Kontrolowany restart: identyczne raporty przed/po, integrity_check=ok. 4 projekty,
  36 zadań, 27 prób, 45 checkpointów, 1 historyczna zgoda, 0 artefaktów, 30 wiadomości,
  21 wpisów pamięci. `logs/candidate-audit-*-restart-20261103.json`.
- Backend i panel działają na http://127.0.0.1:8000, HYBRID, bez aktywnego zadania.
  Zależności blokują dalsze wykonanie obu nieudanych planów. Nie resetowano ich liczników.
- **Nie potwierdzono funkcjonalności końcowego TODO, zaliczonych testów produktu ani ZIP.**
  Niezależne testy akceptacyjne i izolowany runner pozostają ograniczeniami wcześniejszego MVP.

Następny etap wymaga nowej, uzasadnionej hipotezy diagnostycznej, np. kontrolowanego
porównania generowania jednego pliku poza ograniczaniem JSON z obecnym formatem linii.
Nie kontynuować tych samych retry, nie zwiększać limitów i nie pobierać nowych modeli
bez zgody. Obecna sesja kończy testy na udokumentowanej granicy zgodnie z poleceniem użytkownika.

## Punkt wznowienia z 2026-11-02 — po ulepszeniach open-source

- Ukończono audyt, kopię i analizę statyczną czterech repozytoriów. Źródła i decyzje:
  [OPEN_SOURCE_ANALYSIS.md](OPEN_SOURCE_ANALYSIS.md); szczegółowe zmiany i ograniczenia:
  [IMPROVEMENTS.md](IMPROVEMENTS.md). Nie kopiowano ich kodu ani zależności.
- Dodano strukturalny kontekst Developer/QA, celowane edycje, kontrolę braku postępu,
  raport QA oddzielający opinię od testów, status REVIEWED, typowaną pamięć, metryki
  Ollama i trwałe checkpointy (12. tabela, migracja addytywna).
- Panel pokazuje historię i dowody. Poprawiono wybór nowego projektu podczas
  odświeżania oraz readiness start.ps1 niezależne od dostępności Ollama.
- Końcowa weryfikacja: **67 passed, 2 skipped** backend; **4 passed** Edge;
  TypeScript/Vite build zaliczony. Testy istniejące zachowano.
- Faktyczny restart zachował identyczną treść audytowanych tabel: 2 projekty,
  22 zadania, 17 prób, 4 checkpointy, 1 zgoda, 0 ZIP. SQLite integrity_check=ok.
  Dowody: `logs/runtime-audit-before-restart.json`, `logs/runtime-audit-after-restart.json`.
- Nowy realny E2E: `0a87073016a245c79d05873479265584`, CEO ukończył plan.
  Developer `6ebd39bb5a874c5d81836821a55af167` FAILED po 2 próbach:
  SyntaxError tasks.py:52, następnie IndentationError tasks.py:13. Kontrola składni
  zatrzymała obie propozycje przed zapisem. Druga jest w checkpointcie rejected_proposal.
  QA i Release PENDING za niespełnioną zależnością. Nie wykonano kodu, nie powstała zgoda ani ZIP.
- Stary E2E osiągnął limit 5 napraw. Zachowano całą historię; wcześniejsza zgoda CONSUMED.
- Backend i panel działają na http://127.0.0.1:8000; Ollama lokalna, modele bez zmian.
  Pełny E2E nadal **niezaliczony**. Nie rozbudowywano autonomii przed rozwiązaniem tego problemu.
- Końcowa kopia źródeł (także nowych plików), SQLite i artefaktów:
  `data/backups/20261102T193123011126Z`, manifest SHA256. `git diff --check` bez błędów.

Poniższe sekcje opisują wcześniejsze etapy; bieżący wynik i następny krok mają pierwszeństwo.

## Wykonane

- Python/FastAPI/SQLAlchemy/SQLite: 11 tabel, trwałe zadania, historia, pamięć tekstowa.
- OllamaClient: lokalny endpoint, sprawdzanie modelu i zdalnych aliasów, JSON Schema,
  walidacja Pydantic, ograniczone ponowienia, pojedyncze zapytanie, keep_alive=0.
- CEO -> Developer -> QA -> zgoda -> testy -> Release/ZIP.
- QA może zlecać do 5 iteracji napraw; statusy i zależności kontroluje Python.
- Jawny rejestr narzędzi plikowych, ograniczenia rozmiaru/liczby plików, ochrona ścieżek.
- Zgody jednorazowe związane z SHA256 całego projektu; testy uruchamiane na migawce.
- Ochrona zmienionych plików użytkownika, podgląd różnic przed nadpisaniem.
- Anulowanie, limity prób, odzyskiwanie RUNNING -> INTERRUPTED, blokada drugiego workera.
- Research/Marketing/Finance tworzą lokalne raporty; Release rzeczywisty ZIP z manifestem.
- APScheduler: kolejka i opcjonalne propozycje, limity dzienne zachowane po restarcie.
- Panel React/TypeScript: 7 widoków, SSE, podgląd plików, zgody, ustawienia, błędy połączenia.
- Skrypty setup/start/stop (procesy ukryte, nasłuch wyłącznie loopback).

## Weryfikacja dotychczasowa

- Python 3.14.7, Node 24.21.0, npm 11.19.0, Windows NT 10.0.26200.
- NVIDIA RTX 3060 Ti, 8192 MiB (nvidia-smi).
- Ollama 0.40.13, modele qwen3:4b i qwen2.5-coder:7b dostępne lokalnie.
- Bazowy pytest przed obecną serią: 55 zaliczonych, 2 pominięte (symlink privilege, opcjonalny test live), po dodaniu
  regresji restartu, nadpisywania, wyników testów i prawdziwego runnera.
- Dodatkowy pełny przepływ z prawdziwym runnerem i zaufanym fixture kodu: zaliczony,
  unittest rzeczywiście wykonał 1 test, Release zapisał ZIP.
- npm run build: TypeScript i produkcyjna kompilacja Vite zaliczone.
- Playwright w istniejącym Edge: 3 testy zaliczone (API mockowane tylko w testach).
- start.ps1 uruchomił aplikację; /api/health i oba modele dostępne.
- Osobny test prawdziwej Ollama: 1 zaliczony (54,63 s), rzeczywista odpowiedź qwen3:4b.
- setup.ps1 -SkipInstall, stop.ps1 i start.ps1 wykonane poprawnie; restart zachował
  8 zadań, wiadomości i oczekującą zgodę. Ollama nie została zatrzymana.
- Obejrzano zrzut rzeczywistego dashboardu: logs/dashboard.png. Zrzut rozmowy: logs/live-chat.png.

## Praktyczny E2E — aktualny wynik

- Polecenie ze specyfikacji wysłane przez prawdziwy panel w Edge (scripts/live-ui.mjs).
- Projekt: `8a58aef75bd04a4dbe4d486a2d416aef`, „Praktyczny E2E — Lista zadań”.
- CEO/qwen3:4b przygotował plan, SQLite zapisało 8 etapów.
- Developer/qwen2.5-coder:7b zapisał prawdziwe pliki: task_manager.py (991 B),
  test_task_manager.py (1060 B), README.md (573 B).
- QA/qwen3:4b przeprowadził analizę i skierował testy do WAITING_APPROVAL.
- Zgoda: `8686f8e606294296b5347d7736caaebd`; hashe i polecenie są dostępne w panelu.
- Użytkownik zatwierdził w czacie jednorazowe wykonanie tej wersji testów. Zgoda została
  przekazana do API; runner uruchomił zatwierdzoną migawkę bez zmian w plikach źródłowych.
- Rzeczywisty wynik: 4 testy, 1 zaliczony, 3 błędy, exit code 1; czas runnera 0,21 s.
  Błędy add/remove/mark_as_done wynikają z `AttributeError: 'dict' object has no attribute 'append'`.
  Raport: `workspace/runs/8686f8e606294296b5347d7736caaebd-test-output.log`.
  Wynik i hashe zostały zapisane w SQLite przed interpretacją QA. Zgoda jest CONSUMED.
  Pełny E2E nadal niezaliczony: oczekuje napraw i ponownej weryfikacji; ZIP nie powstał.
- Ręczny przegląd odczytanych plików wykazał prawdziwe błędy: load_tasks zwraca dict,
  a add_task wywołuje append; brak rzeczywistego CLI; testy współdzielą tasks.json.
  Mały model QA nie wykrył tych problemów. Pełnego E2E NIE zaliczono.
- Ulepszono prompty i dodano statyczny test punktu wejścia dla nowych analiz konsolowych.
  Nowe plany scalają kolejne etapy Developera przed QA, aby kod/testy/README powstały razem.
  Historyczny plan i pliki objęte oczekującą zgodą pozostawiono bez zmiany.
- Pełny przepływ z mockiem modelu, kontrolowanym błędem testów, naprawą i ZIP przeszedł
  w testach integracyjnych. Nie jest to równoznaczne z zaliczeniem E2E na prawdziwym modelu.
- Po wykonaniu realnych testów QA przeanalizował raport, a silnik utworzył zadania
  `47a5d444de93463b8008c007d0f15f20` (Developer, Poprawki 1) oraz
  `0d9daae6c91243ffb091a099e921f0f8` (QA, Weryfikacja poprawek 1).
  Zależności dalszych etapów zostały przepięte za nowe QA. To rzeczywiste przekazanie
  błędów do lokalnego Developera, nie symulacja testowa.

## Ograniczenia

- Runner obsługuje Python standard library unittest. Inne stosy wymagają przyszłych runnerów.
- Host runner NIE izoluje kodu. Zgoda nie daje gwarancji bezpieczeństwa.
- Brak publikacji, płatności, wiadomości zewnętrznych, instalacji zależności projektów,
  internetowego researchu, wektorowej pamięci i pełnej maszyny wirtualnej.
- Małe projekty: 100 plików / 2 MB, pojedynczy plik 100 KB, ograniczony kontekst LLM.
- HYBRID i AUTONOMOUS wykonują polecone plany; harmonogram tworzy tylko propozycje.
- Model może wygenerować wadliwy kod. O zaliczeniu testów decyduje rzeczywisty wynik runnera.
- W testach biblioteka Starlette zgłasza ostrzeżenie deprecacji TestClient/httpx;
  nie jest to błąd aplikacji. Migracja transportu testowego pozostaje zadaniem przyszłym.

## Następny krok

Poprawić generowanie początkowego kodu Python na podstawie zachowanego rejected_proposal
z nowego E2E. Sprawdzić celowaną korektę składni bez resetowania liczników historycznych
zadań. Następnie ponowić kontrolowany E2E; wykonanie nowego kodu wymaga konkretnej nowej
zgody związanej z hashami. Szczegóły kolejnego etapu i granic w IMPROVEMENTS.md.
Nie oznaczać wszystkich 18 kryteriów MVP jako zweryfikowanych.
