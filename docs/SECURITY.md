# Bezpieczeństwo

## Zakres zaufania

LocalAICompany jest jednoosobową aplikacją lokalną. Nasłuch tylko 127.0.0.1, jeden worker.
Nie wystawiać portu w LAN/internecie. Brak wieloużytkownikowej autoryzacji.
Procesy uruchomione przez tego samego użytkownika mają dostęp do API i danych.
TrustedHost, lista Origin i wymagany niestandardowy nagłówek X-LocalAI: 1 chronią operacje
przeglądarkowe przed typowymi żądaniami cross-site i DNS rebinding. Nie zastępują logowania.

## Kod z modeli

Nigdy nie jest wykonywany automatycznie. Statyczna analiza używa ast.parse, bez importu.
Zgoda jest jednorazowa, zawiera polecenie, ostrzeżenie i SHA256 każdego pliku. Po zmianie
plików zgoda nie działa. Runner tworzy kopię i ponownie weryfikuje hashe przed startem.
Kod ma pełne prawa użytkownika, w tym dostęp do plików i sieci. Timeout, -I, czyste
zmienne środowiska i stałe argv są ograniczeniami operacyjnymi, NIE sandboxem.
Wyjście testów i ich kod też pochodzą z niezaufanego źródła; złośliwy test może skłamać
w swoim stdout. Zgoda ma sens tylko po przeglądzie kodu. Przyszła wersja potrzebuje VM
lub innego rzeczywiście izolowanego ExecutionRunnera.

Runtime nie wykonuje poleceń powłoki od modeli, eval/exec, instalowania pakietów,
publikacji, masowego usuwania, płatności czy wysyłania wiadomości.
Przed wykonaniem kodu z nietypowymi importami albo dostępem do sieci odmów zgody.

## Pliki

Wyjścia modelu ograniczone do UUID projektu w workspace/projects. Odrzucane są ścieżki
absolutne, `..`, UNC, ADS, nazwy urządzeń Windows, symlinki, junctions i hardlinki.
Limity: 100 KB na plik, 100 plików, 2 MB na projekt, 20 plików w odpowiedzi Developera.
Własność zapisanych plików jest śledzona przez SHA256. Zmiany użytkownika blokują
nadpisanie do uzyskania odrębnej zgody z podglądem różnic.
Nie jest to zabezpieczenie przed równoczesnym atakiem lokalnego procesu na filesystem.

## Modele i dane

Tylko loopback HTTP, brak proxy z otoczenia i przekierowań. /api/show blokuje zdalne
aliasy. Nazwy cloud są odrzucane. Aplikacja nie pobiera modeli i nie korzysta z płatnych API.
Ollama to istniejąca instalacja użytkownika; jej niezależne ustawienia nie są zmieniane.
Plany, rozmowy i pliki pozostają w lokalnej bazie i workspace. Nie wklejaj sekretów do
rozmów, ponieważ historia jest trwała. Logi nie powinny zawierać promptów ani tokenów.

## Procesy

stop.ps1 używa wyłącznie zarejestrowanych PID wraz z czasem utworzenia i ścieżką pliku
wykonywalnego. Nie zatrzymuje wszystkich Pythonów/Node ani niezależnej Ollama.
Nagłe zatrzymanie backendu powoduje INTERRUPTED. Windows Job Object z KILL_ON_JOB_CLOSE
zamyka przyłączone procesy testów i ich potomków przy zamknięciu uchwytu. Ten mechanizm
zarządza czasem życia procesu, NIE izoluje plików ani sieci. Nie zakładamy ochrony przed
złośliwą próbą ucieczki przed przyłączeniem procesu do joba. Najpierw anuluj zadanie
i poczekaj na zakończenie, a dopiero potem zatrzymaj aplikację.
