# Postęp LocalAICompany

Aktualizacja: 2026-11-04 (Europe/Warsaw). Projekt powstał w A:\HybridBusiness.

## 2026-11-04 — naprawiony budżet kontekstu, ten sam E2E 2 zakończony Release

**Bloker kontekstu naprawiony bez zwiększania limitów. Projekt
`e445de53b00c45a48732137b4d402d28` ma COMPLETED. Lokalny Developer sam
poprawił produkt; po nowej zgodzie wykonano 7 testów: 7 PASS, 0 FAIL,
0 ERROR, 0 SKIP. QA i Release zakończone, ZIP utworzony i zweryfikowany.**

### Potwierdzona przyczyna i minimalna selekcja

- Odtworzono zachowany przypadek naprawy `8c5f202465914808a09b0f14aacff597`.
  Surowe wyjście runnera (3112 bajtów) było przekazywane trzy razy: jako
  LatestTestResult.output oraz wewnątrz CurrentTask.description i RequiredChanges.
  Pola w zwartej reprezentacji zajmowały odpowiednio 3795, 3733 i 3642 bajty;
  RelevantFiles 7531 bajtów, ProjectGoal 1469, ErrorSummary 1793. To powtórzenia
  dowodów powodowały przekroczenie, a nie nadmierny rozmiar samego produktu.
- Zmiana kodu silnika ograniczona do `backend/app/context.py`: select_context
  zastępuje dokładne, długie kopie wyjścia runnera jawnym odwołaniem do jednego
  pełnego LatestTestResult.output. Obsługuje również historyczną kopię ostatnich
  10000 znaków w opisie naprawy; pełny początek/koniec i wszystkie tracebacki
  pozostają w źródłowym wyniku. Krótkie słowa z stdout nie są usuwane z instrukcji.
- W razie dalszego braku miejsca: zwarta serializacja JSON, pominięcie historycznych
  rozwiązań z pamięci, skrót list zmienionych plików w historii do liczników oraz
  metadane zamiast treści nieistotnej dokumentacji .md/.rst. Preferencje i decyzje,
  wymagania, pełny Python, błędy, wynik walidacji i RejectedProposal są chronione.
  Dokumentacja wskazana w wymaganiach, błędach, zadaniu, dowodach lub kodzie nie
  jest pomijana. Pliki wejściowe .txt nie są uznawane za zbędną dokumentację.
- Każda redukcja jest jawna w ContextSelection i metadanych checkpointu context;
  ścieżki i hashe pominiętej dokumentacji pozostają. Dane trwałe są niezmienne:
  selektor pracuje na kopii. Gdy chroniony rdzeń nadal nie mieści się w budżecie,
  zgłasza błąd z rozmiarami pól; nie obcina końca tekstu ani dowodów.
- Rzeczywisty przypadek: odrzucone wcześniej **22907 bajtów** w zwartej postaci
  (23684 w czytelnej) → **17501 bajtów** po deduplikacji, przy niezmienionym
  limicie **19176** i num_ctx=8192. W tym przypadku wystarczyły wyłącznie dwa
  odwołania zamiast kopii; żadnego pliku, wymogu ani tracebacku nie pominięto.
  Porównanie zapisano w `logs/autonomy-e2e2-context-before-20261104.json`
  i `logs/autonomy-e2e2-context-after-20261104.json`.

### Regresje i weryfikacja silnika

- `tests/fixtures/expense_context_overflow.json`: trwały, samodzielny zapis
  oryginalnego kontekstu 22907 bajtów; źródła produktu są danymi testowymi,
  nie są importowane ani wykonywane przez te regresje.
- `tests/test_context_budget.py`: 10 przypadków obejmujących zachowanie pełnych
  wymagań, kodu i czterech tracebacków, jawne skróty danych drugorzędnych,
  ochronę dokumentacji przywołanej przez wymagania/błędy/kod, ochronę plików
  wejściowych, odrzucenie zbyt dużych dowodów, krótki stdout oraz historyczny
  ogon logu. Regresja integracyjna dochodzi przez rzeczywistą ścieżkę naprawy
  do klienta Ollama z MockTransport, sprawdza num_ctx=8192 i dodatni budżet
  odpowiedzi; nie wykonuje produktu ani wywołania prawdziwego modelu.
