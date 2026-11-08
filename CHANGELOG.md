# Changelog

Toate schimbarile importante sunt notate aici.
Formatul urmeaza [Keep a Changelog](https://keepachangelog.com/ro/1.1.0/), iar versiunile [Semantic Versioning](https://semver.org/lang/ro/).

## [Unreleased]

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

[Unreleased]: https://github.com/nDumitru/forja3d/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nDumitru/forja3d/releases/tag/v0.1.0
