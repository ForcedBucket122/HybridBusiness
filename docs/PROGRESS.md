# Postęp LocalAICompany

Aktualizacja: 2026-11-02 (Europe/Warsaw). Projekt powstał w A:\HybridBusiness.

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
- pytest: 54 zaliczone, 2 pominięte (symlink privilege, opcjonalny test live), po dodaniu
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

Sprawdzić automatyczne przekazanie rzeczywistego raportu błędów Developerowi, przygotowane
naprawy i kolejną analizę QA. Nowa wersja kodu wymaga nowej zgody na wykonanie.
Potem wdrożyć izolowany runner i niezależne testy akceptacyjne, aby ograniczyć zależność
od jakości przeglądu qwen3:4b. Nie oznaczać wszystkich 18 kryteriów MVP jako zweryfikowanych.