- Końcowe testy celowane: **57 PASS, 0 FAIL, 0 SKIP**, 13,11 s.
  Pełny backend: **119 PASS, 0 FAIL, 2 SKIP**, 25,24 s. Pominięte: opt-in live
  i symlinki bez uprawnień Windows. Pozostało wcześniejsze ostrzeżenie Starlette/httpx.
  Wcześniejsze 55/117 zaliczono przed dodaniem dwóch końcowych regresji ochrony
  plików wejściowych i referencji w kodzie; powtórzenie sprawdziło te nowe zabezpieczenia.
  Nie zmieniano compile(), konfiguracji modeli, limitów ani systemu zatwierdzania.

### Kontynuacja istniejącego E2E, bez ręcznych poprawek produktu

- Po testach przeładowano backend i wznowiono to samo zadanie Developer 1
  normalnym retry. Próba 1 nadal dokumentuje błąd budżetu; próba 2 dotarła do
  lokalnego qwen2.5-coder:7b i zakończyła się COMPLETED. Nie resetowano liczników
  i nie dodawano ręcznej propozycji ani dodatkowych wskazówek ratunkowych.
- Model dodał import json w test_main.py, naprawiając NameError. Dodał też
  zbędny drugi import json w main.py; pozostawiono tę niegroźną nadmiarowość,
  aby zachować autorstwo produktu po stronie lokalnego agenta. Kompilacja i QA
  statyczne przeszły; siedem nazw testów zachowano.
- Nowa wersja została wykonana dopiero po jawnej zgodzie użytkownika
  **`6e4d92121f4547dca43bcb979366c782`**, obecnie CONSUMED, dla SHA256:
  - main.py: `e4d843cc2641d8c6f0dc1ed3ac0a127e937cfaeaeebe2b8334b4cde062045619`
  - test_main.py: `091bf5f9a1b78771913ea7f8f784ec3d4f0aedf861c83ec900e8cc3aa3308d5e`
  - README.md: `80bba18468f2ac07355c0b31aa21a15d0961d71fa71d10ad85f5c83690a78200`
- Runner: **7 PASS, exit=0**, 0,42 s (unittest: 0,021 s), pełne wyjście
  zapisane w `workspace/runs/6e4d92121f4547dca43bcb979366c782-test-output.log`.
  QA 1 `014de6022c2b42728c2a043114a6004d`: COMPLETED, outcome=verified.
  Release `52f507dc47a344d1ae9d333e256985a3`: COMPLETED.
- ZIP: `workspace/artifacts/6ff64f6d571d409a8d19334a83b763d7.zip`, SHA256
  **`e3246186985bd8e84f62f56e8faa8c14bac29f5350f7a98776bd0395ebd894ad`**.
  Zweryfikowano CRC, hashe archiwum i plików, ich zgodność ze zgodą i QA oraz
  identyczność wyniku siedmiu testów w VERIFICATION.json. Żadnego kodu ani
  notatek produktu nie poprawiano ręcznie.
- Bilans tego samego projektu: 1 początkowa generacja, 0 korekt składni,
  1 cykl napraw, 2 uruchomienia zadania naprawy (pierwsze bez LLM),
  **1 rzeczywiste żądanie modelu naprawy**, 2 zgody użytkownika,
  **0 ręcznych poprawek produktu**, 1 interwencja w infrastrukturę kontekstu.
  Zachowano 9 TaskRun i 22 checkpointy. Pierwotny eksperyment bez zmiany backendu
  pozostał zatrzymany; ukończenie nastąpiło po osobno zleconej naprawie infrastruktury.
- Pełny eksport po wznowieniu: `logs/autonomy-e2e2-context-fix-result-20261104.json`;
  zgoda, poprawki i kontekst mają osobne snapshoty context-fix-preexecution i approval.
  Porównanie z bazą eksperymentu: w backendzie zmieniono tylko context.py;
  ustawienia i pliki .ignore pozostały identyczne. Backend końcowej wersji działa
  w MANUAL; restart nie ponowił wykonania produktu.

### Granice wyniku

Siedem wygenerowanych testów przeszło, ale nie jest to niezależna, wyczerpująca
walidacja wymagań. Testy nie sprawdzają jawnie wszystkich wariantów (m.in. kwoty
zero/niecałkowite, kategorię z samych spacji, puste list/total, kolejne dodania
przez main ani identyczność zawartości uszkodzonego pliku po odrzuceniu).
Szersze deklaracje pokrycia w wygenerowanym RELEASE.md nie są dodatkowym dowodem.
Naprawa konkretnego NameError przez lokalnego agenta i usunięcie blokera kontekstu
zostały faktycznie potwierdzone. Dalszą pracę nad pokryciem należy traktować jako
osobny etap; nowe wersje produktu nadal wymagają nowej zgody.

