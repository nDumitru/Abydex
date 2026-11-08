# Forja3D 🔥

**Asistent AI local, open-source, pentru printare 3D.** Repară și orientează modelele, recomandă setări în funcție de **material + imprimantă + forma piesei** și **învață din fiecare print** pe care îl evaluezi. Opțional transformă o **poză într-un model 3D** (TripoSR), totul pe calculatorul tău, fără cloud.

> 🇬🇧 English summary at the bottom.

Funcționează pe **Windows și Linux**, inclusiv pe laptopuri **fără placă video** (testat pe profil i5 + grafică integrată).

## Ce face

| | |
|---|---|
| 🔧 **Reparare** | elimină fragmentele plutitoare, unește corpurile suprapuse, închide găurile, repară normalele |
| 📐 **Orientare automată** | alege fața pusă pe pat (mai puține console, contact mai bun) |
| 🔍 **Analiză** | dimensiuni, volum, procent de console, grosime minimă a pereților, verifică dacă piesa încape |
| 🧪 **Setări pe material** | PLA, PETG, ABS, ASA, TPU, PA, PC, variante CF · rășini (standard, ABS-like, lavabilă, flexibilă) · SLS PA12 |
| 🖨️ **Orice imprimantă** | FDM (Bambu, Prusa, Creality, generice), rășină MSLA, SLS. Poți adăuga imprimanta ta |
| 📤 **Export pentru slicer** | presetări Bambu Studio / OrcaSlicer (`.json`), PrusaSlicer (`.ini`) + fișă de setări (`.md`) |
| 🧠 **Învățare continuă** | după print dai feedback (reușit / warping / fire / crăpături...). Data viitoare, pentru piese **similare**, setările se ajustează automat |
| 🤖 **Poză → 3D (AI)** | TripoSR (MIT), local, merge și pe procesor |

### Cum învață

1. Fiecare piesă primește o „amprentă” geometrică (proporții, umplere, console, mărime).
2. Fiecare job salvează setările folosite. Feedback-ul tău se leagă de el (poți spune și ce ai schimbat manual în slicer).
3. La piesa următoare (aceeași imprimantă și același material), Forja3D caută printurile cele mai asemănătoare:
   - **reușitele** trag setările spre ce a mers;
   - **eșecurile** sunt mai întâi corectate cu reguli (de ex. *fire → −5 °C și +15 % retracție*, *crăpături → +5 °C și mai puțin ventilator*), apoi folosite ca exemplu.
4. Fiecare schimbare e explicată: *„Ventilator maxim: 6 % (bază 15 %) - învățat din 2 printuri similare”*.

Totul stă local, într-o bază SQLite (`forja3d info` îți arată folderul).

## Instalare

### Windows
Descarcă `Forja3D-Setup-x.y.z.exe` din [Releases](../../releases) și rulează-l. Nu cere drepturi de administrator și nu ai nevoie de Python instalat. Pornești din meniul Start → **Forja3D**: se deschide în browser.

### Linux
```bash
curl -fsSL https://raw.githubusercontent.com/nDumitru/forja3d/main/packaging/linux/install.sh | bash
```
sau din arhiva din Releases: `./packaging/linux/install.sh`. Apoi pornești cu `forja3d ui`.

### Din sursă (dezvoltatori)
```bash
git clone https://github.com/nDumitru/forja3d && cd forja3d
python -m pip install -e ".[dev]"
python -m pytest
forja3d ui
```

## Utilizare

**Interfața grafică:** `forja3d ui`. Tragi un STL în fereastră, alegi imprimanta și materialul, apeși *Pregătește*. Descarci presetările, printezi, apoi dai feedback.

**Linie de comandă:**
```bash
forja3d prepare suport.stl -p bambu_a1 -m asa -l 0.12
forja3d feedback 1 --fail --issues layer_split,stringing --rating 2
forja3d feedback 2 --ok --set nozzle_temp=255      # ai schimbat temperatura in slicer
forja3d history
forja3d printers | forja3d materials | forja3d issues
forja3d update                                       # exista o versiune noua?
```

**Import în Bambu Studio / OrcaSlicer:** *File → Import → Import Configs…*, apoi alegi fișierele `.filament.json` / `.process.json`. Presetările moștenesc profilul generic oficial (ex. `Generic ASA @BBL A1`), deci restul setărilor rămân cele testate de producător.

**Poză → 3D:**
```bash
forja3d engine install triposr     # o singura data, ~1-2 GB (PyTorch) + 1.7 GB model la prima rulare
forja3d generate cana.jpg -p bambu_a1 -m pla --size 80
```
Pe procesor durează ~1-3 minute și folosește ~6-8 GB RAM. Cu placă NVIDIA durează câteva secunde. Cele mai bune rezultate le obții cu o poză cu obiectul întreg, pe fundal simplu.

## Imprimante și materiale proprii
Creează `printers.json` sau `materials.json` în folderul de date (`forja3d info`), cu aceeași structură ca [forja3d/data](forja3d/data). Cheile noi se adaugă, iar cele existente se suprascriu.

## Update-uri și versiuni
- Instalezi versiunea nouă peste cea veche (Windows: rulezi noul `Setup.exe`; Linux: rulezi din nou scriptul). **Memoria, profilele tale și motoarele AI se păstrează.** Înainte de orice schimbare de structură, baza de date primește automat un backup.
- Aplicația îți arată în interfață când apare o versiune nouă. Dezactivezi cu `FORJA3D_NO_UPDATE_CHECK=1`.
- Ce s-a schimbat în fiecare versiune: [CHANGELOG.md](CHANGELOG.md). Cum se face un release: [docs/RELEASING.md](docs/RELEASING.md).

## Roadmap
- [x] v0.1: reparare, orientare, analiză, setări pe material, învățare din feedback, export slicer, UI web, TripoSR pe CPU, installere
- [ ] Text → 3D (text → imagine → 3D), plus TRELLIS și alte motoare pentru plăci video puternice
- [ ] Slicing direct prin OrcaSlicer CLI, estimare timp și consum
- [ ] Golire automată și găuri de drenaj pentru rășină
- [ ] Analiză foto a printului eșuat (detectare automată warping / stringing)
- [ ] Partajare opțională și anonimă a profilelor reușite în comunitate
- [ ] AppImage / Flatpak, interfață în engleză

## Contribuții
Detalii în [CONTRIBUTING.md](CONTRIBUTING.md).
Sunt binevenite, mai ales **profile de materiale și imprimante testate**: deschide un PR cu modificările în `forja3d/data/*.json` și spune ce ai testat.

## Licențe
Forja3D: MIT. three.js: MIT. TripoSR: MIT (se descarcă separat). Notă: Hunyuan3D nu e inclus intenționat, pentru că licența lui exclude UE.

---

### 🇬🇧 English
Forja3D is a local, open-source AI assistant for 3D printing. It repairs and auto-orients meshes, recommends print settings per material, printer and part geometry (FDM, resin, SLS), and exports Bambu Studio, OrcaSlicer and PrusaSlicer presets. It **learns from your print feedback**: successful prints pull settings toward what worked, and failed prints are corrected by rules before being used. It can also turn a photo into a 3D model locally with TripoSR, even on CPU only. Windows installer and Linux install script included. Run `forja3d ui` or `forja3d --help`.
