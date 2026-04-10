# CLAUDE.md — Sverm-Prosjekt: boligkjop

---

## Prosjektkontekst

**Domene:** En norsk småbarnsfamilie vurderer å kjøpe rekkehus i en forstad. De må vurdere økonomi, familieliv, lokasjon, risiko og langsiktig planlegging før de bestemmer seg.

**Nøkkelinfo:**
- Familien består av to voksne og to barn (7 og 10 år)
- Samlet bruttoinntekt: 1.2 MNOK. Egenkapital: 800 000 kr
- De ser på et rekkehus i en forstad ca 30 minutter fra sentrum. Prisantydning: 6.5 MNOK
- Nåværende leilighet kan selges for ca 4.2 MNOK (netto etter lån)
- Rentenivået har steget 1.5 prosentpoeng siste år. Analytikere er uenige om videre utvikling
- Skolen i det nye området er rangert som middels god
- Reisevei til jobb øker fra 15 til 35 minutter hver vei
- Nabolaget har gode uteområder, lekeplasser og idrettsanlegg
- Barna må bytte skole hvis familien flytter

**Mål:** Hjelp familien å vurdere boligkjøpet fra mange vinkler — økonomi, familie, lokasjon, timing, risiko — og gi konkrete råd som tar hensyn til helheten, ikke bare ett perspektiv.

---

## For Sverm-Instanser

Hvis du er en AI-instans spawnet av dette systemet:

1. **Les prompten din** — den inneholder din ID, seed og oppdrag
2. **Les forrige debrief(er) i `30-debrief/`** — bygg videre, ikke gjenta
3. **La seeden farge perspektivet aktivt**
4. **Skriv output til angitt fil** — `20-flights/FLT_XXX/VS_XXXX_output.md`
5. **Start output med metadata-header:**
   ```
   # VS_XXXX — [Case-tittel]
   seed: ord1 | ord2 | ord3 | ord4 | ord5
   model: haiku/sonnet/opus
   ```

### Output-kvalitet

- **Vær konkret og gjennomførbar**
- **Navngi ressursbehov** — tid, penger, kompetanse, koordinering
- **Dissens er verdifullt** — si hva som er naivt, hva som vil mislykkes
- **Avslutt med neste steg** — ett konkret handlingspunkt

---

## Sverm-Arkitektur

### Quick Start

```bash
# Hjelp og kommandoer
sverm launch --help

# Focus mode — 4 små instanser på case #1 (default model + count)
sverm launch focus 1

# Inbox mode — hver instans velger 1-3 cases selv basert på seed
sverm launch inbox

# Batch mode — alle cases partisjoneres deterministisk
sverm launch batch

# Dry-run (test uten å bruke tokens)
sverm launch focus 1 --dry-run

# Eskaler når oppsettet er validert
sverm launch focus 1 --medium -n 9
```

Hvis du ikke har `sverm` installert globalt, kan du bytte ut `sverm` med
`python cli.py` fra prosjektets rotmappe.

### Tre Flight-Modi

| Mode | Beskrivelse |
|------|-------------|
| **Focus** | Alle instanser jobber med én case. 9+ perspektiver på én problemstilling. |
| **Inbox** | Hver instans velger 1-3 cases selv. Dekker mange cases bredt. |
| **Batch** | Partisjonér alle cases og fordel på instansene. Full dekning. |

---

## Frequency Seeds

Hver instans får en unik kombinasjon av ord, ett fra hver akse.
Ordene farger perspektivet uten å begrense det.

### Dimensjon 1: Perspektiv

| Ord | Vekt | Hva det gjør |
|-----|------|-------------|
| økonom | 0.8 | Cashflow, rentesensitivitet, avkastning, alternativkostnad |
| forelder | 0.7 | Barnas skole, lekemiljø, trygghet, sosial forankring |
| pragmatiker | 0.55 | Hverdagsflyt, logistikk, tidsbruk, stressnivå |
| langtidsplanlegger | 0.45 | 10-15 års horisont, karriereløp, pensjon, arv |
| risikoavers | 0.25 | Worst-case scenarier, buffer, exit-muligheter |
| opportunist | 0.1 | Timing, markedsforhandling, smarte trekk |

### Dimensjon 2: Tidshorisont

| Ord | Vekt | Hva det gjør |
|-----|------|-------------|
| umiddelbart | 0.65 | Neste 3-6 måneder — praktisk gjennomføring |
| mellomlang | 0.7 | 1-5 år — hverdagslivets realitet |
| lang | 0.5 | 5-15 år — når barna blir tenåringer og flytter hjemmefra |
| generasjon | 0.2 | 20+ år — arv, pensjon, eldre dager |

### Dimensjon 3: Risiko

| Ord | Vekt | Hva det gjør |
|-----|------|-------------|
| renterisk | 0.75 | Hva hvis rentene stiger videre? |
| markedsrisk | 0.6 | Hva hvis boligmarkedet faller 20%? |
| jobbrisk | 0.55 | Hva hvis en av de voksne mister jobben? |
| helserisk | 0.3 | Sykdom, ulykke, familiehendelser |
| skilsmisse | 0.2 | Hvordan påvirker et felles huskjøp en skilsmisse? |
| klimarisk | 0.15 | Flom, mold, bygningsskader, endret klima |

### Dimensjon 4: Verdi

| Ord | Vekt | Hva det gjør |
|-----|------|-------------|
| livskvalitet | 0.75 | Hva betyr godt liv for denne familien? |
| fleksibilitet | 0.65 | Kan vi selge lett? Kan vi leie ut? Kan vi endre planer? |
| forankring | 0.5 | Å slå rot, bygge nettverk, kjenne naboer |
| tid | 0.5 | 40 min ekstra reisevei per dag er 10 000 min per år |
| prestasjon | 0.25 | Status, signal til omverdenen, selvbilde |
| enkelhet | 0.15 | Mindre ting å vedlikeholde, mindre stress |

### Dimensjon 5: Beslutningsmodell

| Ord | Vekt | Hva det gjør |
|-----|------|-------------|
| analytisk | 0.7 | Regnearket regjerer — tall, prognoser, scenarier |
| intuitiv | 0.6 | Føles riktig, magefølelse, helhet |
| konsensusbasert | 0.5 | Alle i familien må være enige — også barna |
| ekspertbasert | 0.35 | Lytt til megler, rådgiver, familie, venner |
| eksperimentell | 0.1 | Test hypoteser, juster underveis, ikke bind alt nå |
