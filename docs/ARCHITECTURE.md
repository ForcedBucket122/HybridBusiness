# Architektura

React -> REST/SSE FastAPI -> Service -> SQLite queue -> Orchestrator -> agent/Ollama -> tools.
Instalacja produkcyjna serwuje frontend i API z jednego procesu na 127.0.0.1:8000.
Tryb developerski używa dodatkowego Vite na 127.0.0.1:5173 z proxy /api.

## Moduły

- `schemas.py`: ścisłe wejścia API i wyniki modeli, parametry generowania.
- `database.py`: SQLAlchemy 2, WAL, foreign keys, Projects/Tasks/TaskRuns/Agents/
  ChatMessages/AgentMessages/MemoryEntries/Approvals/Artifacts/Events/SystemSettings.
- `service.py`: polecenia użytkownika, idempotencja request_id, konfiguracja, zgody,
  anulowanie, wznowienia i podsumowanie stanu projektu.
- `orchestrator.py`: atomowe claim przez BEGIN IMMEDIATE, jeden worker, deterministyczne
  zależności, ograniczone naprawy, skutki CEO/napraw zapisane do wznowienia bez duplikacji.
- `agents.py`: wspólny interfejs i odrębne prompty siedmiu agentów.
- `ollama.py`: lokalne /api/tags, /api/show, /api/chat, schemat JSON, retry, timeout.
- `tools.py` + `security.py`: jawny rejestr i kontrola ścieżek.
- `runner.py`: interfejs ExecutionRunner i zatwierdzany ApprovedHostRunner.
- `memory.py`: trwały, ograniczony kontekst, wyszukiwanie tekstowe po projekcie.
- `scheduler.py`: ograniczone propozycje okresowe; stan i liczniki w SQLite.
- `main.py`: cykl życia, blokada procesu, REST, SSE i zabezpieczenia przeglądarkowe.

## Kolejka

PENDING -> RUNNING -> COMPLETED / FAILED / WAITING_APPROVAL / CANCELLED.
Po restarcie RUNNING -> INTERRUPTED. Wznowienie jest jawne, w ramach limitu prób.
Zadania oczekują na COMPLETED wszystkich zależności. Błąd zależności blokuje wykonanie,
ale pozwala na ponowienie. Anulowanie zależności kaskadowo anuluje następców.
W MANUAL każdy nowy etap wymaga przycisku Uruchom; polecenie CEO uruchamia pierwszy etap.
W HYBRID/AUTONOMOUS wykonują się etapy planu zleconego przez użytkownika.

CEO produkuje plan do 4 kroków. Każdy Developer ma automatycznie dopięty QA.
QA statycznie parsuje Python i przegląda kod modelem. Następnie prosi o zgodę na testy.
Testy: `python -I -B -m unittest discover -s . -p test*.py -v`. Żadne polecenie nie
pochodzi z modelu. Wynik musi zawierać przynajmniej jeden wykonany test i exit code 0.
QA interpretuje rzeczywisty raport. Problemy tworzą zadanie naprawy i nowe QA, maks. 5 razy.
Release sprawdza dowody, zapisuje ZIP, manifest SHA256, README źródłowe i raport wydania.

## Granice odporności

SQLite i filesystem nie są wspólną transakcją. Przerwanie zapisu może pozostawić częściowe
pliki; po restarcie zadanie jest INTERRUPTED, nie COMPLETED. Nieznane pliki wymagają zgody
na nadpisanie. Gotowe wydanie ma unikalny task_id; odzyskiwanie nie tworzy drugiego ZIP.
Pozostałości `.localai.tmp` po nagłym przerwaniu wymagają ręcznego przeglądu/usunięcia.
Nie zakładamy ochrony przed złośliwym lokalnym procesem z prawami tego samego użytkownika.

## Źródła kontraktów

- Ollama chat: https://docs.ollama.com/api/chat
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- APScheduler 3: https://apscheduler.readthedocs.io/en/3.x/userguide.html