## 2026-11-04 — niezależny E2E 2: pomiar autonomii zatrzymany na limicie kontekstu

**Projekt `e445de53b00c45a48732137b4d402d28`, rejestr wydatków CLI:
FAILED. Rzeczywisty wynik produktu: 3 PASS, 0 FAIL, 4 ERROR, 0 SKIP.
Release PENDING, ZIP nie powstał. Produktu ani backendu nie poprawiano ręcznie.**

- Nowy projekt jest niezależny od poprzedniego sumatora. Zakres: dodawanie wydatków
  z dodatnią całkowitą kwotą w groszach i kategorią, lista w kolejności dodawania,
  suma, zapis JSON pod jawną ścieżką --file, walidacja wejścia i ochrona uszkodzonego
  JSON przed nadpisaniem. Testy mają używać TemporaryDirectory i main(argv).
- Bazowy stan, pełna specyfikacja oraz hashe backendu i plików .ignore:
  `data/autonomy-e2e2-20261104.json` i
  `logs/autonomy-e2e2-20261104T153030Z-baseline.json`.
  Modele bez zmian: CEO/QA qwen3:4b, Developer qwen2.5-coder:7b;
  kontekst 8192, temperatura 0,2, standardowe limity prób/napraw, MANUAL.
  W tym trybie tylko uruchamiano gotowe, uprawnione etapy istniejącym API;
  nie dodawano instrukcji ratunkowych, checkpointów z ręcznym kodem ani nowych zadań.
- CEO: 1 próba, plan z jednym Developerem. Developer 0: 1 próba generowania,
  0 korekt składni, poprawna kompilacja main.py i test_main.py oraz README.
  QA przed testami zaakceptował przegląd. Testy mimo to zawierały brak importu json.
  Obserwację z przeglądu bezpieczeństwa zapisano, ale nie przekazano jej agentom
  jako podpowiedzi i nie zmieniono wygenerowanego kodu.
- Przegląd bezpieczeństwa: brak sieci i subprocess; aplikacja otwiera wyłącznie
  przekazany file_path, a wszystkie wywołania main w testach podają ścieżkę z
  TemporaryDirectory. Przed wykonaniem uzyskano konkretną zgodę użytkownika:
  `8a728291aaa44cf3b565fad8d2517e70`, obecnie CONSUMED. Obejmuje SHA256:
  - main.py: `7c800e88fa773f28ab3e04f399911f06d1a5b3074e582801be2060c4164453e8`
  - test_main.py: `8e828f7bf158348950d081ca635c6ce54d3778dd38a438202be4cd0a997918f8`
  - README.md: `80bba18468f2ac07355c0b31aa21a15d0961d71fa71d10ad85f5c83690a78200`
- Runner wykonał tylko zatwierdzoną migawkę: projektowy Python
  `-I -B -m unittest discover -s . -p test*.py -v`, bez izolacji systemowej.
  Jedno wykonanie, exit=1. PASS: test_invalid_amount, test_invalid_category,
  test_malformed_json. ERROR: test_add_expense, test_get_total, test_list_expenses,
  test_missing_file. Wszystkie cztery tracebacki wskazują
  `NameError: name 'json' is not defined` w test_main.py.
  Błąd dotyczy kodu testów; nie dowodzi niesprawności wszystkich odpowiadających
  im funkcji aplikacji. Dalsze asercje i kompletność wymagań nie zostały potwierdzone.
- Po wykonaniu QA otrzymał wynik runnera i skierował do naprawy potwierdzone błędy.
  Developer 1 `8c5f202465914808a09b0f14aacff597` uruchomiono raz. Zatrzymał się
  **przed wywołaniem modelu**: `Kontekst wymaga 22907 bajtów, limit 19176`.
  Istniejący mechanizm nie obciął wymaganych plików/błędów. To rzeczywisty bloker
  infrastruktury kontekstu, nie NO_PROGRESS ani nieudana odpowiedź modelu naprawy.
- Zgodnie z warunkami pomiaru nie ponawiano tej samej próby, nie zwiększano
  kontekstu ani limitów, nie zmieniano backendu, nie skracano promptu i nie
  dodawano ręcznej poprawki importu. Nie można z tego wyniku wywnioskować, czy
  Developer sam naprawiłby błąd: żądanie naprawy nie dotarło do modelu.

