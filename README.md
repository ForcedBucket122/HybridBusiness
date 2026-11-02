# LocalAICompany

Lokalny zespół agentów z panelem WWW. FastAPI + SQLite + React + Ollama.
Runtime działa niezależnie od Codex i ChatGPT, bez płatnych API i usług chmurowych.

**Status:** działająca implementacja MVP w trakcie weryfikacji praktycznej.
Aktualne dowody, ograniczenia i dokładny wynik E2E: [docs/PROGRESS.md](docs/PROGRESS.md).
Ocena modelu nigdy nie zastępuje uruchomionych testów. Wyniki i przychody nie są gwarantowane.

## Uruchomienie na Windows 11

Wymagania: Python 3.11+ (sprawdzony 3.14), Node 22+ (sprawdzony 24), istniejąca Ollama
z modelami `qwen3:4b` i `qwen2.5-coder:7b`. Bez Dockera i praw administratora.

```powershell
cd A:\HybridBusiness
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Panel: **http://127.0.0.1:8000**. API: http://127.0.0.1:8000/docs.
Backend serwuje skompilowany frontend, więc nie jest potrzebny drugi serwer w trybie produkcyjnym.
`-ExecutionPolicy Bypass` dotyczy tylko tego procesu i nie zmienia globalnej polityki systemu.
Skrypty używają `npm.cmd`, aby ominąć blokowanie `npm.ps1` przez politykę PowerShell.

Jeżeli Ollama nie działa, uruchom istniejącą instalację (`ollama serve`) w osobnym terminalu.
Setup sprawdza modele, ale nigdy ich nie pobiera ani nie przenosi. Nie reinstaluje Ollama.
Wszystkie zależności projektu instaluje lokalnie: Python do `.venv`, frontend do `node_modules`.

```powershell
# Zatrzymuje wyłącznie zarejestrowane procesy aplikacji, nie Ollama ani inne projekty
powershell -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1

# Wariant developerski: dodatkowy Vite na http://127.0.0.1:5173
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Dev
```

Nie uruchamiaj wielu workerów Uvicorn ani autoreload dla trwałej kolejki.
Backend ma blokadę zapobiegającą uruchomieniu drugiego workera tej samej bazy.

## Pierwszy projekt

1. Utwórz projekt w panelu.
2. W CEO Chat opisz cel i kryteria odbioru, np. aplikację konsolową Python z testami unittest.
3. Obserwuj rzeczywisty plan i kolejkę. Developer zapisze pliki w `workspace/projects/<id>`.
4. Przejrzyj pliki i wyniki analizy QA. W Zatwierdzeniach sprawdź polecenie, pliki i hashe.
5. Dopiero po świadomej zgodzie runner wykona testy na kopii w `workspace/runs/<approval-id>`.
6. Błędy mogą uruchomić do 5 iteracji poprawek. Każda nowa wersja testów wymaga nowej zgody.
7. Release przygotuje ZIP z plikami, README, changelogiem, raportem i `VERIFICATION.json`.

**Runner nie jest sandboxem.** Kod działa z uprawnieniami użytkownika. Brak automatycznego
wykonywania kodu w jakimkolwiek trybie. Więcej: [docs/SECURITY.md](docs/SECURITY.md).
MVP obsługuje małe projekty Python ze standardową biblioteką i unittest; nie instaluje
zależności wygenerowanych projektów. Nie podawaj sekretów w rozmowach.

## Tryby i ustawienia

- MANUAL: każdy etap uruchamiany jawnie; polecenie z rozmowy zleca etap CEO.
- HYBRID (domyślny): dalsze etapy poleconego planu wykonują się samodzielnie.
- AUTONOMOUS: obecnie ten sam ograniczony zakres planów; zgody nadal obowiązują.
- Opcjonalny harmonogram generuje propozycje Research, bez automatycznej implementacji.
  Domyślnie wyłączony; minimum 15 minut, limit dzienny i limit aktywnych zadań.
- Modele wszystkich agentów, kontekst, tokeny, temperatura, timeout i próby są konfigurowalne.
- Jedno zadanie LLM naraz, modele zwalniane po odpowiedzi, bez wymagania wspólnej rezydencji VRAM.

Po zatrzymaniu zadanie RUNNING staje się INTERRUPTED. Ponowienie jest jawne i ograniczone.
Zgody na wykonanie rozpoczętych testów nie są automatycznie ponownie używane.
Nieudana zależność blokuje następców do wznowienia; anulowanie zależności anuluje następców.

## Struktura

```text
backend/app/          API, modele, agenci, kolejka, Ollama, narzędzia, zgody, runner
frontend/src/         panel React/TypeScript i style
frontend/tests/       testy Playwright
tests/                testy jednostkowe, integracyjne i opcjonalna Ollama live
scripts/              praktyczny test przez panel
docs/                 architektura, bezpieczeństwo, postęp, testowanie, roadmapa
data/                 SQLite i stan procesów (ignorowane w repozytorium)
logs/                 logi i lokalne dowody weryfikacji (ignorowane)
workspace/projects/   wygenerowane projekty (ignorowane)
workspace/runs/       zatwierdzone migawki testów i raporty (ignorowane)
workspace/artifacts/  archiwa ZIP (ignorowane)
```

Moduły backendu są płaskie, aby w MVP unikać pustych warstw abstrakcji; podział odpowiedzialności
opisuje [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
`LOCALAI_DATA_DIR` i `LOCALAI_WORKSPACE` można ustawić jako zmienne procesu przed startem.
Plik `.env.example` dokumentuje przykład; skrypty nie wykonują kodu ani nie parsują `.env`.

## Testy

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp data\pytest-temp
cd frontend
npm.cmd run build
npm.cmd test
cd ..
# Opcjonalne prawdziwe zapytanie do lokalnego modelu; nie uruchamia wygenerowanego kodu
$env:LOCALAI_LIVE='1'
.\.venv\Scripts\python.exe -m pytest -q tests\test_live.py
Remove-Item Env:LOCALAI_LIVE
```

Playwright wymaga uruchomionej aplikacji i istniejącego Edge; automatyczne testy UI
mockują API. `node scripts/live-ui.mjs` wysyła prawdziwe polecenie do modeli przez panel,
tworzy nowy projekt i zapisuje `data/live-e2e.json`. Nie klika zgód na wykonanie kodu.
Szczegóły: [docs/TESTING.md](docs/TESTING.md).

## Ograniczenia i dalszy rozwój

Brak internetowego researchu, publikacji, wysyłania wiadomości, płatności, izolowanej VM,
instalacji pakietów produktów i runnerów innych języków. Research/Finance tworzą hipotezy
i prognozy, nie zweryfikowane dane rynkowe. Małe modele mogą pominąć rzeczywiste błędy.
Projekty ograniczone do 100 plików, 2 MB i dostępnego kontekstu modelu.
Następny etap: rzeczywista izolacja wykonania i niezależne testy kryteriów odbioru.
[Roadmapa](docs/ROADMAP.md).
