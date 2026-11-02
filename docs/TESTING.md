# Testowanie

## Zestawy automatyczne

`tests/test_security.py`: konfiguracja, traversal/UNC/ADS/nazwy Windows, hardlinki,
symlinki (pominięte, jeśli system nie daje uprawnienia ich tworzenia), limity plików i narzędzia.

`tests/test_ollama.py`: transport httpx mockowany, JSON fallback, błędna odpowiedź i retry,
brak modeli, błąd połączenia oraz blokowanie zdalnych aliasów. Nie wymaga uruchomionego modelu.

`tests/test_flow.py`: API/SQLite, idempotencja, tryb MANUAL, delegowanie, zgody, rzeczywiste
pliki i ZIP, pętla naprawcza, limity, anulowanie, pamięć, harmonogram i recovery.
Model i runner są testowymi implementacjami, które nie są używane w aplikacji produkcyjnej.

`tests/test_recovery_runner.py`: prawdziwy runner uruchamia zaufane testowe fixtures napisane
w repozytorium (nie kod od LLM). Sprawdza unittest, zero testów, anulowanie oraz dodatkowe
przypadki utraty procesu, przechowania wyników i zmian kodu po zatwierdzeniu.

`frontend/tests/panel.spec.ts`: Edge/Playwright, tworzenie projektu, rozmowa, stan zadań,
błąd backendu i wymaganie zgody. API mockowane w przeglądarce tylko w tych testach.

## Uruchamianie

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp data\pytest-temp
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
cd frontend
npm.cmd run build
npm.cmd test
```

## Realna Ollama

`LOCALAI_LIVE=1` odblokowuje `tests/test_live.py`. Test sprawdza obydwa modele w /api/tags
i rzeczywistą odpowiedź qwen3:4b z JSON Schema. Nie pobiera modeli i nie wykonuje ich kodu.

## Praktyczny E2E

```powershell
node scripts/live-ui.mjs
```

Skrypt wysyła przez panel dokładne polecenie aplikacji TODO, zapisuje identyfikator projektu
i zrzuty ekranu. Dalsze zadania wykonuje aplikacja. Sprawdź pliki przed akceptacją testów.
Zgoda użytkownika jest wymagana także podczas testu prowadzonego przez Codex.
Po zgodzie weryfikacja obejmuje raport runnera, nie tylko tekst odpowiedzi QA,
oraz zawartość ZIP, SHA256 i wpisy TaskRuns w SQLite.

Nie oznaczać pełnego E2E jako zaliczonego bez rzeczywiście wykonanych testów wygenerowanego
produktu i końcowego ZIP. Testy własnej aplikacji z mockami nie zastępują tego sprawdzianu.
Aktualne wyniki i niewykonane etapy znajdują się w PROGRESS.md.
