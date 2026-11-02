# Ulepszenia istniejącego LocalAICompany — 2026-11-02

Nie zastąpiono aplikacji ani bazy. Przed zmianami utworzono tag
`checkpoint/before-open-source-improvements-20261102` i kopię
`data/backups/20261102T190826470092Z`. Analizowane repozytoria pobrano wyłącznie do
katalogu tymczasowego i czytano statycznie. Szczegóły źródeł, commitów, licencji
i ograniczeń: [OPEN_SOURCE_ANALYSIS.md](OPEN_SOURCE_ANALYSIS.md).

## Co zmieniono i dlaczego

| Zmiana | Pliki | Inspiracja i zakres |
| --- | --- | --- |
| Kontekst Developer/QA rozdziela cel, bieżące zadanie, pliki z hashami, rzeczywiste testy, błędy, wymagane zmiany, poprzednie próby i pozostałe limity. Czyta wyłącznie przodków danego zadania. Stare werdykty modeli nie są doklejane jako aktualne dowody. | `backend/app/context.py`, `orchestrator.py` | Koncepcja task/project context z Babber; własna implementacja |
| Naprawy używają `RepairResult`: dokładna zamiana fragmentu występującego jeden raz. Pusty old_text pozwala jedynie utworzyć brakujący plik. Cała propozycja przechodzi kontrolę ścieżek, limitów, składni i zachowania nazw testów przed zapisem. | `repairs.py`, `schemas.py`, `agents.py`, `orchestrator.py` | Koncepcja typowanych operacji CrossWave; zapis przez istniejący lokalny rejestr `write_file`, bez kopiowania kodu |
| Brak zmiany AST kodu i treści pozostałych plików zatrzymuje naprawę jako NO_PROGRESS. Zmienione pliki, diff i hashe stanowią dowód zapisu. | `repairs.py`, `orchestrator.py` | Własna kontrola, zgodna z ograniczonymi cyklami Babber/Open Polsia |
| Checkpointy SQLite przechowują kontekst/metryki, propozycję, zapisane pliki, analizę QA i wykonane testy. Retry odzyskuje poprawną propozycję bez kolejnego LLM; odrzuca niespodziewane zmiany użytkownika. Odrzucony kod pozostaje w checkpointach, nie w projekcie. | `database.py`, `checkpoints.py`, `orchestrator.py`, `service.py` | Koncepcja checkpoint CrossWave dostosowana do istniejącego SQLite; nowa tabela jest dodatkiem |
| QA rozróżnia analizę statyczną, opinię modelu i wynik runnera. Traceback daje plik, linię, typ i komunikat błędu. QA przekazujące poprawki ma status REVIEWED. COMPLETED Developera oznacza zapis i kontrolę składni, nie zaliczone testy. | `evidence.py`, `schemas.py`, `orchestrator.py`, `service.py` | Koncepcja jawnego ukończenia/kontynuacji Open Polsia, zaostrzona o lokalne dowody |
| Zmiana plików podczas QA lub wykonania testów blokuje dalszą weryfikację. Wynik wykonanych testów pozostaje zapisany. Release nadal wymaga rzeczywistych zaliczonych testów tej wersji. | `orchestrator.py` | Zachowane i wzmocnione lokalne bramki |
| Pamięć posiada typowane wpisy: preferencja, decyzja, wynik testów, zweryfikowane rozwiązanie. Selekcja tekstowa ma limit; niesprawdzone rozwiązania nie trafiają do kontekstu. Preferencję można zapisać przez POST projektu `/memory`. | `memory.py`, `main.py`, `schemas.py` | Rozdzielenie pamięci i rozmowy z Babber/Open Polsia; własna implementacja SQLite |
| Ollama zapisuje faktyczne prompt_eval_count/eval_count, czas, model, powód zakończenia oraz szacowany budżet. Korekta JSON podaje nazwy błędnych pól bez kopii danych wejściowych. Deadline obejmuje cały etap. | `ollama.py`, `orchestrator.py` | Koncepcja parametrów/metryk Babber; nadal jeden request i loopback |
| Istniejący panel pokazuje raport QA, wyjście testów, źródła problemów i historię prób/checkpointów. Naprawiono wyścig odświeżania przy wyborze nowego projektu. | `frontend/src/TaskEvidence.tsx`, `App.tsx`, `styles.css`, `main.py` | Własna rozbudowa istniejących widoków, bez nowego dashboardu |
| Start sprawdza szybkie `/api/ready`; dostępność Ollama jest sprawdzana osobno. Backup obejmuje także nieśledzone, nieignorowane źródła. Skrypty E2E zachowują oddzielne pliki wyników kolejnych uruchomień. | `start.ps1`, `scripts/backup.py`, `audit_state.py`, `live-ui.mjs`, `inspect-ui.mjs` | Własne poprawki operacyjne |