| Mierzona wielkość | Rzeczywisty wynik |
| --- | --- |
| Próby początkowego generowania | 1 |
| Automatyczne korekty składni | 0 |
| Cykle napraw zlecone przez QA | 1 |
| Uruchomienia zadania naprawy / zapytania modelu naprawy | 1 / 0 |
| Łączne wywołania LLM | 4: CEO 1, Developer 1, QA 2 |
| Łączne TaskRun | 5, w tym dwie fazy tego samego QA |
| Wykonania testów produktu | 1 |
| Interwencje człowieka | 1 obowiązkowa zgoda; 0 poprawek i 0 wskazówek ratunkowych |
| Ręczne zmiany produktu / backendu | 0 / 0 |
| ZIP | 0; Release PENDING |

- Stan kolejki: CEO i Developer 0 COMPLETED, QA 0 REVIEWED,
  Developer 1 FAILED (attempts=1), QA 1 `014de6022c2b42728c2a043114a6004d`
  PENDING, Release `52f507dc47a344d1ae9d333e256985a3` PENDING.
  Żadnego statusu nie zmieniano na sukces ręcznie i nie resetowano liczników.
- Pełny raport, każdy wynik i traceback, pliki, zadania, checkpointy, próby,
  metryki i zgoda: `logs/autonomy-e2e2-20261104T153030Z-result.json`.
  Surowe wyjście: `workspace/runs/8a728291aaa44cf3b565fad8d2517e70-test-output.log`.
  Snapshot sprzed wykonania zachowuje również pierwszą opinię QA i jej metryki.
- Porównanie SHA256 potwierdziło identyczny backend przed/po eksperymencie,
  identyczne ustawienia, nienaruszone pliki .ignore oraz produkt zgodny z hashami
  zużytej zgody. Nie uruchamiano ponownie testów silnika ani wcześniejszego E2E.
- **Następny krok poza tym eksperymentem:** osobno zbadać i poprawić budowę
  kontekstu napraw, z regresją dla tego zapisanego przypadku. Bieżący pomiar
  pozostaje niezaliczony; nie odblokowywano go ręczną ingerencją.

## 2026-11-04 — istniejący E2E zakończony wydaniem ZIP

**Projekt `5685e12b142044d1a8b9c3b0029265bd` ma COMPLETED.
Developer 2, QA 2 i Release zakończone. Zatwierdzona poprawiona wersja:
7 PASS, 0 FAIL, 0 ERROR, 0 SKIP; rzeczywisty ZIP zweryfikowany.**

### Wznowienie i autorstwo korekty

- Zachowano istniejący projekt, plan, próby, zgody i historię. Nie tworzono nowego E2E.
  Przy wznowieniu pliki nie zawierały opisanej wcześniej reguły pierwszeństwa wymagań,
  stanu CLI unknown ani tests/test_review_contract.py. Przywrócono te same konieczne
  poprawki i sprawdzono tylko ich 6 regresji: **6 PASS**, 2,17 s, jedno wcześniejsze
  ostrzeżenie Starlette/httpx. Z tego powodu krótka weryfikacja została powtórzona;
  nie powtarzano pełnego zestawu backendu ani wcześniejszego audytu. Compile bez zmian.
- Developer 2 `f79e56edfbe2436cb0bfa94583f8d337`, próba 1: qwen2.5-coder:7b
  zwrócił edycję z niejednoznacznym old_text w test_main.py. Materialize odrzucił
  całą propozycję przed zapisem; to nie był NO_PROGRESS. Pliki pozostały bez zmian.
  Dowód: `logs/qa-e2e-developer2-resume-20261104.json`.
- Następnie Codex przygotował **jawną korektę inżynierską**, a nie przypisał jej
  lokalnemu modelowi: zachowano add, main(argv=None), parser.parse_args(argv),
  usunięto wadliwy wrapper z powtórzonym file i niezdefiniowanym sys. Zachowano
  siedem nazw testów; stdout/stderr przechwytują StringIO/redirect_stdout/stderr,
  a błędne wejście wymaga niezerowego kodu i komunikatu zamiast wymyślonego kodu 1.
  Test prawidłowego CLI obejmuje dodatnie, ujemne liczby i zero; oba błędne operandy
  mają sprawdzane błędy, brak wyniku w stdout oraz niezerowy SystemExit.
