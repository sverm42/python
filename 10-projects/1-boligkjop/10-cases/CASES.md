# Sverm — Cases

*Auto-generert fra sverm.db — 5 cases*

## Oversikt

| Status | Antall |
|--------|--------|
| Open | 5 |
| In Progress | 0 |
| Resolved | 0 |
| **Totalt** | **5** |

---

## Kjør Sverm

| Modus | Kommando | Beskrivelse |
|-------|---------|-------------|
| **focus** | `sverm launch focus <case#> --project 1 --medium -n 9` | Alle instanser jobber på **én** case (dybde) |

Modell: `--medium` (default) · `--small` (rask/billig) · `--large` (dyp). `-n 9` = 9 instanser. `--dry-run` for test.

---

## Åpne Cases

### 🔵 Case #1: Bør familien kjøpe rekkehuset nå?

**Prioritet:** critical | **Status:** open
**Tags:** beslutning,helhet

Vurder boligkjøpet helhetlig. Er dette en klok beslutning gitt økonomi, familieform og markedet? Hva bør de spørre om, tenke gjennom, eller vente med? Gi en klar anbefaling med begrunnelse.

**Kjør:**
```bash
sverm launch focus 1 --project 1 --medium -n 9
# --small (rask/billig) · --large (dyp) · --dry-run (test)
```

---

### 🔵 Case #2: Hva er den største risikoen ved dette kjøpet?

**Prioritet:** high | **Status:** open
**Tags:** risiko,analyse

Identifiser den viktigste risikoen og foreslå hvordan familien kan redusere eller forsikre seg mot den. Bruk seeden din til å fokusere på én type risiko — ikke forsøk å dekke alt.

**Kjør:**
```bash
sverm launch focus 2 --project 1 --medium -n 9
# --small (rask/billig) · --large (dyp) · --dry-run (test)
```

---

### 🔵 Case #3: Hva er alternativene hvis de IKKE kjøper nå?

**Prioritet:** high | **Status:** open
**Tags:** alternativer,opportunity-cost

Utforsk hva som skjer hvis familien venter, flytter et annet sted, eller investerer pengene på andre måter. Hva mister de? Hva vinner de? Lag minst to konkrete alternative scenarier.

**Kjør:**
```bash
sverm launch focus 3 --project 1 --medium -n 9
# --small (rask/billig) · --large (dyp) · --dry-run (test)
```

---

### 🔵 Case #4: Hvordan påvirker den lengre reiseveien familien?

**Prioritet:** normal | **Status:** open
**Tags:** livskvalitet,kostnad

35 minutter mot 15 minutter er 40 minutter mer per dag — 200 minutter i uken, 10 000 minutter per år. Utforsk hva dette koster i penger, tid, energi, og livsglede. Er det verdt det? Hvordan kompenseres det?

**Kjør:**
```bash
sverm launch focus 4 --project 1 --medium -n 9
# --small (rask/billig) · --large (dyp) · --dry-run (test)
```

---

### 🔵 Case #5: Er boligen riktig størrelse for familien nå OG om 5 år?

**Prioritet:** normal | **Status:** open
**Tags:** framtid,vekst

Barna er 7 og 10 nå. Om 5 år er de 12 og 15 — tenåringer som trenger eget rom og kanskje egen inngang. Om 15 år flytter de kanskje ut. Hva slags fleksibilitet bør familien planlegge for?

**Kjør:**
```bash
sverm launch focus 5 --project 1 --medium -n 9
# --small (rask/billig) · --large (dyp) · --dry-run (test)
```

---
