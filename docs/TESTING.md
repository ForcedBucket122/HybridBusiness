# Testowanie

Ostatnia weryfikacja po ulepszeniach (2026-11-02): backend **67 passed, 2 skipped**,
frontend **4 passed**, build TypeScript/Vite zaliczony. Realny E2E negatywny:
Developer zwrócił błędną składnię w obu dozwolonych próbach. Nie wykonywano tych plików.

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

`tests/test_improvements.py`: exact-match edits, tworzenie brakujących plików bez
nadpisania istniejących, składnia, zachowanie nazw testów, brak postępu, parsowanie
traceback, aktualne dowody w kontekście, checkpoint częściowego zapisu, zmiany
użytkownika, pamięć, przekroczenie budżetu, odrzuty kodu i zmiana plików podczas QA.
Frontend sprawdza również raport QA i historię checkpointów oraz wybór nowego
projektu przy istniejącym poprzednim projekcie.

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
i zrzuty ekranu z osobnym znacznikiem czasu. Opcjonalne LOCALAI_E2E_PROJECT wybiera
już istniejący pusty projekt. Dalsze zadania wykonuje aplikacja. Sprawdź pliki przed akceptacją testów.
Zgoda użytkownika jest wymagana także podczas testu prowadzonego przez Codex.
Po zgodzie weryfikacja obejmuje raport runnera, nie tylko tekst odpowiedzi QA,
oraz zawartość ZIP, SHA256 i wpisy TaskRuns w SQLite.

Nie oznaczać pełnego E2E jako zaliczonego bez rzeczywiście wykonanych testów wygenerowanego
produktu i końcowego ZIP. Testy własnej aplikacji z mockami nie zastępują tego sprawdzianu.
Aktualne wyniki i niewykonane etapy znajdują się w PROGRESS.md.

`scripts/audit_state.py before-restart` oraz `after-restart` czytają SQLite w trybie
read-only i zapisują liczniki oraz hashe tabel w logs. Rzeczywisty restart po obecnych
zmianach dał identyczne raporty, integrity_check=ok. `scripts/inspect-ui.mjs` jest
odczytowym sprawdzeniem widoczności bieżącego błędu składni i checkpointu w panelu;
ustaw LOCALAI_E2E_PROJECT na projekt nowego E2E. Żaden z tych skryptów nie zatwierdza kodu.
