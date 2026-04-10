# Seed-design — Hvordan skrive frequency seeds som fungerer

> *Dårlige seeds gir deg varianter av samme svar. Gode seeds gir deg genuint forskjellige analyser — og det er dissensen mellom dem som åpner innsikten.*

Dette dokumentet forklarer hvordan du designer frequency seeds for ditt eget sverm-prosjekt. Det er den viktigste ferdigheten i sverm-metodikken. En god seed-design kan gjøre forskjellen mellom en flight som gir deg ekte nye perspektiver, og en flight som bare omskriver det samme svaret ni ganger.

---

## Hva er en frequency seed?

En **frequency seed** er et sett med vektede ord som farger perspektivet til én AI-instans. Hver instans i en sverm-flight får sin egen unike seed, trukket vektet fra *aksene* du har definert i JSON-configen.

**Eksempel fra boligkjøp-demoet:**

```
VS_001: økonom | umiddelbart | renterisk | livskvalitet | analytisk
VS_002: forelder | mellomlang | markedsrisk | forankring | intuitiv
VS_003: pragmatiker | lang | jobbrisk | fleksibilitet | konsensusbasert
```

Hver instans får ett ord fra hver akse. Samme case, samme rådata — men genuint forskjellige analyser fordi seedene skaper forskjellige mentale ståsteder.

---

## Akser — byggeklossene

En *akse* er en dimensjon som perspektivene kan variere langs. En god sverm-config har **5 akser** med **5-10 ord per akse**. Det gir deg 3 125 til 100 000 mulige kombinasjoner, langt mer enn nok for en 9-instans-flight uten duplikater.

### Hva en akse er IKKE

Før vi snakker om hva en god akse ER, la oss peke på det som ikke fungerer:

- **"Ekspertise-nivå"** (novice → expert) — dette er en skala, ikke en akse. Det gir bare ett kontinuum, ikke forskjellige ståsteder.
- **"Positiv ↔ negativ"** — kunstig polarisering. En økonom og en forelder er begge ekte perspektiver, ikke "positiv" og "negativ".
- **"Ulike bransjer"** som eneste akse — det gir bredde, ikke dybde.

### Hva en god akse ER

En god akse fanger én *mental bevegelse* som leserne kan gjøre fra ord til ord. Ordene i aksen er ikke bare forskjellige — de representerer *ulike måter å se på problemet*.

**Eksempel på god akse — "rolle":**

```json
{
  "name": "rolle",
  "words": [
    {"word": "økonom", "weight": 0.80, "description": "Ser cashflow, rentesensitivitet, avkastning"},
    {"word": "forelder", "weight": 0.70, "description": "Ser barnas hverdag, skole, lekemiljø"},
    {"word": "pragmatiker", "weight": 0.55, "description": "Ser hverdagslogistikk, tid, stressnivå"},
    {"word": "langtidsplanlegger", "weight": 0.45},
    {"word": "risikoavers", "weight": 0.25},
    {"word": "opportunist", "weight": 0.10}
  ]
}
```

Her er hver rolle en reell måte å nærme seg problemet på. De er ikke komplementære (alle "delvis sanne"), de er *alternative*.

---

## De fem gode aksene

Over alle sverm-prosjektene våre har vi sett at disse fem akse-typene fungerer gjentagende godt:

### 1. Perspektiv / rolle
*Fra hvem sitt ståsted ser vi dette?*

Eksempler: økonom, forelder, ingeniør, kunde, investor, regulator, historiker, aktivist, partner, terapeut

Dette er den sterkeste aksen i de fleste cases. Den gir store, distinkte innsikter.

### 2. Tidshorisont
*Over hvilket tidsrom tenker vi?*

Eksempler: umiddelbart (dager-måneder), mellomlang (1-3 år), lang (5-10 år), generasjon (25+ år), inneværende-valgperiode, neste-kvartal

En beslutning som ser rasjonell ut over 6 måneder kan være katastrofal over 10 år, og omvendt. Denne aksen fanger det.

### 3. Risiko / feiltype
*Hva er verst tenkelige utfall — og hvilken type risiko?*

Eksempler: finansiell-risk, helserisk, markedsrisk, konkurrent-kopierer, regulatorisk-endring, teknologi-skift, familiestress, omdømme-tap

Å tvinge én instans til å fokusere på "hva hvis den største feilen blir X" gir helt andre råd enn en instans som tenker "alt går bra".

