# Kolejne etapy

Priorytet przed rozbudową autonomii: rozwiązać błędy składni początkowego kodu z
rzeczywistego qwen2.5-coder:7b. Zachowany rejected_proposal i metryki pozwalają
porównać celowaną korektę z pełną regeneracją, bez resetowania historycznych prób.
Dopiero po poprawnej wersji i zgodzie na jej hashe dokończyć realny TODO → testy → ZIP.
Wdrożono już edycje fragmentów, checkpointy, strukturalny kontekst, raporty QA,
wykrywanie braku postępu i szacowanie tokenów; ich dalsza rozbudowa wymaga dowodów potrzeby.

1. Rzeczywiście izolowany ExecutionRunner (VM) oraz testy odporności na złośliwy kod,
   procesy potomne, dostęp do sieci i trwałość wykonania po awarii hosta.
2. Większe projekty: selekcja zależności plików, testy pokrycia niezależne od kodu modelu,
   dokładniejszy pomiar tokenów, wersjonowanie plików i rozwój migracji bazy.
3. Oddzielne runnery JavaScript/TypeScript i kontrolowane środowiska zależności.
4. Opcjonalny moduł researchu internetowego z cytowaniami i rozróżnieniem źródeł/hipotez.
   Dziś moduł nie ma narzędzia sieciowego; ustawienie internet_enabled może być tylko false.
5. Różne zakresy autonomii dla projektów i harmonogramy przeglądów istniejących produktów.
   Obecna autonomia to wyłącznie polecone plany i ograniczone propozycje badawcze.
6. Wyszukiwanie semantyczne za interfejsem MemoryService, po wykazaniu potrzeby.
7. Autoryzacja i audyt wieloużytkownikowy przed jakimkolwiek udostępnieniem sieciowym.

Nie ma obecnie publikacji, płatności, poczty, reklam, automatycznej instalacji zależności
produktów ani gwarancji przychodów. Te funkcje nie są atrapami przycisków w panelu.