- Propozycję sprawdzono statycznie przez validate_batch(repair=True), ochronę nazw
  testów i kompilację, bez importowania produktu. Zapisano human_reviewed_proposal
  i zwykły proposal z aktualnymi hashami. Standardowe retry (próba 2) odtworzyło
  propozycję istniejącą ścieżką checkpointów: normalna kontrola plików, kompilacja,
  zapis i aktualizacja własności przez silnik. Nie resetowano limitów ani nie
  ustawiano statusu sukcesu ręcznie. Developer 2 ma COMPLETED; nieudana próba jest
  nadal w TaskRun. `logs/qa-e2e-engineering-proposal-20261104.json`.

### QA, zgoda i rzeczywiste testy

- QA 2 `a41545e68107402c803005480f70d6cb` przed testami ponownie powtórzył stare
  zarzuty mimo nowych plików. Deterministyczny raport zachował je jako hipotezy,
  bez tworzenia kolejnych napraw. Statyka: errors=[], cli_entrypoint=present,
  siedem testów. Stan WAITING_APPROVAL był prawidłowy; model nadal może halucynować.
- Użytkownik jawnie zatwierdził nową zgodę
  `b20b5623bc6c4d63a35dc8a63f8167bc`, wykonanie bez izolacji, dla SHA256:
  - main.py: `e7ac71f36c71ae2e5c5e4e285a86e04bec87c55e92a7a058a38e8b26a90a8c34`
  - test_main.py: `0dbddc053570112f95362f0a87f8f230c377f0c4523e659db0fb75094ed40684`
  - README.md: `342332abaac1e6f14a32ebadce62a6c3f149bc08bbb102450b371b62960e9731`
- Po ponownym porównaniu hashów zgodę przekazano przez istniejące API. Runner
  wykonał migawkę poleceniem projektowego Pythona:
  `-I -B -m unittest discover -s . -p test*.py -v`. **7 PASS, exit=0**, 0,21 s
  runnera (unittest: 0,002 s). Każda z siedmiu funkcji ma ok; brak tracebacków.
  Zgoda ma CONSUMED. Testy CLI wywołują main(argv) w procesie unittest; nie
  uruchamiano dodatkowego procesu CLI poza zakresem zatwierdzonego polecenia.
- QA otrzymał rzeczywisty wynik z hashami, wycofał zarzuty i zaakceptował pliki:
  COMPLETED, qa_report.outcome=verified, issues=[], hypotheses=[]. Nie utworzono
  Developer 3 ani nowej pętli NO_PROGRESS. To potwierdza działanie bramki dowodów
  w tym przebiegu, nie ogólną niezawodność ocen modelu.
- Każdy wynik i pełne wyjście: `logs/qa-e2e-corrected-test-results-20261104.json`
  oraz `workspace/runs/b20b5623bc6c4d63a35dc8a63f8167bc-test-output.log`.
  Poprzedni wynik produktu (3 PASS, 4 ERROR) i jego tracebacki nadal znajdują się
  w `logs/qa-e2e-first-test-results-20261103.json` i logu poprzedniej zgody.

### Release i weryfikacja artefaktu

- Pierwszy Release utworzył ZIP `4d4087f8e275408cb33088997964af26` z poprawnym
  manifestem, ale sprzecznym zdaniem w notatkach o niewykonanych testach. Artefakt
  zachowano w historii. Dodano jeden standardowy etap Release do istniejącego
  projektu, zależny od ukończonego QA 2, z poleceniem korekty samych notatek.
  Nie zmieniano kodu produktu ani nie powtarzano testów.
- Końcowy Release `90000550c6564771ad13c680b861d0c6`: COMPLETED. Artefakt
  **`c77fa162c6114793a8707af14f757aa0`**, plik
  `workspace/artifacts/c77fa162c6114793a8707af14f757aa0.zip`, SHA256
  **`7058ece46229bfdf13260a0a6282a38990a8ed4ddcb84f1dfb76f34e1491a7ef`**.
- Sprawdzono CRC ZIP, dokładną listę sześciu elementów, SHA256 całego archiwum,
  hashe trzech plików produktu względem zgody, QA i VERIFICATION.json oraz
  identyczność dowodu siedmiu testów w manifeście. Skorygowane RELEASE.md jest
  zgodne z wynikiem. ZIP zawiera produkt, VERIFICATION.json, RELEASE.md i CHANGELOG.md.
- Pełny eksport projektu, wszystkich zadań, prób i checkpointów, zgód, manifestu
  oraz notatek: `logs/qa-e2e-release-20261104-evidence.json` (32 checkpointy,
  12 TaskRun). Zachowano również pierwotny ZIP z wadliwymi notatkami.
