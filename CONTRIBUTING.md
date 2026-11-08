# Cum contribui la Abydex

Mulțumim! Orice ajutor contează, iar cel mai valoros e **experiența reală de printare**.

## Profile de materiale și imprimante
Cel mai simplu mod de a ajuta e să adaugi sau să corectezi date în `abydex/data/materials.json` și `abydex/data/printers.json`.
În Pull Request scrie pe ce imprimantă, cu ce material (producător) și cu ce rezultat ai testat.

## Cod
```bash
git clone https://github.com/nDumitru/abydex && cd abydex
python -m pip install -e ".[dev]"
python -m pytest
abydex ui
```
- Lucrează pe o ramură nouă (`feature/...` sau `fix/...`) și deschide un Pull Request spre `main`.
- Adaugă teste pentru comportament nou (`tests/`).
- Notează schimbarea în `CHANGELOG.md`, la `[Unreleased]`.
- Schimbi structura bazei de date? Adaugă o migrare nouă în `abydex/memory.py` (vezi [docs/RELEASING.md](docs/RELEASING.md)).

## Motoare AI noi
Un motor nou (ex. TRELLIS) se adaugă în `abydex/generate.py` (`ENGINES`) plus un runner în `abydex/engines/`. Rulează într-un proces separat și se instalează la cerere. Verifică licența: trebuie să permită folosirea în UE și redistribuirea.
