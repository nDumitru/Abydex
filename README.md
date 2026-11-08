<p align="center"><img src="docs/abydex-512.png" width="140" alt="Abydex"></p>

# Abydex

> Numele vine de la Abydos, orașul antic al Egiptului. Sigla e un portal din circuite, cu o piramidă printată strat cu strat.

**Asistent AI local, open-source, pentru printare 3D.** Repară și orientează modelele, recomandă setări în funcție de **material + imprimantă + forma piesei** și **învață din fiecare print** pe care îl evaluezi. Transformă **text sau poze în modele 3D**. Totul merge local, pe calculatorul tău; serviciile AI online (Claude, OpenAI, Gemini, Meshy, Tripo...) sunt opționale, cu cheia ta.

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
| ✍️ **Text → 3D** | *„cutie 80x50x30 cu capac, perete 2 mm”* → piesă cu dimensiuni exacte, instant, fără internet și fără placă video. Obiectele decorative se fac prin AI (text → imagine → 3D) |
| 🤖 **Poză → 3D (AI)** | TripoSR (MIT), local, merge și pe procesor |

### Cum învață

1. Fiecare piesă primește o „amprentă” geometrică (proporții, umplere, console, mărime).
2. Fiecare job salvează setările folosite. Feedback-ul tău se leagă de el (poți spune și ce ai schimbat manual în slicer).
3. La piesa următoare (aceeași imprimantă și același material), Abydex caută printurile cele mai asemănătoare:
   - **reușitele** trag setările spre ce a mers;
   - **eșecurile** sunt mai întâi corectate cu reguli (de ex. *fire → −5 °C și +15 % retracție*, *crăpături → +5 °C și mai puțin ventilator*), apoi folosite ca exemplu.
4. Fiecare schimbare e explicată: *„Ventilator maxim: 6 % (bază 15 %) - învățat din 2 printuri similare”*.

Totul stă local, într-o bază SQLite (`abydex info` îți arată folderul).

## Instalare

### Windows
Descarcă `Abydex-Setup-x.y.z.exe` din [Releases](../../releases) și rulează-l. Nu cere drepturi de administrator și nu ai nevoie de Python instalat. Pornești din meniul Start → **Abydex**: se deschide o fereastră neagră (serverul local, o lași deschisă) și aplicația în browser.

- Windows poate afișa *„Windows protected your PC”*, pentru că installerul nu e semnat digital încă: apeși *More info → Run anyway*.
- Dacă ceva nu merge, fereastra neagră rămâne deschisă cu un raport. Îl poți genera oricând din *Start → Abydex - linie de comandă* cu `abydex doctor`. Trimite-l într-un [issue](../../issues).

### Linux
```bash
curl -fsSL https://raw.githubusercontent.com/nDumitru/abydex/main/packaging/linux/install.sh | bash
```
sau din arhiva din Releases: `./packaging/linux/install.sh`. Apoi pornești cu `abydex ui`.

### Din sursă (dezvoltatori)
```bash
git clone https://github.com/nDumitru/abydex && cd abydex
python -m pip install -e ".[dev]"
python -m pytest
abydex ui
```

## Utilizare

**Interfața grafică:** `abydex ui`. Tragi un STL în fereastră, alegi imprimanta și materialul, apeși *Pregătește*. Descarci presetările, printezi, apoi dai feedback.

**Linie de comandă:**
```bash
abydex prepare suport.stl -p bambu_a1 -m asa -l 0.12
abydex feedback 1 --fail --issues layer_split,stringing --rating 2
abydex feedback 2 --ok --set nozzle_temp=255      # ai schimbat temperatura in slicer
abydex history
abydex printers | abydex materials | abydex issues
abydex update                                       # exista o versiune noua?
abydex doctor                                       # verifica instalarea (pentru raportare probleme)
```

**Import în Bambu Studio / OrcaSlicer:** *File → Import → Import Configs…*, apoi alegi fișierele `.filament.json` / `.process.json`. Presetările moștenesc profilul generic oficial (ex. `Generic ASA @BBL A1`), deci restul setărilor rămân cele testate de producător.

**Text → 3D:**
```bash
abydex text "cutie 80x50x30 cu capac, perete 2 mm" -p bambu_a1 -m pla
abydex text "suport L 50x40x20 cu gauri M4" -p bambu_a1 -m petg
abydex text "organizator 150x100x40 cu 4x3 compartimente" --show   # doar arata cum a inteles
abydex templates                                                   # toate tipurile de piese
```
Înțelege română și engleză, dimensiuni în mm sau cm, șuruburi (`M3` → gaură de 3,4 mm, cu joc pentru print). Șabloane: **cutie/carcasă** (cu capac), **suport L**, **distanțier/șaibă**, **placă cu găuri**, **cârlig**, **organizator cu compartimente**. Piesele sunt orientate pentru rezistență: suportul L și cârligul se printează culcate. În interfață vezi ce a înțeles, poți schimba orice valoare și regenerezi.

