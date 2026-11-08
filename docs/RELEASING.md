# Versiuni și release-uri

## Numerotare: `MAJOR.MINOR.PATCH` ([SemVer](https://semver.org/lang/ro/))

| Schimbare | Exemplu | Când |
|---|---|---|
| **PATCH** | 0.1.0 → 0.1.1 | reparații de bug-uri, profile de materiale corectate |
| **MINOR** | 0.1.1 → 0.2.0 | funcții noi (ex. text → 3D, motor AI nou), compatibile cu datele existente |
| **MAJOR** | 0.x → 1.0.0 | schimbări care cer acțiune de la utilizator; 1.0.0 = prima versiune „stabilă” |
| **Pre-release** | 0.2.0-beta.1 | versiuni de test; pe GitHub apar ca *Pre-release* și nu sunt oferite ca update stabil |

## Ramuri
- `main` e mereu funcțional: fiecare push rulează testele și construiește installerele.
- Lucrul nou se face pe ramuri (`feature/text-to-3d`, `fix/bambu-export`) și intră în `main` prin Pull Request.
- Fiecare release e un **tag** `vX.Y.Z` pe `main`.

## Pașii pentru un release
1. În `CHANGELOG.md`, la `## [Unreleased]`, notezi pe parcurs ce s-a schimbat (Adăugat / Schimbat / Reparat).
2. Rulezi:
   ```bash
   python scripts/release.py 0.2.0
   ```
   Scriptul schimbă versiunea în `abydex/__init__.py` și mută notele în secțiunea `[0.2.0]`.
3. ```bash
   git commit -am "Release v0.2.0"
   git push origin main
   ```
4. GitHub Actions rulează testele și construiește `Abydex-Setup-0.2.0.exe`, pachetul Linux și wheel-ul. Văzând că `v0.2.0` nu există încă, creează **automat** tag-ul și release-ul, cu notele din CHANGELOG. Push-urile pe `main` fără schimbare de versiune doar testează și construiesc.

   Funcționează și varianta clasică, cu tag pus manual (`git tag v0.2.0 && git push origin v0.2.0`). Dacă tag-ul nu se potrivește cu versiunea din cod, release-ul e oprit.

## Ce se păstrează la update (important!)
Datele utilizatorului stau **separat** de aplicație (`abydex info`):
- `abydex.db`: memoria (proiecte, setări, feedback). Schimbările de structură se fac **doar** adăugând o intrare nouă în `MIGRATIONS` din `abydex/memory.py`. Intrările deja publicate nu se modifică niciodată. Înainte de migrare se face automat backup (`abydex.db.bak-vN`).
- `printers.json` / `materials.json` personale: nu sunt atinse de update.
- Motoarele AI descărcate (`engines/`) și modelele: rămân.

Dacă schimbi „amprenta” formei (`shape_features` din `mesh_tools.py`), crește `FEATURES_VERSION`, ca piesele vechi să nu fie comparate greșit cu cele noi.

## Notificare de update
Aplicația verifică (maxim o dată pe zi) ultimul release de pe GitHub și arată un buton „Versiune nouă” în interfață. Se trimite doar o cerere publică către API-ul GitHub. Dezactivare: variabila de mediu `ABYDEX_NO_UPDATE_CHECK=1`. Manual: `abydex update`.