- Backend pozostaje na http://127.0.0.1:8000 w MANUAL, bez aktywnego zadania tego
  projektu. Plików `.ignore` i `.ignore.backup-*` nie zmieniano. Nie pobierano modeli,
  nie używano chmury i nie naruszano mechanizmu zgód.

**Ten E2E ma poprawny produkt, wykonane testy i ZIP, z udokumentowaną korektą
inżynierską. Nie jest dowodem w pełni autonomicznej naprawy przez lokalny model.**
Następny ewentualny rozwój: niezawodność propozycji exact-match i ograniczenie
powtarzania przez QA nieaktualnych obserwacji; bez potrzeby ponawiania tego E2E.

Poniższe wpisy są historyczne; stan końcowy tego projektu opisano powyżej.

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

## 2026-11-04 — niezależne testy akceptacyjne rejestru wydatków (bez wykonania)

- Dodano acceptance/expense_log/test_acceptance.py i README.md poza produktem.
  Oczekiwania porównano z request w data/autonomy-e2e2-20261104.json.
- 10 metod: 8 obowiązkowych (ochrona bajtów uszkodzonego JSON przy add/list/total,
  zero/ujemne/niecałkowite kwoty, puste i białe kategorie, wymagane --file) oraz
  2 opcjonalne odpornościowe (błędny schemat JSON, niepełne add i zachowanie
  danych po odrzuceniu). Dodatkowe kontrakty nie są obowiązkowymi kryteriami Release.
- Walidacja statyczna ast.parse + compile drzewa: PASS; potwierdzono 10 metod,
  2 advisory, brak bezpośredniego importu main przy zbieraniu testów. Niczego
  nie wykonano: ani nowych testów, ani produktu, ani zestawu backendu.
- SHA256 test_acceptance.py:
  fd18da5123eeae70f21d22aa2af2d3e72f480909f8f57d55e04f220ff735e6da.
- Hashe main.py, test_main.py i README.md produktu oraz istniejącego Release ZIP
  nadal odpowiadają poprzedniemu zatwierdzonemu wydaniu. Nie zmieniano backendu.
- Wykonanie wymaga nowej jednorazowej zgody związanej z hashami migawki produktu
  i niezależnego testu. Guard środowiskowy nie jest zgodą; README opisuje warunki
  runnera, także konieczność adaptera, jeśli runner usuwa zmienne środowiskowe.

## 2026-11-04 — przygotowane wykonanie niezależnej akceptacji, zgoda PENDING

- Sprawdzono oryginalny request, 8 wymaganych metod i 2 dodatkowe. Statyczne
  ast.parse/compile przeszły. Oryginalny produkt i istniejący ZIP zachowały hashe.
- Runner zachowano bez zmian: stała komenda, czyste środowisko, limit 120 s,
  Windows Job Object, kontrola hashów przed startem i jednorazowa zgoda.
  Nie obsługuje osobnej listy plików zewnętrznych ani dodatkowych zmiennych.
- Dodano acceptance/expense_log/approved_adapter.py: w zatwierdzonym procesie
  ładuje niezależne testy i wymusza pominięcie 2 advisory. Nie udziela zgody.
- tests/test_acceptance_adapter.py: 3 PASS, 0 FAIL/ERROR/SKIP (0,29 s), wyłącznie
  własne zaufane atrapy. Pierwsza próba: 2 PASS/1 ERROR przy tworzeniu systemowego
  katalogu tymczasowego; ponowienie w nowym katalogu repo potwierdziło poprawność.
  Nie powtarzano pełnego backendu; produktu nie importowano ani nie wykonywano.
- Osobny projekt b5e63a23e87543519ca2d89fbdaff4d0; QA
  f2476b1bd502455381d9a723f06434cf: WAITING_APPROVAL. Zarejestrowano inżynierski
  checkpoint acceptance_preflight i zgodę host_tests
  79077d28f33a4d9b8bf5e21883867b40: PENDING. Nie podszywano się pod ocenę modelu.
- Kopia źródłowa zgody zawiera tylko main.py, acceptance_cases.py i adapter
  test_acceptance.py. Testy otrzymały UTF-8 bez BOM/LF, bez zmian asercji.
  Pełne hashe, komenda, specyfikacja i pochodzenie:
  logs/expense-independent-acceptance-prepared-20261104.json.
- Wyniki produktu: brak wykonania (PASS/FAIL/ERROR/SKIP: nieustalone).
  Po nowej zgodzie istniejący engine utworzy i sprawdzi migawkę, wykona testy,
  utrwali pełny output/checkpoint i przekaże błędy QA do procesu napraw w osobnej
  kopii. Produkt źródłowy i historyczny ZIP nie będą nadpisywane.