Żadnego fragmentu kodu z analizowanych repozytoriów nie przeniesiono. Nie dodano
zależności, modeli, usług, cloud AI ani publikacji. Harmonogram i autonomia zachowują
dotychczasowy, ograniczony zakres; rozbudowa jest odłożona do zaliczenia realnego E2E.

## Wykonana weryfikacja

- Backend: **67 passed, 2 skipped**, 13,53 s. Pominięcia: uprawnienie symlink Windows
  i opt-in live. Pozostało wcześniejsze ostrzeżenie deprecacji Starlette/httpx.
- Frontend: `npm.cmd run build` zaliczony; `npm.cmd test`: **4 passed**, Edge.
- Regresje obejmują realny runner na zaufanych fixtures, ZIP, ograniczenia iteracji,
  dokładne edycje, brak postępu, utratę procesu między plikami, zmianę użytkownika,
  kontekst rzeczywistych błędów, zachowanie odrzuconej propozycji oraz budżet LLM.
- Test zmiany źródła podczas wykonania nadal sprawdza brak ZIP i zapis dowodów.
  Oczekiwany moment blokady zaostrzono: QA FAILED, Release PENDING zamiast dopiero
  Release FAILED. Nie usuwano testu ani wykrywanego przypadku.
- Rzeczywisty restart: identyczne raporty przed/po (SHA256 całych raportów równe),
  `integrity_check=ok`: 2 projekty, 22 zadania, 17 prób, 4 checkpointy, 1 zgoda,
  0 artefaktów, 18 wiadomości, 13 wpisów pamięci. Raporty w `logs/runtime-audit-*.json`.
- Obejrzano realny panel po restarcie: `logs/e2e-improvements-evidence.png`.

## Realny E2E — wynik negatywny

Przez Edge wysłano dokładne polecenie z nowej specyfikacji, obejmujące również
wyświetlanie zadań. Projekt `0a87073016a245c79d05873479265584`; zapis polecenia:
`data/live-e2e-20261102192224037.json`. CEO/qwen3:4b ukończył plan i zapisał
łańcuch Developer → QA → Release. Developer/qwen2.5-coder:7b otrzymał dwie próby:

1. `SyntaxError: unterminated string literal`, `tasks.py:52`.
2. `IndentationError: unexpected unindent`, `tasks.py:13`.

Developer `6ebd39bb5a874c5d81836821a55af167` jest FAILED, attempts=2. Nie resetowano
liczników. QA i Release pozostają zależne i niewykonane. Żadnego wygenerowanego
kodu z tego przebiegu nie wykonano; nie utworzono nowej zgody ani ZIP. Wadliwe pliki
nie zostały zapisane w workspace. Druga odrzucona odpowiedź jest zachowana w
checkpointcie `rejected_proposal`; pierwsza powstała przed dodaniem tej funkcji.
Zmierzono dla drugiej odpowiedzi 2158 tokenów wejścia, 1351 wyjścia, 20,415 s,
done_reason=stop — nie ma dowodu ucięcia odpowiedzi przez limit tokenów.

Historyczny projekt `8a58aef75bd04a4dbe4d486a2d416aef` zachowano. Jego jednorazowa
zgoda jest CONSUMED; wcześniej 4 rzeczywiste testy dały 3 błędy, a dalsze naprawy
osiągnęły limit 5. Żadna stara zgoda nie została użyta ponownie.

## Pozostałe ograniczenia i kolejny krok

Pełny przepływ działa w integracji z kontrolowanym klientem i realnym runnerem,
ale **nie zaliczono końcowego TODO na rzeczywistych modelach**. Następny etap to
naprawa generowania początkowego kodu Python na podstawie zachowanego odrzutu:
sprawdzenie celowanej korekty składni w ramach istniejącego limitu, bez ręcznego
resetowania historycznych prób i bez uznawania tekstu modelu za wykonany produkt.
Dopiero potem ponowny kontrolowany E2E, przegląd konkretnych plików i nowa zgoda
z SHA256 na testy, jeżeli powstanie wersja nadająca się do wykonania.

Budżet wejścia jest szacunkiem bajty/3, nie dokładną tokenizacją. Duży wymagany
kontekst kończy etap czytelnym błędem zamiast ucinania plików. Zachowanie nazw
testów nie dowodzi zachowania ich jakości; potrzebne są niezależne testy akceptacyjne.
Porównanie AST wykrywa pozorne zmiany, lecz nie dowodzi poprawności algorytmu.
Checkpoint nie zapewnia transakcji filesystem+SQLite; kontroluje częściowy zapis
i rozpoznaje niespodziewane zmiany. Host runner nadal nie jest sandboxem.