### 4. Verdi / motivasjon
*Hva er egentlig viktigst?*

Eksempler: livskvalitet, fleksibilitet, mestring, mening, trygghet, status, frihet, forankring, effektivitet, rettferdighet

To økonomisk like valg kan være helt forskjellige moralsk. Denne aksen fanger at.

### 5. Beslutningsramme / metode
*Hvordan bør selve beslutningen tas?*

Eksempler: analytisk, intuitiv, konsensusbasert, ekspertbasert, eksperimentell, verdibasert, mimetisk, rasjonell

Dette er en meta-akse — den bestemmer ikke hva du velger, men hvordan du velger. Ofte overraskende viktig.

---

## Vekting — det som virkelig betyr noe

Hvert ord i en akse har en **vekt** (0.00-1.00) som bestemmer hvor ofte det blir trukket. Høye vekter er *kjerneord* som dukker opp ofte. Lave vekter er *reframers* — de sjeldne ordene som forhindrer at alle analysene ender i samme middelverdi.

### Regel: Høye vekter forankrer, lave vekter redder

```
0.75 - 0.85   KJERNEORD. Disse definerer domenet.
              Minst 2-3 per akse. Dukker opp i de fleste instanser.

0.50 - 0.65   TYPISKE PERSPEKTIVER. Vanlige tilgangsmåter.
              De fleste flights har 2-3 av disse.

0.25 - 0.45   STØTTEORD. Sjeldne nok til å være friske, vanlige nok
              til å være håndterbare.

0.05 - 0.20   REFRAMERS. De "rare" ordene. Dukker opp i 1 av 10-20 instanser.
              Disse er OFTE hvor innsikten kommer fra.
              IKKE HOPP OVER LAVE VEKTER. De er det viktigste.

0.01 - 0.04   EKSTREME REFRAMERS. Bruk forsiktig — kun hvis du faktisk
              vil ha den reframingen tilgjengelig.
```

### Hvorfor lave vekter er kritiske

Hvis alle ordene dine har vekt 0.5-0.7, vil hver instans få et "typisk" perspektiv. Resultatet: 9 instanser, 9 varianter av samme analyse.

Hvis du har én lav-vekt-reframer som *"opportunist"* (0.10) eller *"risikoavers"* (0.25), vil én av 9 instanser trekke det ordet — og den instansen vil skrive en helt annen analyse enn de åtte andre. **Den annerledes analysen er ofte den mest verdifulle.** Den bryter konvergensen.

---

## Diagnose — er dine seeds gode nok?

Før du kjører en ekte flight, still deg disse spørsmålene om hver akse:

### 1. Har aksen minst én reframer under 0.20?
Hvis alle ord er >0.30, vil aksen bare generere "middelvarianter". Legg til minst ett lavt-vektet alternativ.

### 2. Er ordene gjensidig ekskluderende?
To ord skal ikke være synonymer. *"økonom"* og *"finansperspektiv"* er for like. Velg ett.

### 3. Er det minst 5 ord i aksen?
Færre enn 5 gir ikke nok variasjon. Flere enn 10 blir uoversiktlig og vanskelig å vekte.

### 4. Ville en 65-åring og en 25-åring sett forskjell?
Hvis aksen ikke fanger reelle menneskelige forskjeller, er den bare abstraksjon. Test den mot ekte folk.

### 5. Er aksene uavhengige?
Aksene dine skal være ortogonale. *"Rolle"* og *"yrke"* er nesten samme akse. *"Tidshorisont"* og *"risiko"* kan være relaterte men kan holdes separate. Test: Kan hvilken som helst kombinasjon av ord oppstå meningsfullt?

---

## Vanlige feil

### Feil 1: For generiske ord
Dårlig: `"optimist"`, `"pessimist"`, `"realist"` — disse er abstrakte stemninger, ikke perspektiver
Bedre: `"vekst-entusiast"`, `"risiko-kritiker"`, `"veteran"` — gir konkret mental retning

### Feil 2: For få lave vekter
Dårlig: Alle ord vektet 0.5-0.8 — konvergens
Bedre: 60% av ordene >0.5, 30% mellom 0.2-0.5, 10% under 0.2

### Feil 3: Akser som overlapper
Dårlig: "perspektiv" (økonom/forelder) + "fagfelt" (økonomi/familieliv) — redundant
Bedre: "perspektiv" (rolle) + "tidshorisont" (når) — komplementært

