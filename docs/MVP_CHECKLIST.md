# Kryteria MVP — stan weryfikacji 2026-11-02

| Kryterium ze specyfikacji | Dowód / stan |
| --- | --- |
| 1. Lokalny Windows 11 | start/setup/stop wykonane w rzeczywistym środowisku |
| 2. Panel WWW | build TypeScript/Vite, Edge, 4 testy UI, realne wysłanie polecenia, raporty QA i checkpointy |
| 3. Backend | działające /api/health, REST, worker |
| 4. Trwała SQLite | historia i oczekująca zgoda przetrwały rzeczywisty restart |
| 5. Ollama | oba lokalne modele wykryte; prawdziwe zapytania CEO/Developer/QA |
| 6. CEO i plan | plan zapisany dla rzeczywistego polecenia TODO |
| 7. Delegowanie | 8 historycznych zadań w SQLite; nowa normalizacja scala kolejne prace programistyczne |
| 8. Rzeczywiste pliki | 3 pliki w workspace/projects/8a58aef75bd04a4dbe4d486a2d416aef |
| 9. QA kodu i wyników testów | analiza lokalnym modelem pominęła błędy; zatwierdzone wykonanie realnego produktu wykazało 3 błędy w 4 testach, raport przekazany do QA |
| 10. Przekazanie błędów Developerowi | potwierdzone również realnym E2E: po 3 błędach testów powstały zadania Poprawki 1 i Weryfikacja poprawek 1 |
| 11. Kontrolowane próby | testy limitów prób i maksymalnej iteracji napraw przechodzą |
| 12. Prawdziwy postęp | SSE z trwałych zdarzeń, stan API w panelu |
| 13. Anulowanie | testy kolejki i prawdziwego procesu fixture na Windows przechodzą |
| 14. Restart | testy recovery i faktyczne restarty; po ulepszeniach identyczne audyty 22 zadań, 17 prób, 4 checkpointów i pozostałych danych |
| 15. Zatwierdzenia | brak zgody blokuje wykonanie; hash binding i jednorazowość przetestowane |
| 16. Pobranie artefaktu | integracja API/ZIP z prawdziwym runnerem na zaufanym fixture; brak ZIP realnego TODO |
| 17. Podstawowe testy | 67 pass, 2 skip; wcześniejszy osobny live 1 pass; frontend 4 pass |
| 18. README | instalacja, start, stop, testy, ograniczenia i dalsza praca opisane |

**Nie ogłoszono w pełni zweryfikowanego MVP.** Po zgodzie użytkownika testy realnego
produktu wykonano: 4 testy, 3 błędy, exit code 1. Raport jest zapisany na dysku i w SQLite.
Kryteria dotyczące realnych poprawek, ponownej weryfikacji i wydania wymagają dokończenia.

Po ulepszeniach wykonano nowy E2E `0a87073016a245c79d05873479265584`. CEO ukończył plan,
ale dwie odpowiedzi Developera miały błędy składni; obie zablokowano przed zapisem.
Brak nowego wykonania testów i ZIP. Nowe regresje potwierdzają celowane edycje,
zatrzymanie NO_PROGRESS i przekazanie prawdziwych błędów; nie zastępują zaliczenia
realnego przepływu modelowego. Historyczny projekt osiągnął limit 5 napraw.