## 2026-11-04 — niezależna akceptacja wykonana: 7 PASS / 1 FAIL / 0 ERROR / 2 SKIP

- Użytkownik jawnie zatwierdził wersję bez izolacji; zgodę
  79077d28f33a4d9b8bf5e21883867b40 przekazano przez istniejące API.
  Status końcowy CONSUMED. Jedno wykonanie produktu, runner 0,32 s, exit=1.
- Osiem metod obowiązkowych: 7 PASS / 1 FAIL / 0 ERROR. Dwie opcjonalne: SKIP.
  Unittest raportuje failures=2, bo jedna metoda test_blank_category_rejected
  ma dwa niezaliczone podprzypadki: trzy spacje oraz tabulator. Nie są to dwa
  różne testy metodowe. Oba przypadki zwracają kod 0 zamiast błędu.
- Potwierdzono rzeczywiste naruszenie pierwotnego wymagania odrzucania blank
  categories. Ochrona bajtów uszkodzonego JSON dla add/list/total, wymagane
  --file i odrzucanie zero/ujemnych/niecałkowitych kwot przeszły.
- Pełne tracebacki i wyniki każdej metody:
  workspace/runs/79077d28f33a4d9b8bf5e21883867b40-test-output.log oraz
  logs/expense-independent-acceptance-result-20261104.json.
- Faza post_tests początkowo zatrzymała się przed LLM: 20123 > 19176 bajtów.
  Usunięto wyłącznie dokładną kopię specyfikacji z opisu zadania; pełne wymagania
  pozostały w ProjectGoal, poprzedni opis zachowano w checkpoincie
  acceptance_description_deduplicated. Żadnego kodu, dowodu ani limitu nie zmieniono.
  Standardowy retry wznowił tylko interpretację post_tests, bez ponowienia testów.
- QA f2476b1bd502455381d9a723f06434cf: REVIEWED, changes_requested.
  Istniejący proces napraw utworzył Developer 8c8c89413be94fce8cf8eb2b19265914
  i QA 4d7efc7e1c734aa3ad8b8f1aad5b17a7: oba PENDING, nieuruchomione w MANUAL.
  Developer otrzymał pełne wyjście runnera i oba tracebacki; oryginalne wymagania
  pozostają w projekcie. Nie wykonano ręcznych napraw ani zmian testów dla PASS.
- Potwierdzono identyczność hashów zatwierdzonej kopii i wykonanej migawki.
  Produkt źródłowy i poprzedni ZIP zachowały hashe. Backend bez zmian.
  Zmodyfikowany produkt nadal wymaga nowej jednorazowej zgody przed wykonaniem.
 
## 2026-11-04 — Developer poprawił whitespace; nowa zgoda QA oczekuje

- Odrzucono propozycję Developera 1, która osłabiała asercję testu akceptacyjnego.
  Zgodę overwrite 013a49be699646d9aaa46bf14b01100f ustawiono REJECTED;
  pełen checkpoint kandydatury i historia zadania zachowane. Utworzono Developer 2
  z pełnymi runner dowodami i zakazem modyfikacji testów.
- Pierwsze podejście Developer 2 nie dotarło do LLM z powodu powtórzonego logu
  (20713 > 19176 bajtów). Opis skrócono; pierwotny zapis zachowano w checkpointcie.
  Lokalny qwen2.5-coder:7b zmienił wyłącznie warunek w main.py na
  not args.category.strip(). Static compile przeszło. Oryginalne testy akceptacji,
  test_main.py i README mają niezmienione hashe.
- QA 2 błędnie zgłosił brak test_main.py/README w wąskiej kopii. Zatrzymano zadania
  naprawy utworzone na podstawie tego false positive. Do kopii akceptacyjnej dodano
  niezmienione pliki z oryginalnego produktu; nowe QA obejmuje pięć plików.
- Kontekst QA ponad budżet 21308 bajtów wymagał, żeby po testach zachować pełny
  produkt i runner output, a testowe moduły streścić listami metod z hashami.
  Dodano jeden warunkowy mechanizm backend/app/context.py i regresję w
  tests/test_context_budget.py. Celowany test: 1 PASS (0,04 s); poprzednie próby
  ujawniły błąd fixture, następnie poprawiono fixture przed zieloną weryfikacją.
  Pełny backend nie powtarzany. Kontrolowany restart załadował tę zmianę.
