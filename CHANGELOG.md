# Changelog

Toate schimbarile importante sunt notate aici.
Formatul urmeaza [Keep a Changelog](https://keepachangelog.com/ro/1.1.0/), iar versiunile [Semantic Versioning](https://semver.org/lang/ro/).

## [Unreleased]

## [0.4.0] - 2026-11-08

### Adaugat
- **Aplicatie cu fereastra proprie**: Abydex porneste ca un program normal (WebView2 pe Windows), fara browser
  si fara consola; daca fereastra nativa nu e disponibila, foloseste Edge/Chrome in mod aplicatie.
- **Update direct din aplicatie**: butonul *Actualizeaza* descarca versiunea noua de pe GitHub, verifica suma
  SHA-256, o instaleaza si reporneste aplicatia. Fiecare release are acum fisierul `SHA256SUMS.txt`.
- *Setari AI -> Despre Abydex*: versiunea instalata si butonul *Verifica update-uri*.
- Scurtatura *Abydex (mod depanare)*, cu consola, pentru diagnostic.

## [0.3.1] - 2026-11-08

### Adaugat
- Furnizor nou **llamafile / llama.cpp** (local, gratuit, fara cheie): Abydex foloseste direct un model
  pornit pe `http://127.0.0.1:8080`. Aplicatia verifica singura daca serverul local ruleaza.

### Reparat
- Raspunsurile modelelor care "gandesc cu voce tare" (Qwen3, DeepSeek-R1: blocuri `<think>`) sunt citite corect.

## [0.3.0] - 2026-11-08

### Schimbat
- **Proiectul se numeste acum Abydex**, cu sigla noua: un portal din circuite, cu o piramida printata
  strat cu strat. Comanda devine `abydex`, iar repo-ul `nDumitru/abydex`.
- Update-ul peste versiunile anterioare se face pe loc: installerul Windows inlocuieste versiunea veche si scurtaturile ei,
  iar datele (memoria printurilor, profilele, motoarele AI, setarile) se copiaza automat in folderul Abydex.

### Adaugat
- **AI la alegere** (tab-ul *Setari AI*): Ollama local sau, cu cheia ta, Anthropic Claude, OpenAI, Google Gemini,
  Mistral, DeepSeek, Groq, OpenRouter ori orice server compatibil OpenAI, pentru intelegerea pieselor libere.
- **3D in cloud** pentru obiecte decorative: Meshy si Tripo, utile pe PC-uri fara placa video puternica.
- Butonul *Testeaza AI-ul de text*; `abydex doctor` arata furnizorul ales (fara sa trimita cereri platite).
- Iconuri pentru installer, scurtaturi si interfata.

## 0.2.0 - 2026-11-08 (versiune de dezvoltare)

_Versiunile 0.1.0 si 0.2.0 au fost etape de dezvoltare, inainte de numele Abydex; nu mai sunt publicate.
Prima versiune publica este 0.3.0._

### Adaugat
- **Text -> 3D**: descrierea in romana sau engleza devine piesa gata de print. 6 sabloane parametrice
  (cutie cu capac, suport L, distantier/saiba, placa cu gauri, carlig, organizator cu compartimente)
  cu dimensiuni exacte, intelegerea suruburilor (M3 -> 3.4 mm) si a unitatilor (mm/cm). Merge offline, pe procesor.
- Parametrii interpretati se pot edita in interfata, apoi piesa se regenereaza.
- Model AI local optional (Ollama) pentru piese libere, descrise ca geometrie validata (date, nu cod).
- Obiecte decorative: text -> imagine (SD-Turbo) -> 3D (TripoSR).
- Invatare: cererile cu print reusit sunt refolosite si date ca exemple modelului AI.
- `abydex doctor` (verificarea instalarii), fisier de log, `abydex templates`, `abydex text`.

### Schimbat
- Suportul L si carligul se printeaza culcate, pentru rezistenta la indoire.
- Interfata isi cauta singura alt port daca 8765 e ocupat.

### Reparat
- Windows: installerul include acum runtime-ul Microsoft C++ (`msvcp140.dll`), care lipsea pe PC-urile fara
  "Visual C++ Redistributable".
- Windows: la o eroare, fereastra nu se mai inchide instant; ruleaza automat diagnosticul si il afiseaza.
- Build-ul de Windows e testat automat ca pe un PC real: porneste aplicatia instalata, genereaza o piesa
  si verifica interfata.

## 0.1.0 - 2026-11-08 (versiune de dezvoltare)

### Adaugat
- Reparare mesh: fragmente plutitoare, corpuri suprapuse unite, gauri inchise, normale reparate.
- Orientare automata pe pat si analiza piesei: dimensiuni, volum, console, perete minim, incadrare in volum.
- Catalog de materiale (FDM, rasina, SLS) si imprimante (Bambu, Prusa, Creality, generice), extensibil de utilizator.
- Recomandare de setari pe material + imprimanta + geometrie, care invata din feedback-ul printurilor (memorie SQLite locala).
- Export presetari Bambu Studio / OrcaSlicer (.json), PrusaSlicer (.ini) si fisa de setari (.md).
- Interfata web locala cu vizualizare 3D, istoric si feedback; linie de comanda completa.
- Motor optional poza -> 3D (TripoSR), functional si pe procesor, fara compilator.
- Migrari versionate ale bazei de date (cu backup automat) si verificare de versiune noua.
- Installer Windows (fara Python, fara admin), script de instalare Linux, build automat prin GitHub Actions.

[Unreleased]: https://github.com/nDumitru/abydex/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/nDumitru/abydex/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/nDumitru/abydex/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/nDumitru/abydex/releases/tag/v0.3.0