### Feil 4: For få akser
Dårlig: 2-3 akser — ikke nok variasjon mellom instanser
Bedre: 5 akser (3 kjerne + 2 reframers)

### Feil 5: For mange akser
Dårlig: 7-8 akser — prompter blir lange, seeds blir kaotiske
Bedre: Komprimér til 5 ortogonale akser

### Feil 6: Glemmer `description`-feltet
Dårlig: Bare ord og vekter — AI-en må gjette hva ordet betyr i din kontekst
Bedre: Legg til 1 setning per ord som forklarer hva det *gjør* for perspektivet

---

## Praktisk workflow: fra tom fil til første flight

1. **Definér domenet** i 2-3 setninger. Hva handler dette egentlig om?
2. **Skriv målet.** Hva vil du sverm skal hjelpe deg med?
3. **List opp nøkkelinfo** — 5-10 fakta som enhver analyse må kjenne til
4. **Brainstorm 5 akser** — start med "rolle", "tid", "risiko", "verdi", "metode"
5. **For hver akse, skriv 6-10 ord** med beskrivelser
6. **Vekt ordene** — høy for kjerne, lav for reframers
7. **Skriv 3-5 cases** — spesifikke nok til å handle på, brede nok for seed-variasjon
8. **Test med `--dry-run`** — se hvilke kombinasjoner svermen genererer
9. **Kjør først en liten flight** (`-n 4 --small`) for å sjekke output-kvalitet
10. **Juster seeds** basert på hva du faktisk får tilbake

---

## Test dine seeds — kvalitetssjekk

Etter en første flight, les outputene. Still deg:

- **Er de forskjellige?** Hvis du kan bytte forfatternavn mellom to outputs og ingen merker det, er seedene for svake.
- **Dukker det opp overraskelser?** Hvis svarene er forutsigbare, mangler du reframers (lave vekter).
- **Reflekterer seeden seg i teksten?** En "forelder"-seed bør prate om barn. En "økonom"-seed bør prate om tall. Hvis seedene ikke synes i output-teksten, tyder det på at prompten eller aksen er for svak.
- **Er det dissens?** Ideell sverm-flight har 2-3 klynger som er uenige. Hvis alle er enige, har du ikke differensiert nok.

Juster og kjør igjen. Sverm-design er iterativt.

---

## Hvor mange instanser trenger du?

| Antall | Bruk |
|--------|------|
| **3-4** | Dry-run, sanity check, første test av ny config |
| **9** | Standard focus-flight. Nok til å se dissens og klynger |
| **15-20** | Dypere analyse. Når du vil være sikker på å treffe reframers |
| **50+** | Metodikk-eksperimenter, paper-skriving, veldig komplekse cases |

**Default er 9.** Det er det magiske tallet — nok til å se tre distinkte klynger, men lite nok til å lese alle outputene.

---

## Eksempler på gode seed-designs

Se disse configene i `examples/`:

- **`boligkjop.json`** — Personlig beslutning, 5 klassiske akser
- **`restaurant.json`** — Forretningslansering, roller + faser + risiko
- **`karriere.json`** — Personlig beslutning med psykologi-dimensjon
- **`produktlansering.json`** — Tech/SaaS med markeds- og konkurransefokus
- **`kommune-beslutning.json`** — Offentlig sektor med verdikompass

Alle fem har 5 akser med vekting fra 0.10 til 0.85, med beskrivelser på de fleste ordene. Åpne dem og diff dem — se hvordan samme struktur (5 akser × 5-10 ord) produserer helt forskjellige semantiske rom.

---

## Sluttsjekk før du kjører ekte flight

- [ ] 5 akser, ikke færre, ikke flere
- [ ] Hver akse har 5-10 ord
- [ ] Hver akse har minst ett ord med vekt < 0.20 (reframeren)
- [ ] Hver akse har minst to ord med vekt > 0.60 (kjerneordene)
- [ ] Ingen synonymer innen en akse
- [ ] Aksene er ortogonale (tester: kan hvilken som helst kombinasjon eksistere meningsfullt?)
- [ ] Hver case er spesifikk nok til å handle på
- [ ] `key_info` i domenet dekker det som må være kjent for å svare
- [ ] Dry-run kjørt og seed-kombinasjoner ser fornuftige ut
- [ ] Første ekte flight (n=4, --small) gir genuint forskjellige outputs

---

Lykke til med svermen. Send gjerne spørsmål til raymond@sverm.ai.
