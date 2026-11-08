# Changelog

Toate schimbarile importante sunt notate aici.
Formatul urmeaza [Keep a Changelog](https://keepachangelog.com/ro/1.1.0/), iar versiunile [Semantic Versioning](https://semver.org/lang/ro/).

## [Unreleased]

## [0.3.0] - 2026-11-08

### Schimbat
- **Proiectul se numeste acum Abydex** (fost Forja3D), cu sigla noua: un portal din circuite, cu o piramida printata
  strat cu strat. Comanda devine `abydex`, iar repo-ul `nDumitru/abydex`.
- Update-ul peste Forja3D se face pe loc: installerul Windows inlocuieste versiunea veche si scurtaturile ei,
  iar datele (memoria printurilor, profilele, motoarele AI, setarile) se copiaza automat in folderul Abydex.

### Adaugat
- **AI la alegere** (tab-ul *Setari AI*): Ollama local sau, cu cheia ta, Anthropic Claude, OpenAI, Google Gemini,
  Mistral, DeepSeek, Groq, OpenRouter ori orice server compatibil OpenAI, pentru intelegerea pieselor libere.
- **3D in cloud** pentru obiecte decorative: Meshy si Tripo, utile pe PC-uri fara placa video puternica.
- Butonul *Testeaza AI-ul de text*; `abydex doctor` arata furnizorul ales (fara sa trimita cereri platite).
- Iconuri pentru installer, scurtaturi si interfata.

## [0.2.0] - 2026-11-08

### Adaugat
- **Text -> 3D**: descrierea in romana sau engleza devine piesa gata de print. 6 sabloane parametrice
  (cutie cu capac, suport L, distantier/saiba, placa cu gauri, carlig, organizator cu compartimente)
  cu dimensiuni exacte, intelegerea suruburilor (M3 -> 3.4 mm) si a unitatilor (mm/cm). Merge offline, pe procesor.
- Parametrii interpretati se pot edita in interfata, apoi piesa se regenereaza.
- Model AI local optional (Ollama) pentru piese libere, descrise ca geometrie validata (date, nu cod).
- Obiecte decorative: text -> imagine (SD-Turbo) -> 3D (TripoSR).
- Invatare: cererile cu print reusit sunt refolosite si date ca exemple modelului AI.
- `forja3d doctor` (verificarea instalarii), fisier de log, `forja3d templates`, `forja3d text`.

### Schimbat
- Suportul L si carligul se printeaza culcate, pentru rezistenta la indoire.
- Interfata isi cauta singura alt port daca 8765 e ocupat.

### Reparat
- Windows: installerul include acum runtime-ul Microsoft C++ (`msvcp140.dll`), care lipsea pe PC-urile fara
  "Visual C++ Redistributable".
- Windows: la o eroare, fereastra nu se mai inchide instant; ruleaza automat diagnosticul si il afiseaza.
- Build-ul de Windows e testat automat ca pe un PC real: porneste aplicatia instalata, genereaza o piesa
  si verifica interfata.

## [0.1.0] - 2026-11-08

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

[Unreleased]: https://github.com/nDumitru/abydex/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/nDumitru/abydex/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/nDumitru/forja3d/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/nDumitru/forja3d/releases/tag/v0.1.0
