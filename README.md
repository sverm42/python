# sverm

> **Multi-perspektiv AI-analyse.** N instanser, samme problem, ulike perspektiver. En metodikk for å se samme spørsmål fra 9 vinkler samtidig — uten at instansene smelter sammen til en gjennomsnittsanalyse.

[![Lisens: PolyForm NC 1.0](https://img.shields.io/badge/lisens-PolyForm_NC_1.0-blue.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-green.svg)](https://www.python.org)
[![sverm.ai](https://img.shields.io/badge/sverm-.ai-purple.svg)](https://sverm.ai)

`sverm` er orkestreringsmotoren bak metodikken fra [sverm.ai](https://sverm.ai). Den lar deg angripe et problem fra mange vinkler samtidig ved å starte N AI-instanser parallelt — hver med sin egen *frequency seed*: et sett vektede ord som farger perspektivet uten å låse det.

Resultatet er ikke varianter av samme svar. Det er genuint forskjellige stemmer som bryter mot hverandre og åpner nye spørsmål du ikke visste du burde stille.

*[English summary below.](#english-summary)*

---

## Hvorfor sverm?

Én AI-instans gir deg ett perspektiv. Samme instans kjørt ti ganger gir deg ti varianter av samme perspektiv — for modellen konvergerer mot sin egen middelverdi. Det du ofte trenger er ikke mer av samme svar, men *andre* svar. Svar fra en ingeniør, en økonom, en bruker, en skeptiker — som alle ser det samme problemet fra hver sin grunnmur.

Sverm-metodikken løser dette ved å gi hver instans et unikt frequency seed: 3-5 vektede ord som differensierer perspektivet aktivt. En instans med seeden `økonom | langsiktig | renterisk` vil se et boligkjøp helt annerledes enn en instans med `forelder | umiddelbart | livskvalitet`. Begge leser samme case. Begge får samme rådata. Men de ender i forskjellige konklusjoner — og i dissensen mellom dem ligger innsikten.

---

## Rask start

### 1. Installasjon

Du trenger Python 3.11 eller nyere og én av:
- **[Claude Code CLI](https://docs.claude.com/en/docs/claude-code)** (`claude`)
- **[OpenAI Codex CLI](https://github.com/openai/codex)** (`codex`)

Begge CLI-ene fungerer på macOS, Windows og Linux. Valget handler om hvilken AI-leverandør du foretrekker — ikke om hvilken plattform du er på. Har du Claude Max eller Pro-abonnement, velg Claude Code. Har du ChatGPT Plus eller Pro, velg Codex. Har du begge, fungerer begge.

**Viktig om kostnad — sverm krever IKKE en API-nøkkel.** Sverm kaller CLI-en din (`claude` eller `codex`) som subprocess og arver autentiseringen den allerede har. Det betyr:

- Har du **Claude Max-abonnement** og er logget inn via `claude login`? Da bruker sverm Max-abonnementet ditt — ingen ekstra kostnad, ingen API-nøkkel.
- Har du **ChatGPT Plus/Pro** og er logget inn via `codex login`? Da bruker sverm det abonnementet — samme prinsipp.
- Har du en **API-nøkkel** hos Anthropic eller OpenAI? Da bruker sverm den hvis CLI-en er konfigurert sånn.

Det eneste sverm gjør er å spawne N parallelle CLI-instanser med forskjellige prompter. Hvordan du betaler for dem, bestemmes av CLI-konfigurasjonen din — ikke av sverm.

Installer sverm via pipx (anbefalt) eller pip:

```bash
# pipx — globalt tilgjengelig kommando
pipx install git+https://github.com/sverm42/python.git

# pip — hvis du foretrekker lokal installasjon
pip install git+https://github.com/sverm42/python.git
```

Etter installasjon har du kommandoen `sverm` i PATH. Verifiser:

```bash
sverm --help
```

### 2. Kjør det innebygde demo-prosjektet

Repoet inkluderer et nøytralt demo — "boligkjøp-analyse" — som du kan kjøre umiddelbart:

```bash
# Klon repoet for å få demoen
git clone https://github.com/sverm42/python.git sverm
cd sverm

# Se casene i demoen
sverm inspect --project 1

# Dry-run (tester setup, starter ikke ekte AI)
sverm launch focus 1 --project 1 --dry-run

# Ekte kjøring: 4 små instanser på case #1 (default)
sverm launch focus 1 --project 1
```

Default er nå `--small -n 4` — fire raske, billige instanser. Det er nok til å se metodikken i praksis uten å brenne mye av abonnementskvoten din. Når du er komfortabel, kan du eskalere til `--medium -n 9` eller `--large -n 9` for dypere analyser.

Etter en vellykket flight finner du:
- **Rå outputs** i `10-projects/1-boligkjop/20-flights/FLT_XXX/VS_XXXX_output.md`
- **Debrief-rapport** i `10-projects/1-boligkjop/30-debrief/FLT_XXX_debrief.md`
- **Oppdatert cases-register** i `10-projects/1-boligkjop/10-cases/CASES.md`

### 3. Lag ditt eget sverm-prosjekt

Kopier en av eksempel-configene, tilpass den til ditt problem, og kjør `sverm setup`:

```bash
cp examples/boligkjop.json min-analyse.json
# rediger min-analyse.json: bytt ut domain, goal, axes og cases

sverm setup min-analyse.json
# → opprettes i ~/sverm-projects/1-min-analyse/
#   (eller cwd/10-projects/ hvis du står i en klonet sverm-repo)

sverm launch focus 1 --project 1
```

Default lagringssted for nye prosjekter er `~/sverm-projects/`. Vil du ha dem et annet sted, sett `SVERM_PROJECTS_DIR` eller bruk `--projects-dir`.

---

## Hvordan sverm fungerer

```
  JSON config  ───►  sverm setup  ───►  prosjektmappe + database
                                         │
                                         ▼
                                    sverm launch focus
                                         │
                          ┌──────────────┼──────────────┐
                          │              │              │
                       VS_001         VS_002         VS_009
                     (seed A)       (seed B)       (seed I)
                          │              │              │
                          └──────────────┼──────────────┘
                                         ▼
                                    sverm debrief
                                         │
                                         ▼
                              rapport + indeks + CASES.md
```

### Steg-for-steg

1. **Du definerer problemet** i en JSON-config: domenet, målet, nøkkelinfo, og 3-5 akser med vektede ord som differensierer perspektivene.
2. **`sverm setup`** oppretter prosjektmappen med database, CLAUDE.md-kontekst og cases-register.
3. **`sverm launch focus N`** starter N AI-instanser parallelt. Hver får samme case, men unik seed.
4. **Instansene jobber** i subprocesser via Claude Code eller Codex som runtime. Hver skriver sin analyse til `20-flights/FLT_XXX/VS_XXXX_output.md`.
5. **`sverm debrief`** (eller automatisk ved slutt-lås) samler outputene, genererer rapport og oppdaterer indeksen.

### Tre flight-modi

| Modus | Beskrivelse |
|-------|-------------|
| **focus** | Alle instanser jobber med én case. 9+ perspektiver på én problemstilling. Best for dybde. |
| **inbox** | Hver instans velger 1-3 cases selv. Bred dekning. *(under utvikling)* |
| **batch** | Alle cases partisjoneres og fordeles. Full dekning. *(under utvikling)* |

I denne første publiserte versjonen er **focus-modus** fullt støttet. Inbox og batch kommer i v1.1.

---

## Frequency seeds — metodikkens kjerne

Et frequency seed er et sett vektede ord som farger en instans sitt perspektiv uten å begrense det. Seedene defineres i JSON-configen din som *akser* (dimensjoner), og hver instans får ett ord trukket vektet fra hver akse.

Eksempel fra boligkjøp-demoet:

```json
{
  "axes": [
    {
      "name": "perspektiv",
      "words": [
        {"word": "økonom",             "weight": 0.80, "description": "Cashflow, rentesensitivitet, avkastning"},
        {"word": "forelder",           "weight": 0.70, "description": "Barnas skole, lekemiljø, trygghet"},
        {"word": "pragmatiker",        "weight": 0.55, "description": "Hverdagsflyt, tid, stressnivå"},
        {"word": "langtidsplanlegger", "weight": 0.45, "description": "10-15 års horisont, karriereløp, pensjon, arv"},
        {"word": "risikoavers",        "weight": 0.25, "description": "Worst-case scenarier, buffer, exit-muligheter"},
        {"word": "opportunist",        "weight": 0.10, "description": "Timing, markedsforhandling, smarte trekk"}
      ]
    }
  ]
}
```

En instans trekker én seed fra hver akse (vektet random), så en instans kan få `økonom | langsiktig | renterisk | livskvalitet | analytisk`. En annen kan få `forelder | umiddelbart | jobbrisk | forankring | intuitiv`. Begge leser samme case, men de ender opp med distinktivt forskjellige analyser.

### Regler for gode seeds

- **5 akser, 5-10 ord per akse** gir 3000+ mulige kombinasjoner — nok for 20+ instanser uten duplikater.
- **Høye vekter (0.6-0.85)** = kjerneord som definerer domenet, dukker opp ofte.
- **Lave vekter (0.03-0.15)** = sjeldne reframers som forhindrer konvergens. Disse er de viktige.
- **Test**: Ville to tilfeldige seed-kombinasjoner gi merkbart forskjellige perspektiver? Hvis nei, er aksene for like.

---

## Prosjektstruktur

Etter `sverm setup min-config.json`:

```
10-projects/1-min-prosjekt/
├── sverm.db                    # SQLite: seeds, cases, flights, instanser, outputs
├── CLAUDE.md                   # Kontekst for AI-instansene
├── CONTEXT.md                  # Kort prosjektbeskrivelse
├── 10-cases/
│   └── CASES.md                # Oversikt med launch-kommandoer
├── 20-flights/
│   └── FLT_001/
│       ├── MANIFEST.json       # Hvem deltok, med hvilke seeds
│       ├── VS_001_prompt.md    # Prompten instansen fikk
│       ├── VS_001_output.md    # Hva instansen skrev
│       ├── VS_001.done         # Landingssignal
│       └── ...
└── 30-debrief/
    └── FLT_001_debrief.md      # Oppsummering, alle outputs samlet
```

---

## Kommandoer

| Kommando | Hva den gjør |
|----------|--------------|
| `sverm setup config.json` | Opprett nytt prosjekt fra JSON |
| `sverm inspect --project P` | Vis prosjektstatus og cases |
| `sverm launch focus N --project P` | Kjør N instanser på case #N (focus mode) |
| `sverm debrief FLT_XXX --project P` | Generer debrief manuelt |
| `sverm mirror --project P` | Synk DB → CASES.md |

**Modellvalg** (runtime-agnostisk):

| Flagg | Claude Code | Codex | Bruk |
|-------|-------------|-------|------|
| `--small` *(default)* | haiku | gpt-5.4-mini | Raskt og billig — bra for testing, workshops og bredde |
| `--medium` | sonnet | gpt-5.4 | Balansert — anbefalt når du har validert seeds og cases |
| `--large` | opus | gpt-5.4 *(samme)* | Dyp og dyr. Codex har per april 2026 ingen høyere reasoning-tier enn gpt-5.4. |

Default er `--small -n 4` slik at workshopdeltakere og nye brukere ikke brenner abonnementskvoten på første flight. Eskalér når du har sett metodikken fungere på små instanser.

`--timeout SECONDS` setter maks ventetid på en hel flight (default: 900s). 0 = uendelig. Hvis timeout overskrides, dreper sverm hengende prosesser og lager debrief med det som har landet.

---

## Runtime-valg

`sverm` abstraherer over AI-runtimen via en enkel auto-detect. Både [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) og [OpenAI Codex CLI](https://github.com/openai/codex) fungerer på macOS, Windows og Linux — du velger basert på hvilken AI-leverandør du foretrekker og hvilket abonnement/API-nøkkel du har.

- **Claude Code** er mest modent per v1.0 og prioriteres automatisk hvis begge er installert
- **OpenAI Codex** fungerer som fullverdig alternativ. Sett `CODEX_BIN` hvis binæren ikke er i PATH
- **Override**: Sett miljøvariabelen `SVERM_RUNTIME=claude`, `SVERM_RUNTIME=codex` eller `SVERM_RUNTIME=dry-run` for å tvinge valget
- **Dry-run**: `--dry-run`-flagget lar deg teste setup og seed-allokering uten å starte ekte AI-prosesser. Nyttig for å verifisere at configen din er riktig.

### Autentisering — abonnement eller API-nøkkel?

Sverm gjør ingenting selv med auth. Den kaller `claude` eller `codex` som subprocess og arver den auth-tilstanden CLI-en allerede har. Dette betyr at du kan kjøre sverm med:

1. **Claude Max / Pro-abonnement** — Etter `claude login` og OAuth-flyt, bruker sverm samme auth. Kall-ene teller mot abonnementsgrensen, ikke mot en API-konto.
2. **ChatGPT Plus / Pro-abonnement** — Etter `codex login` fungerer det samme for Codex-runtimen.
3. **Anthropic API-nøkkel** — Hvis `ANTHROPIC_API_KEY` er satt og `claude` er konfigurert sånn, brukes API-en. Du betaler per token.
4. **OpenAI API-nøkkel** — Samme prinsipp for Codex.

**For workshop-deltakere:** Har du allerede et Claude Max eller ChatGPT Plus-abonnement, trenger du INGEN API-nøkkel for å kjøre sverm. Logg inn i CLI-en på vanlig måte, og sverm bruker det du allerede betaler for.

---

## Eksempler

Se `examples/` for ferdige JSON-configs du kan bruke som utgangspunkt:

- **[`boligkjop.json`](./examples/boligkjop.json)** — En norsk småbarnsfamilie vurderer å kjøpe rekkehus. Universelt relaterbar, 5 akser, 5 cases. *(Kjøres som innebygd demo.)*
- **[`restaurant.json`](./examples/restaurant.json)** — Maria (kokk) vurderer å åpne bistro i Bjerke. Forretningsperspektiv, finansiering, lansering, konsept.
- **[`karriere.json`](./examples/karriere.json)** — Anders (42) har fått startup-tilbud. Personlig beslutning med familie, økonomi og psykologi.
- **[`produktlansering.json`](./examples/produktlansering.json)** — Norsk AI-bokføring-SaaS klar for offentlig lansering. Go-to-market, pris, segment, konkurranse.
- **[`kommune-beslutning.json`](./examples/kommune-beslutning.json)** — Mo kommune vurderer 120 MNOK flerbrukshall mot opposisjonens renoverings-alternativ. Offentlig sektor, politikk, verdiprioritering.

Alle fem er designet med 5 akser × 5-10 vektede ord per akse, med beskrivelser på ordene. Kopier en av dem som utgangspunkt, tilpass til ditt eget domene.

## Dokumentasjon

Utover denne README finnes det to dype tekniske dokumenter:

- **[docs/SEED-DESIGN.md](./docs/SEED-DESIGN.md)** — Hvordan skrive frequency seeds som faktisk produserer forskjellige perspektiver. Regler for vekting, vanlige feil, kvalitetssjekkliste, workflow fra tom fil til første flight.
- **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)** — Teknisk oversikt: moduler, datamodell, prosess-livssyklus, fil-kontrakter, ekstensjonspunkter. For deg som vil forstå koden under panseret eller utvide sverm.

---

## Lisens

`sverm` er lisensiert under **[PolyForm Noncommercial License 1.0.0](./LICENSE)**.

Du kan fritt bruke, modifisere og redistribuere programvaren for *ethvert ikke-kommersielt formål* — inkludert:

- ✓ Forskning, undervisning, hjemmelekser
- ✓ Personlige prosjekter og eksperimenter
- ✓ Intern evaluering i bedriften din (før eventuell kjøpsbeslutning)
- ✓ Ideelle organisasjoner, utdanningsinstitusjoner, offentlige etater
- ✓ Workshop-deltakere på sverm.ai sine kurs
- ✓ AI-assistenter som leser, vurderer eller diskuterer koden

Kommersiell bruk krever en separat avtale med rettighetshaver. Kontakt raymond@sverm.ai for dialog.

### Hvorfor ikke en klassisk open-source-lisens?

Vi valgte PolyForm NC (i stedet for MIT, Apache eller Creative Commons) av tre grunner:

1. **PolyForm er designet for programvare.** Creative Commons fraråder eksplisitt CC-lisenser for kildekode. MIT og Apache tillater kommersielt re-salg vi ønsker å unngå.
2. **Klar non-commercial-definisjon.** PolyForm definerer tydelig hva "ikke-kommersielt" betyr — i motsetning til CC, der grensen er uklar.
3. **Bærekraft for prosjektet.** `sverm` finansieres gjennom workshoptjenester og konsulentoppdrag. En lisens som hindrer kommersiell re-pakking beskytter både prosjektet og brukerne.

Hvis du vil bidra: se [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## Workshop 15. april 2026

Denne versjonen er spesielt klargjort for workshopen **"KI-sverm i praksis"** på Quben, Kongsberg, 15. april 2026. Deltakerne får tilgang til `github.com/sverm42/python` for å prøve ut metodikken på sine egne problemstillinger.

Mer info: [sverm.tech](https://sverm.tech).

### Før workshopen: Installeringssjekkliste

Gjør disse stegene hjemme før du kommer. Hele sjekklisten tar omtrent 20-30 minutter hvis du ikke har noe installert fra før, og 5 minutter hvis du allerede har Python og en AI-CLI. Har du problemer, ta kontakt på [sverm.tech](https://sverm.tech) eller skriv til raymond@sverm.ai.

#### Steg 1 — Python 3.11 eller nyere

Sjekk hva du har:
```bash
python3 --version
```

Hvis du ser `Python 3.11.x` eller høyere, gå videre. Ellers:

- **macOS:** `brew install python@3.12` (krever [Homebrew](https://brew.sh))
- **Windows:** Last ned fra [python.org/downloads](https://www.python.org/downloads/) — viktig: huk av "Add Python to PATH" under installasjonen
- **Linux:** `sudo apt install python3.12` (Debian/Ubuntu) eller bruk pakkehåndtereren din

#### Steg 2 — pipx (for global installasjon)

```bash
# macOS
brew install pipx
pipx ensurepath

# Windows (i PowerShell)
python -m pip install --user pipx
python -m pipx ensurepath

# Linux
sudo apt install pipx
pipx ensurepath
```

Lukk og åpne terminalen på nytt etter `pipx ensurepath` så den oppdaterte PATH-en blir aktiv.

Verifiser: `pipx --version`

#### Steg 3 — AI-CLI (Claude Code eller Codex)

Du må ha *minst én* av disse installert og logget inn. Begge fungerer på macOS, Windows og Linux. Valget avhenger av hvilken AI-leverandør du foretrekker.

**Alternativ A: Claude Code CLI**

```bash
# macOS / Linux
curl -fsSL https://claude.ai/install.sh | sh

# Windows (PowerShell)
irm https://claude.ai/install.ps1 | iex

# Logg inn (åpner nettleser)
claude login

# Verifiser
claude -p "Si 'hei' og ingenting annet"
```

Offisiell installasjonsdokumentasjon: [docs.claude.com/en/docs/claude-code](https://docs.claude.com/en/docs/claude-code)

**Alternativ B: OpenAI Codex CLI**

```bash
# Krever Node.js 18+ på alle plattformer
npm install -g @openai/codex

# Logg inn
codex login

# Verifiser
codex exec "Si 'hei' og ingenting annet"
```

Offisiell dokumentasjon: [github.com/openai/codex](https://github.com/openai/codex)

> **Om kostnad:** Har du **Claude Max/Pro** eller **ChatGPT Plus/Pro**, bruker CLI-en abonnementet ditt etter innlogging — ingen API-nøkkel nødvendig. Har du ingen av delene, må du ha en API-nøkkel fra [console.anthropic.com](https://console.anthropic.com) eller [platform.openai.com](https://platform.openai.com).

#### Steg 4 — Installer sverm

```bash
pipx install git+https://github.com/sverm42/python.git
```

Verifiser:
```bash
sverm --help
```

Du burde se kommandoene `setup`, `launch`, `inspect`, `mirror`, `debrief`.

#### Steg 5 — Last ned demo-prosjektet

```bash
git clone https://github.com/sverm42/python.git sverm
cd sverm
```

#### Steg 6 — Dry-run (test uten å bruke tokens)

```bash
sverm launch focus 1 --project 1 --small -n 4 --dry-run
```

Hvis du ser linjer som begynner med `FOCUS MODE: Case #1`, `Flight: FLT_001 (4 instances)`, og til slutt `FLIGHT FLT_001 LAUNCHED` — da fungerer installasjonen. Du er klar for workshopen.

#### Steg 7 — Ekte mini-flight (valgfritt, anbefalt)

For å verifisere at AI-CLI-en din faktisk svarer:

```bash
sverm launch focus 1 --project 1 --small -n 2
```

Dette starter 2 haiku/gpt-5.4-mini-instanser på boligkjop-casen. Tar omtrent 1-2 minutter. Ser du `FLIGHT FLT_002 LAUNCHED` og deretter `Debrief: .../FLT_002_debrief.md`, er alt klart.

Sjekk at debrief-filen har ekte AI-output:
```bash
cat 10-projects/1-boligkjop/30-debrief/FLT_002_debrief.md
```

#### Feilsøking

| Symptom | Sannsynlig årsak | Løsning |
|---------|------------------|---------|
| `command not found: sverm` | pipx PATH ikke aktiv | Kjør `pipx ensurepath`, åpne ny terminal |
| `command not found: claude` eller `codex` | CLI ikke installert | Gå tilbake til Steg 3 |
| Flight starter men ingen outputs | CLI ikke logget inn | Kjør `claude login` / `codex login` |
| Python-feil om versjon | Python < 3.11 | Oppgrader Python |
| "No runtime found" | Ingen CLI i PATH | Sjekk `which claude` eller `which codex` |

Fortsatt problemer? Lag en issue på [github.com/sverm42/python/issues](https://github.com/sverm42/python/issues) eller skriv til raymond@sverm.ai.

---

## English Summary

`sverm` is the orchestration engine behind [sverm.ai](https://sverm.ai). It lets you attack a problem from many angles simultaneously by launching N parallel AI instances, each with a unique *frequency seed* — a set of weighted words that color the perspective without constraining it.

The result is not variations of the same answer. It's genuinely different voices that push against each other and open new questions.

**Quick start:**
```bash
pipx install git+https://github.com/sverm42/python.git
git clone https://github.com/sverm42/python.git sverm && cd sverm
sverm launch focus 1 --project 1 --small -n 4 --dry-run
```

**Requirements:**
- Python 3.11+
- Either [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) or [OpenAI Codex CLI](https://github.com/openai/codex) — both work on macOS, Windows and Linux. Pick whichever AI provider you already have a subscription or API key for.

**License:** PolyForm Noncommercial 1.0.0 — free for research, teaching, personal projects, and evaluation. Commercial use requires a separate agreement. Contact raymond@sverm.ai.

---

*sverm.ai — Kristiansen Sverm ENK, Norge.*
