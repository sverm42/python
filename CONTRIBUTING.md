# Contributing to sverm

Takk for interessen! `sverm` er et non-commercial open-source-prosjekt lisensiert under PolyForm Noncommercial 1.0.0. Bidrag er velkomne, men husk at lisensen betyr at all kode — inkludert din — forblir non-commercial.

## Hvordan bidra

### Rapportere bugs
Åpne en issue på [github.com/sverm42/python/issues](https://github.com/sverm42/python/issues) med:
- Operativsystem og Python-versjon
- Runtime i bruk (Claude Code eller Codex)
- Eksakt kommando som feilet
- Feilmelding (gjerne med `--dry-run` for å isolere)

### Foreslå forbedringer
Åpne en issue først for diskusjon før du sender en pull request. Større endringer bør få grønt lys før arbeidet begynner — det er trist for alle hvis en flott PR blir avvist fordi vi har en annen retning planlagt.

### Pull requests
1. Fork repoet
2. Lag en feature branch (`git checkout -b feature/navn-på-endring`)
3. Gjør endringen med passende testing
4. Commit med en tydelig melding
5. Push til din fork
6. Åpne en pull request mot `main`

### Kode-stil
- Python 3.10+ (bruker `from __future__ import annotations` for å støtte nyere type-hint-syntax)
- Type hints der det gir mening
- Docstrings på norsk (matcher resten av kodebasen)
- UTF-8 overalt — bruk ekte æ, ø, å, ingen ASCII-erstatninger
- Hold endringer fokuserte — én PR = ett konsept

## Utvikling lokalt

```bash
git clone https://github.com/sverm42/python.git sverm
cd sverm
pip install -e .
sverm --help
```

## Lisensiering av bidrag

Ved å sende en pull request bekrefter du at:
1. Bidraget er ditt eget arbeid (eller at du har tillatelse)
2. Du godtar at bidraget lisensieres under PolyForm Noncommercial 1.0.0 sammen med resten av prosjektet
3. Du gir rettighetshaver (Kristiansen Sverm ENK) rett til å gjenlisensiere bidraget om prosjektet senere skifter lisens

## Kontakt

For spørsmål utenom issues: raymond@sverm.ai