- **Învață:** cererile ale căror printuri le-ai marcat *Reușit* sunt refolosite data viitoare și date ca exemplu modelului AI.
- **Piese libere (opțional):** un model AI înțelege și piese care nu sunt în șabloane (de ex. *„flanșă rotundă cu 6 găuri pe cerc”*). Modelul produce doar o descriere de geometrie (date, nu cod), pe care Abydex o verifică înainte să construiască piesa. Vezi mai jos *AI la alegere*.
- **Obiecte decorative:** pentru figurine, vaze sau animale instalezi din tab-ul *Motoare AI* „SD-Turbo” și „TripoSR”. Descrierea devine imagine, iar imaginea devine model 3D (câteva minute pe procesor). Scrie descrierea în engleză pentru rezultate mai bune.

**Poză → 3D:**
```bash
abydex engine install triposr     # o singura data, ~1-2 GB (PyTorch) + 1.7 GB model la prima rulare
abydex generate cana.jpg -p bambu_a1 -m pla --size 80
```
Pe procesor durează ~1-3 minute și folosește ~6-8 GB RAM. Cu placă NVIDIA durează câteva secunde. Cele mai bune rezultate le obții cu o poză cu obiectul întreg, pe fundal simplu.

## Imprimante și materiale proprii
Creează `printers.json` sau `materials.json` în folderul de date (`abydex info`), cu aceeași structură ca [abydex/data](abydex/data). Cheile noi se adaugă, iar cele existente se suprascriu.

## AI la alegere (tab-ul *Setări AI*)

| Pentru | Opțiuni |
|---|---|
| Înțelegerea textului | **Ollama** (local, gratuit, offline: instalezi [Ollama](https://ollama.com), apoi rulezi `ollama pull qwen2.5-coder:3b`) · **llamafile / llama.cpp** (local, gratuit: pornești serverul, de obicei pe `http://127.0.0.1:8080`, și îl alegi în Setări AI) · **Anthropic Claude** · **OpenAI** · **Google Gemini** · **Mistral** · **DeepSeek** · **Groq** · **OpenRouter** · orice server compatibil OpenAI (LM Studio, vLLM) |
| Obiecte decorative în cloud | **Meshy** · **Tripo**: mai rapide decât generarea locală pe un PC fără placă video |

- Cheile API rămân doar pe calculatorul tău (`settings.json` în folderul de date) și nu apar niciodată în interfață. Variabilele de mediu (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `MESHY_API_KEY`, `TRIPO_API_KEY`...) au prioritate.
- Când alegi un serviciu online, descrierea piesei se trimite la el, iar costurile sunt cele ale furnizorului.
- Dacă serviciul nu răspunde sau cheia e greșită, Abydex continuă cu regulile locale, deci piesele tehnice merg oricum.
- Claude e apelat prin SDK-ul oficial `anthropic`, cu răspuns JSON garantat prin schemă (structured outputs). Dacă un filtru de siguranță refuză cererea, API-ul o reia automat pe un model de rezervă (`fallbacks: "default"`).

## Update-uri și versiuni
- Instalezi versiunea nouă peste cea veche (Windows: rulezi noul `Setup.exe`; Linux: rulezi din nou scriptul). **Memoria, profilele tale și motoarele AI se păstrează.** Înainte de orice schimbare de structură, baza de date primește automat un backup.
- Aplicația îți arată în interfață când apare o versiune nouă. Dezactivezi cu `ABYDEX_NO_UPDATE_CHECK=1`.
- Ce s-a schimbat în fiecare versiune: [CHANGELOG.md](CHANGELOG.md). Cum se face un release: [docs/RELEASING.md](docs/RELEASING.md).

## Roadmap
- [x] v0.1: reparare, orientare, analiză, setări pe material, învățare din feedback, export slicer, UI web, TripoSR pe CPU, installere
- [x] v0.2: text → 3D (șabloane parametrice + AI local opțional + text → imagine → 3D), `abydex doctor`, installer Windows mai robust
- [ ] TRELLIS și alte motoare pentru plăci video puternice
- [ ] Slicing direct prin OrcaSlicer CLI, estimare timp și consum
- [ ] Golire automată și găuri de drenaj pentru rășină
- [ ] Analiză foto a printului eșuat (detectare automată warping / stringing)
- [ ] Partajare opțională și anonimă a profilelor reușite în comunitate
- [ ] AppImage / Flatpak, interfață în engleză

## Contribuții
Detalii în [CONTRIBUTING.md](CONTRIBUTING.md).
Sunt binevenite, mai ales **profile de materiale și imprimante testate**: deschide un PR cu modificările în `abydex/data/*.json` și spune ce ai testat.

## Licențe
Abydex: MIT. three.js: MIT. TripoSR: MIT (se descarcă separat). SD-Turbo: licența Stability AI (se descarcă separat, verifică termenii pentru uz comercial). Modelele Ollama au licențele lor. Notă: Hunyuan3D nu e inclus intenționat, pentru că licența lui exclude UE.

---

### 🇬🇧 English
Abydex is a local, open-source AI assistant for 3D printing. It repairs and auto-orients meshes, recommends print settings per material, printer and part geometry (FDM, resin, SLS), and exports Bambu Studio, OrcaSlicer and PrusaSlicer presets. It **learns from your print feedback**: successful prints pull settings toward what worked, and failed prints are corrected by rules before being used. It can also turn a photo into a 3D model locally with TripoSR, even on CPU only. Windows installer and Linux install script included. Run `abydex ui` or `abydex --help`.