- QA 3 statycznie zaakceptował składnię i przygotował zgodę
  0decfc0fb6374740a1f2d6ebf1107f5c: PENDING. Jego modelowy opis błędu jest
  sprzeczny z wcześniejszym runner dowodem i kodem (strip() odrzuca białe znaki);
  niezależne wykonanie pozostaje rozstrzygającym dowodem. Migawka zawiera:
  README.md 80bba18468f2ac07355c0b31aa21a15d0961d71fa71d10ad85f5c83690a78200,
  acceptance_cases.py ad2e2fa93bc9905fd2433df770a50ca87054532c4f666c6f79fe27bbb633c3fb,
  main.py 3ee672b721782a0f2bf37dbd713a09db13dbbdce3b7619896ff745eb7fc5f25d,
  test_acceptance.py 954af2a7c0dd176fd47008882955adf71a62dbdeeac6c242cebb7c3b40a90051,
  test_main.py 091bf5f9a1b78771913ea7f8f784ec3d4f0aedf861c83ec900e8cc3aa3308d5e.
  Komenda i pełne zatwierdzenie zapisane w
  logs/expense-fix-preexecution-20261104.json. Produktu jeszcze nie wykonano.
 
## 2026-11-04 — po nowej zgodzie produktowe 7 PASS; acceptance guard przerwał niezależną suite

- Zgoda 0decfc0fb6374740a1f2d6ebf1107f5c CONSUMED; zatwierdzona migawka miała
  pięć sprawdzonych hashy. Runner wykonał poprawiony produkt jeden raz.
- test_main.py: 7 PASS. Niezależny zestaw nie wykonał metod: setUpClass zgłosił
  ERROR, bo zewnętrzny guard w acceptance_cases.py nadal wymaga SHA256
  pierwotnego main.py (e4d843...), podczas gdy zatwierdzony fix ma hash 3ee672...
  To blokada guardu testowego, nie wynik funkcjonalnych asercji. Liczby runnera:
  PASS 7, FAIL 0, ERROR 1, SKIP 0, exit 1; runner wykrył 7 metod, bo klasyczny
  błąd setUpClass poprzedza uruchomienie metod acceptance.
- Zapisano pełne wyjście i QA/approval state w logs/expense-fix-run-result-20261104.json
  i workspace/runs/0decfc0fb6374740a1f2d6ebf1107f5c-test-output.log.
  Zgoda jest zużyta; nie ponawiano testów.
- QA post_tests nie zakończył interpretacji: model zwrócił błąd braku miejsca
  dla promptu wraz ze schematem. Produkt źródłowy i historyczny ZIP bez zmian.
  Release PENDING; nie utworzono artefaktu nowej wersji.
- Kontynuacja wymaga zgody na aktualizację wyłącznie hash guardu niezależnych testów
  do nowej zatwierdzonej wersji, bez zmian ich asercji. Po takiej zmianie wymagane
  będą statyczna kontrola i nowa zgoda hash-bound. Bez modyfikacji niezależnych
  plików próba ponownego wykonania pozostanie deterministycznie zablokowana.

## 2026-11-04 — autoryzowana aktualizacja wyłącznie hash guardu

- Użytkownik zezwolił na zmianę samego hash guardu w niezależnym zestawie.
  Zmieniono jedną stałą w acceptance/expense_log/test_acceptance.py oraz jej
  kopii acceptance_cases.py w projekcie. Poprzednie treści po odwróceniu tej
  stałej odtwarzają dokładnie wcześniejsze SHA256 fd18da5123eeae70f21d22aa2af2d3e72f480909f8f57d55e04f220ff735e6da
  a wcześniejsza wartość projektu odpowiada SHA256 z
  logs/expense-independent-acceptance-result-20261104.json.
- Nowy guard wskazuje poprawiony main.py SHA256
  3ee672b721782a0f2bf37dbd713a09db13dbbdce3b7619896ff745eb7fc5f25d. Asercje
  pozostały identyczne. Nowe hashe plików guardu: source
  abd70cb1b0ddcee34e79a661e54c5720cbb19f5332eea0ec4a0c9ae241c4b439;
  project copy c8e97c018bb95b7d01ab808a6080ca237be1c534cfbff24183805c42b5fe6447.
- Nie utworzono jeszcze świeżej zgody ani nie powtórzono wykonania. Terminal
  przestał uruchamiać procesy (helper_unknown_error: setup refresh had errors),
  więc kolejny krok przez istniejący QA/approval runner jest obecnie zablokowany.
