"""
Scheidsrechter Planning App
BV Waterdragers

Twee views:
1. Spelers: inschrijven via unieke link met NBB-nummer
2. Beheerder: overzicht en toewijzen
"""

import streamlit as st
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
from io import BytesIO

# Database module voor Supabase
import database as db

# Geofiltering - alleen toegang vanuit Nederland
# Let op: Werkt momenteel NIET op Streamlit Cloud (geen publiek IP beschikbaar)
# Zie database.py voor details. Code is voorbereid voor toekomstig gebruik.
db.check_geo_access()

# Versie informatie
APP_VERSIE = "1.30.0"
APP_VERSIE_DATUM = "2026-01-25"
APP_CHANGELOG = """
### v1.30.0 (2026-01-25)
**Koppeling met Competitie Planner:**
- 🔗 Nieuwe synchronisatie met Competitie Planner database
- 📥 Import wedstrijden direct uit CP (zonder Excel export)
- 🔄 Detecteert nieuwe, gewijzigde en verwijderde wedstrijden
- 👥 Behoudt scheidsrechters bij het bijwerken van wedstrijden
- 🔑 Match op NBB wedstrijdnummer voor robuuste koppeling

### v1.29.0 (2026-01-20)
**Scheidsrechter status & Team overzicht:**
- 🎯 Nieuwe status optie: "Op te leiden" (voor spelers die nog getraind moeten worden)
- ⏸️ Nieuwe status optie: "Inactief" (voor spelers die gestopt/pauze hebben)
- 👥 Nieuw: "Scheidsrechters per team" overzicht in beheer
- 📋 Kopieerbare tekst per team voor WhatsApp (om te delen met coaches)
- 🔍 Extra filter op scheidsrechter status

### v1.28.5 (2026-01-19)
**Bugfix - Blokkade conflicten:**
- 🔒 Bij blokkeren van een dag wordt nu gecheckt of je al bent ingedeeld
- ✅ Automatisch uitschrijven bij conflicterende toewijzingen
- ⚠️ Duidelijke melding welke wedstrijden zijn verwijderd

### v1.28.4 (2026-01-10)
**Synchronisatie verbeteringen:**
- 📅 Alleen toekomstige wedstrijden worden gesynchroniseerd (niet meer verleden)
- ✅ Geannuleerde wedstrijden worden automatisch heractiveerd bij verplaatsing
- 🔔 Duidelijke indicatie wanneer annulering wordt opgeheven
- 📊 Success melding toont aantal heractiveerde wedstrijden

### v1.28.3 (2026-01-10)
**UX verbetering - Auto-scroll naar meldingen:**
- 🔄 Scherm scrollt automatisch naar "Positie al bezet" error melding
- 🔄 Scherm scrollt automatisch naar waarschuwing bij lager niveau inschrijving
- 📜 Nieuwe helper functies `toon_error_met_scroll()` en `scroll_naar_warning()`

### v1.28.2 (2026-01-10)
**Bugfix - Race condition melding en None handling:**
- 🐛 Fix: Foutmelding "Positie al bezet" werd niet getoond door sessie-cache
- 🔄 Nieuwe functie `laad_wedstrijd_vers()` haalt data direct uit database zonder cache
- ✅ Bij gelijktijdige inschrijving krijgt de tweede speler nu correct een melding
- 🐛 Fix: TypeError bij afmelden wanneer afgemeld_door/heraanmeldingen None is

### v1.28.1 (2026-01-10)
**Bugfix - TypeError bij nieuwe wedstrijden:**
- 🐛 Fix: TypeError wanneer afgemeld_door kolom None is (bij nieuwe/oude wedstrijden)

### v1.28.0 (2026-01-10)
**Pool blijft stabiel na afmelding:**
- 🎯 Pool stijgt niet meer onterecht wanneer een scheidsrechter zich afmeldt
- 📝 Afmeldingen worden nu geregistreerd per wedstrijd
- 🔙 Scheidsrechters die zich hebben afgemeld kunnen zich alsnog heraanmelden
- ⚠️ Bij heraanmelding geen bonus (voorkomt gaming)
- 👀 TC ziet in beheer wie zich eerder had afgemeld (⚠️ indicator)
- 🔙 In kandidatenlijst toont 🔙 icoon bij eerder afgemelde scheidsrechters

### v1.27.1 (2026-01-09)
**KRITIEKE BUGFIX - Ingeschreven wedstrijden niet zichtbaar:**
- 🐛 Fix: indentatiefout waardoor alleen de laatste ingeschreven wedstrijd werd getoond
- 🐛 Fix: buggy `kan_inschrijven` check verwijderd die UI blokkeerde
- ✅ Alle ingeschreven wedstrijden worden nu correct getoond

### v1.27.0 (2026-01-09)
**Pool Bonus uitleg & opschoning:**
- 📋 Pool bonus uitleg toegevoegd aan "Punten & Strikes" expander
- 🧹 Bonuspunten verwijderd uit pool badge (te druk) - bonus staat nu in uitleg
- 🎯 Pool badge toont alleen nog het pool getal

### v1.26.0 (2026-01-09)
**Pool Bonus - Beloning voor kritieke wedstrijden:**
- 🏆 Nieuwe bonus: extra punten voor inschrijven op wedstrijden met kleine pool
- 🔴 Pool ≤3 (kritiek): +3 punten
- 🟠 Pool 4-5 (zeer krap): +2 punten  
- 🟡 Pool 6-8 (krap): +1 punt
- 👁️ Bonus zichtbaar in pool badge (+X🏆)
- ⚙️ Grenzen configureerbaar in beloningsinstellingen

### v1.25.11 (2026-01-09)
**Verwijder "Open posities" hints:**
- 🧹 "Open posities" hints verwijderd - pool-indicator is nu de primaire indicator
- ✅ Bevestigingsdialoog bij lager niveau blijft behouden

### v1.25.10 (2026-01-09)
**Dag-indicator negeert volledig bezette wedstrijden:**
- 🎯 Wedstrijden met beide scheidsrechters ingevuld tellen niet mee voor dag-indicator
- ✅ Als alle wedstrijden op een dag bezet zijn, wordt de dag groen

### v1.25.9 (2026-01-09)
**Pool telt toegewezen scheidsrechters niet mee:**
- 🐛 Fix: scheidsrechters die al aan deze wedstrijd zijn toegewezen tellen niet meer mee in pool
- 🎯 Pool toont nu correct het aantal nog beschikbare scheidsrechters

### v1.25.8 (2026-01-09)
**Fix dag-indicator v2:**
- 🐛 Fix: "type" veld werd overschreven door wedstrijd data
- 🎯 Dag-indicator toont nu correct de laagste pool kleur

### v1.25.7 (2026-01-09)
**Fix dag-indicator:**
- 🐛 Dag-indicator toont nu laagste pool van alle getoonde wedstrijden
- 🎯 Consistentie: dag-kleur komt nu overeen met wedstrijd-kleuren

### v1.25.6 (2026-01-09)
**Uitsluiten van pool optie:**
- 🧪 Nieuwe optie: "Uitsluiten van pool" voor test/reserve spelers
- 📊 Uitgesloten spelers tellen niet mee in pool-berekening
- 👁️ Zichtbaar in overzichtstabel en scheidsrechter details

### v1.25.2 (2026-01-09)
**Bugfix beschikbare teams v2:**
- 🐛 Fix: teams worden nu getoond (keek naar gefilterde items i.p.v. alle wedstrijden)
- 🎯 Kijkt nu naar alle wedstrijden van die dag, onafhankelijk van ingelogde speler

### v1.25.1 (2026-01-09)
**Bugfix beschikbare teams:**
- 🐛 Fix: beschikbare teams nu dynamisch per dag (was statisch)
- 🎯 Kijkt nu naar wedstrijdniveaus, eigen team, en tijdsoverlap

### v1.25.0 (2026-01-09)
**Pool-indicator & Inschrijfadvies:**
- 🎯 Pool-indicator per wedstrijd toont aantal beschikbare scheidsrechters
- 🔴🟠🟢 Kleurcodering: Kritiek (<5), Krap (5-8), Ruim (>8)
- 📋 Dag-header toont welke teams die dag kunnen fluiten
- 💡 Spelers zien direct waar hun inschrijving het meest nodig is

### v1.24.2 (2026-01-09)
**Bugfix weekend overzicht:**
- 🔄 Overzicht update nu correct bij wisselen van weekend
- 🗑️ Oude gegenereerde afbeeldingen worden gewist bij selectie wijziging

### v1.24.1 (2026-01-09)
**Niveau in alert afbeelding:**
- 📊 Wedstrijdniveau getoond in alert header
- 🎯 Benodigd niveau per positie (1e/2e scheids)

### v1.24.0 (2026-01-09)
**Verbeterde wedstrijd filtering:**
- 🚫 Wedstrijden waar je niet op kunt inschrijven worden verborgen
- 🔒 BS2-vereiste wedstrijden niet meer zichtbaar zonder BS2 diploma
- 👁️ Alleen zichtbaar via "Hele overzicht" filter

### v1.23.9 (2026-01-08)
**Wedstrijden verplaatsen bij NBB sync:**
- 🔄 Detecteert wedstrijden die verplaatst zijn naar nieuwe datum
- 📅 Keuze: verplaatsen (scheidsrechters behouden) of nieuwe wedstrijd
- ❌ Werkt ook voor geannuleerde wedstrijden (heractiveren)

### v1.23.8 (2026-01-08)
**Bugfix duplicate form keys:**
- 🐛 Fix voor form key conflict na bulk annulering

### v1.23.7 (2026-01-08)
**Bulk annulering wedstrijden:**
- 🚫 Nieuwe functie: annuleer alle wedstrijden per dag
- 📝 Scheidsrechters worden afgemeld met reden "annulering_wedstrijd"
- 🗓️ Wedstrijden worden gemarkeerd als geannuleerd

### v1.23.6 (2026-01-08)
**Verbeterde race condition fix:**
- 🔒 Niemand kan overschrijven (ook TC niet)
- 📢 Duidelijke foutmelding met naam van wie er al staat
- 🔄 TC moet pagina verversen om actuele data te zien

### v1.23.5 (2026-01-08)
**KRITIEKE FIX - Race condition bij inschrijving:**
- 🔒 Verse database check voordat inschrijving wordt opgeslagen
- ⚠️ Foutmelding als positie al door iemand anders is ingenomen
- 🛡️ Voorkomt overschrijven van bestaande inschrijvingen

### v1.23.4 (2026-01-08)
**Aankomend weekend openstellen:**
- 🗓️ Wedstrijden in aankomend weekend met open posities zijn nu zichtbaar
- 🚫 Zelf inschrijven voor deze wedstrijden geeft nog steeds geen bonus

### v1.23.3 (2026-01-08)
**Tekst aanpassing alert:**
- 📝 "1e/2e zoekt vervanger" → "1e/2e scheids zoekt vervanger"

### v1.23.2 (2026-01-08)
**Bugfix zoekt vervanging:**
- 🐛 Fix: checkbox veroorzaakte geen infinite loop meer

### v1.23.1 (2026-01-08)
**Zoekt vervanging status:**
- 🔄 Nieuw: markeer scheidsrechter als "zoekt vervanging" in admin
- 🚨 Alert toont "zoekt vervanging" status naast open posities
- 🐛 Fix: io import voor alert PNG generatie

### v1.23.0 (2026-01-08)
**Bonus systeem herziening & Open Posities Alert:**
- 🎯 Last-minute bonus alleen bij vervanging of TC-toewijzing
- 🚫 Zelf inschrijven na deadline geeft geen bonus meer
- 📊 Bonus gebaseerd op moment van uitnodiging, niet acceptatie
- 🚨 Nieuw: Open Posities Alert overzicht voor WhatsApp
- ⚠️ Teams met ** (no-show risico) worden extra benadrukt
- ➕ V12-2 toegevoegd aan selecteerbare teams voor coaches

### v1.22.8 (2026-01-07)
**Begeleiders ranking fix:**
- 🐛 Fix: alleen echte MSE spelers (MSE in eigen_teams) tellen als begeleider
- 🐛 Fix: BS2 spelers zonder MSE team worden niet meer meegeteld
- 🐛 Fix: begeleiding telt alleen bij echte interactie:
  - Niet-fluitende begeleider: alleen met positieve feedback
  - Fluitende MSE: alleen als 2e scheids open_voor_begeleiding had + positieve feedback
- 📊 Handmatig gekoppelde MSE + onervaren speler telt NIET meer automatisch

### v1.22.7 (2026-01-07)
**Bugfix begeleiders klassement:**
- 🐛 Fix: begeleiders ranking telde ook toekomstige wedstrijden mee
- 📊 Nu worden alleen gespeelde wedstrijden geteld

### v1.22.2 (2026-01-07)
**Layout fixes:**
- 🐛 Fix: sidebar toggle CSS vereenvoudigd
- 📱 Mobiel: gebruik "Begeleiders & Info" voor dagen blokkeren
- 🖥️ Desktop: sidebar 320px breed

### v1.22.1 (2026-01-07)
**Mobiele sidebar verbeteringen:**
- 📱 Pogingen om sidebar toggle te verbeteren (teruggedraaid in v1.22.2)

### v1.22.0 (2026-01-07)
**Dagen blokkeren:**
- 🚫 Spelers kunnen nu wedstrijddagen blokkeren
- 🚫 Geblokkeerde dagen worden uitgefilterd bij handmatige toewijzing
- 🚫 Geblokkeerde dagen worden uitgefilterd bij vervangingsverzoeken
- 🔒 Blokkades voor verleden dagen kunnen niet worden verwijderd

### v1.21.1 (2026-01-07)
**Kritieke bugfix inschrijvingen:**
- 🐛 Fix: Inschrijvingen verdwenen na herladen (race condition opgelost)
- 🐛 Fix: "Toch inschrijven" op mobiel werkt nu correct
- ⚡ Inschrijven/afmelden slaat nu alleen de betreffende wedstrijd op (niet alle wedstrijden)
- 🔄 Bulk save functie uitgebreid met alle velden (punten, status, begeleider)

### v1.21.0 (2026-01-07)
**Blessure status & Wedstrijd synchronisatie:**
- 🤕 Nieuwe blessure status per scheidsrechter (geblesseerd t/m maand)
- 🤕 Geblesseerde spelers worden uitgefilterd bij handmatige toewijzing
- 🐛 Fix: Veld wordt nu correct opgeslagen in database
- 🔄 Nieuwe tab "Synchronisatie" in Import/Export
- 📥 Completeren: vul ontbrekende velden aan vanuit NBB import
- ⚖️ Vergelijken: detecteer en los mismatches op tussen BOB en NBB

### v1.20.0 (2026-01-04)
**Inschrijfgedrag monitoring & verbeterde statistieken:**
- 📈 Nieuwe tab "Inschrijfgedrag" in Analyse dashboard
- 📊 Vergelijking top 3 punten vs. probleemgevallen (3+ strikes)
- 🐦 Early bird indicator (>7 dagen vooruit)
- ⚠️ Last-minute indicator (<3 dagen vooruit)
- 🗓️ Verbeterde metrics: Weekend, Rest maand, Hele seizoen
- 📝 Logging van inschrijf/uitschrijf momenten

### v1.19.3 (2026-01-03)
**Prioriteit passieve spelers bij handmatig toewijzen:**
- 😴 Spelers zonder inschrijvingen staan nu bovenaan kandidatenlijst
- 🔢 Sortering: passief → tekort op niveau → minste wedstrijden
- 👀 Passieve spelers gemarkeerd met 😴 icoon in dropdown

### v1.19.2 (2026-01-03)
**Bugfix eigen wedstrijd detectie:**
- 🐛 Fix: Tegenstanders met zelfde teamcode (bijv. M18-1) worden niet meer als eigen wedstrijd gezien
- ✅ Check nu ook op "Waterdragers" in teamnaam

### v1.19.1 (2026-01-03)
**Bugfix wedstrijd verwijderen:**
- 🐛 Fix: Wedstrijden worden nu correct uit database verwijderd
- ⚠️ Bevestigingsdialoog toegevoegd bij verwijderen wedstrijd

### v1.19.0 (2025-12-31)
**Help-functie:**
- ❓ Nieuwe Help-sectie in Begeleiders & Info expander
- 📚 Uitleg over: Aan de slag, Beschikbaarheid, Ontwikkelen, Belonen
- 🎓 MSE-sectie alleen zichtbaar voor MSE-scheidsrechters
- 📱 Korte, bondige teksten voor jeugdspelers

### v1.18.1 (2025-12-31)
**No-show met invaller:**
- 🔄 Nieuwe optie: No-show met invaller (strikes + punten in één actie)
- 📝 Verbeterde uitleg in bevestigingsscherm

### v1.18.0 (2025-12-31)
**Deadline per maand & Punten na bevestiging:**
- 📅 Deadline sluit nu alleen de betreffende maand, latere maanden blijven open
- ✅ Nieuwe tab "Bevestigen" in beheerder view
- 🏆 Punten worden pas toegekend na bevestiging door TC
- ❌ No-show optie met automatische strike toekenning
- 📊 Bulk actie om alle wedstrijden als gefloten te markeren
- 🔄 Sessie-cache verwijderd voor beloningsinstellingen (direct doorvoeren)

### v1.17.0 (2025-12-30)
**Mobiele UX verbeteringen:**
- 📱 Blauwe lijn boven wedstrijden container
- 📱 Container met rand voor visuele afbakening
- 📱 Versienummer in Begeleiders & Info expander
- 🏆 Punten klassement permanent zichtbaar
- 🎓 Begeleiders & Info in opvouwbare expander

### v1.16.4 (2025-12-30)
**Klassement & Feedback:**
- 🏆 Punten klassement nu permanent zichtbaar (ook op mobiel)
- 🎓 Begeleiders & Info in opvouwbare expander
- 🎓 Begeleider ziet feedback melding in hoofdscherm

### v1.16.3 (2025-12-29)
**Fix:**
- 🐛 Fix: Ingeschreven telling toont nu alle wedstrijden (inclusief verleden)

### v1.16.2 (2025-12-29)
**Layout fixes:**
- 🖥️ Desktop: Header weer logo - titel - logo
- 📱 Mobiel: Logo's naast elkaar, welkom eronder
- 📱 Mobiel: Filters nu onder elkaar
- 📱 Mobiel: Metrics blijven naast elkaar

### v1.15.0 (2025-12-29)
**Seizoen beheer:**
- 📅 Nieuwe tab: Seizoen in Instellingen
- 🔒 Seizoen afsluiten met archivering
- 📚 Bekijk gearchiveerde seizoenen
- 📊 Statistieken per speler per seizoen (incl. minimums)
- 📥 Export archief naar CSV

### v1.14.0 (2025-12-29)
**Analyse Dashboard & Export uitbreiding:**
- 📊 Nieuw: Analyse tab voor fluitgedrag analyse
- 🌟 Overzicht: Wie fluit veel (+3 boven minimum)
- ⚠️ Overzicht: Wie fluit weinig (onder minimum)
- 💡 Suggesties voor minimum aanpassingen
- 🔧 Bulk minimum aanpassen (verhogen/verlagen)
- 📤 Export: Scheidsrechters + statistieken
- ... scheiding als je niet in top 3 staat

### v1.12.3 (2025-12-29)
**Verbeterde Data Reset tab:**
- 📊 Overzicht met metrics bovenaan
- 🔢 Toont aantal items per categorie
- ✅ Groen vinkje als er niets te resetten valt
- 🗑️ Nieuwe optie: begeleiders uit wedstrijden resetten

### v1.12.2 (2025-12-29)
**Bugfix:**
- 🐛 Reset functies gebruiken nu correcte kolom namen per tabel

### v1.12.1 (2025-12-29)
**Bugfix:**
- 🐛 Reset beloningen gebruikt nu correcte beloningen tabel

### v1.12.0 (2025-12-29)
**Data Reset functionaliteit:**
- 🗑️ Nieuwe "Data Reset" tab in beheerder instellingen
- 💰 Reset punten/strikes per speler of voor alle spelers
- 👥 Reset MSE begeleidingsuitnodigingen en feedback
- 📱 Reset apparaten en apparaat instellingen

### v1.11.5 (2025-12-29)
**Device verificatie & beheer - Definitieve versie:**
- 🔐 Apparaat verificatie via geboortedatum
- 🔍 Apparaten worden herkend op basis van browser fingerprint
- 📱 Browser type wordt getoond (Chrome, Firefox, Safari, etc.)
- 📱 Spelers kunnen gekoppelde apparaten zien en verwijderen
- ⚙️ Spelers kunnen max aantal apparaten instellen
- ✅ Optionele goedkeuring voor nieuwe apparaten
- 🔐 Beheerder tab voor apparaatoverzicht
- 🌍 Netwerk info in sidebar (IP/land detectie voorbereid)

### v1.9.35 (2025-12-28)
**Beveiliging update:**
- 🔐 Device verificatie met cookies (90 dagen)
- 🌍 Geofiltering (alleen Nederland - voorbereid)
- 🔑 Admin wachtwoord in database (niet meer in code)
- 📥 Ledengegevens import (geboortedatum + teams)

### v1.9.34 (2025-12-28)
**Bugfix sidebar feedback:**
- 🐛 "Gegeven feedback" toont nu alleen feedback die je als scheidsrechter hebt gegeven
- 🐛 Begeleider_gezien records worden niet meer getoond in sidebar

### v1.9.33 (2025-12-28)
**Begeleider feedback melding:**
- 🎓 Begeleider ziet nu feedback in hoofdscherm (niet meer sidebar)
- 📋 Vergelijkbaar met collega feedback: "Scheidsrechter X gaf aan dat je..."
- ✓ OK knop slaat op in database (persistent, niet sessie-gebaseerd)
- 🔄 Nieuwe status: "begeleider_gezien" voor bevestiging

### v1.9.32 (2025-12-28)
**Beheerder refresh knop:**
- 🔄 "Ververs data" knop in header beheerder view
- Laadt alle data opnieuw zonder uitloggen

### v1.9.31 (2025-12-28)
**Debug voor TC Monitoring:**
- 🔍 Debug expander toont alle feedback records in database
- 🔍 Per wedstrijd: toont welke feedback_id wordt gezocht

### v1.9.30 (2025-12-28)
**Feedback systeem fixes:**
- 🔄 Feedback altijd vers laden (geen caching meer)
- 🔒 Verbeterde wijzig-blokkade check
- 🎓 Begeleider melding voor alle begeleiders (niet alleen MSE)
- 🐛 TC Monitoring tellers nu correct na reset

### v1.9.29 (2025-12-28)
**Feedback systeem verfijningen:**
- 🔒 Feedback niet wijzigbaar als collega al bevestigd heeft
- 🎓 MSE/Begeleider krijgt melding over ontvangen feedback
- 🐛 Fix: alleen echte feedback telt, geen bevestigingen
- 🧹 Debug code verwijderd

### v1.9.28 (2025-12-28)
**Debug OK-knop:**
- 🔍 Uitgebreide debug informatie bij OK-knop
- 📝 Volledige error logging in database functie
- ⏳ Visuele feedback bij klikken

### v1.9.27 (2025-12-28)
**Begeleiding indicator voor MSE's:**
- 🎓 Bij scheidsrechter naam: indicator als speler open staat voor begeleiding
- 👤🎓 Alleen zichtbaar voor MSE begeleiders
- 📋 Legenda uitgebreid voor MSE's

### v1.9.26 (2025-12-28)
**Bugfix OK-knop feedback:**
- 🐛 Cache wordt nu correct gecleared na opslaan feedback
- ✅ OK-knop zou nu moeten werken

### v1.9.25 (2025-12-28)
**Performance verbetering - complete caching:**
- 🚀 Caching toegevoegd aan alle resterende database functies
- 💾 laad_beloningen, laad_beloningsinstellingen, laad_instellingen nu gecached
- 🔧 Voorkomt "Resource temporarily unavailable" fouten volledig

### v1.9.24 (2025-12-28)
**Bugfixes feedback systeem:**
- 🐛 TC Monitoring: "Wacht op feedback" telt nu correct (1 echte feedback = klaar)
- 🐛 OK-knop werkt nu correct (cache fix)
- 👁️ "bevestigd" status wordt nu getoond als "gezien"
- 📊 Response rate berekening aangepast

### v1.9.23 (2025-12-28)
**Feedback systeem verbeteringen:**
- 🏆 Top Begeleiders telt alleen begeleidingen met positieve feedback
- 👥 Als collega al feedback gaf: alleen OK-knop nodig (geen enquête)
- ℹ️ Toon wat collega aangaf bij bevestiging

### v1.9.22 (2025-12-28)
**Bugfix feedback enquête:**
- 🐛 Begeleider krijgt niet langer feedback vraag over zichzelf
- ✅ Alleen scheidsrechters (niet de begeleider) krijgen de enquête

### v1.9.21 (2025-12-28)
**Performance verbetering:**
- 🚀 Caching toegevoegd aan alle database functies
- 🔧 Voorkomt "Resource temporarily unavailable" fouten
- 💾 Fallback naar oude cache bij connectieproblemen

### v1.9.20 (2025-12-28)
**Begeleiding Feedback Systeem:**
- 📋 Mini-enquête voor spelers na wedstrijd met begeleider
- ✅ Opties: "Aanwezig en geholpen", "Aanwezig niet geholpen", "Niet aanwezig"
- ✏️ Feedback wijzigen mogelijk via sidebar
- 🔍 TC Monitoring: overzicht van alle feedback met response rate
- 🗑️ TC kan feedback resetten indien nodig
- 📊 Statistieken: totaal, wacht op feedback, response rate

### v1.9.19 (2025-12-28)
**Filter verbetering:**
- 🔍 Wedstrijden waar je niets mee kunt (niet fluiten én niet begeleiden) worden verborgen
- 🎓 MSE's zien wedstrijden waar ze kunnen begeleiden ook als ze niet kunnen fluiten
- 📋 "Hele overzicht" toggle toont nog steeds alles

### v1.9.18 (2025-12-28)
**UI verduidelijking:**
- 📝 "eigen wedstrijd" → "speelt zelf" (duidelijker dat je overlap hebt met eigen wedstrijd)

### v1.9.17 (2025-12-28)
**Bugfix:**
- 🐛 Begeleider knop verborgen bij wedstrijden waar MSE zelf moet spelen

### v1.9.16 (2025-12-28)
**MSE functies geïntegreerd in wedstrijdoverzicht:**
- 🎓 Begeleider knop direct bij elke wedstrijd voor MSE's
- 📨 Uitnodiging selectbox bij wedstrijden waar MSE 1e scheids is
- 🗑️ Aparte MSE expanders verwijderd (ruimtebesparing)
- 📊 Compacte samenvatting bovenaan voor MSE's
- ❌ Afmelden als begeleider direct bij wedstrijd

### v1.9.15 (2025-12-28)
**Begeleider overzicht verbeterd:**
- 📋 Toon scheidsrechters bij elke wedstrijd (1e: naam | 2e: naam)
- 🎯 Alleen wedstrijden met minimaal 1 scheidsrechter getoond
- 🔢 Telling klopt nu met daadwerkelijk getoonde wedstrijden
- 📊 Scheidsrechter info ook bij "Mijn begeleidingen"

### v1.9.14 (2025-12-28)
**Begeleider functie:**
- 🎓 MSE kan zich aanmelden als begeleider (niet-fluitend) bij wedstrijden
- 📋 "Mijn begeleidingen" overzicht voor MSE's
- 👀 "Beschikbaar voor begeleiding" lijst met aanmeldknop
- 🏆 Begeleider telt mee voor Top Begeleiders klassement
- 👤 Begeleider zichtbaar bij wedstrijd voor spelers
- 🔧 Beheerder kan begeleider toewijzen/verwijderen

### v1.9.13 (2025-12-28)
**Klassementen:**
- 🏆 Top 3 scheidsrechters (op basis van punten) in sidebar
- 🎓 Top 3 begeleiders (MSE's met meeste begeleidingen) in sidebar

### v1.9.12 (2025-12-28)
**Bugfix:**
- 🐛 NameError opgelost in get_kandidaten_voor_wedstrijd (eigen_niveau → niveau_1e)

### v1.9.11 (2025-12-28)
**UI:**
- 🟠 Oranje lijn: zelfde CSS als blauwe border-top, 180° geroteerd (exacte match)

### v1.9.10 (2025-12-28)
**UI:**
- 🟠 Oranje lijn met taps toelopende uiteinden naar een punt (gevulde vorm)

### v1.9.9 (2025-12-28)
**UI:**
- 🟠 Oranje lijn: rechte onderkant met uiteinden die omhoog buigen naar punt

### v1.9.8 (2025-12-28)
**UI:**
- 🟠 Oranje lijn exact als blauwe lijn maar 180° gedraaid

### v1.9.7 (2025-12-28)
**UI:**
- 🟠 Oranje lijn nu recht met elegante gebogen uiteinden (spiegeling van blauwe lijn)

### v1.9.6 (2025-12-28)
**UI:**
- 🟠 Oranje lijn met afgeronde uiteinden (sluit aan bij metric blokken)

### v1.9.5 (2025-12-28)
**Ontwikkelstimulans:**
- 📈 Wedstrijden op hoger niveau tellen nu ook mee voor minimum
- 🏷️ Label gewijzigd naar "Niveau X+" om dit duidelijk te maken
- 🎯 Stimuleert spelers om zich te ontwikkelen naar hogere niveaus

### v1.9.4 (2025-12-27)
**UI:**
- 🟠 Gebogen oranje lijn verbeterd (subtielere curve)
- 🖼️ Logo's vergroot (70 → 90px)
- ➖ Divider onder filters verwijderd

### v1.9.3 (2025-12-27)
**UI:**
- 🟠 Gebogen oranje lijn hersteld met SVG curve

### v1.9.2 (2025-12-27)
**Bugfix tellingen:**
- 📊 Tellers bij filters kloppen nu exact met weergave
- 🚫 Uitwedstrijden worden niet meer meegeteld
- ✅ Alleen wedstrijden waar je daadwerkelijk kunt inschrijven worden geteld

### v1.9.1 (2025-12-27)
**Filter verbeteringen:**
- 🚫 Wedstrijden waar je niet op kunt inschrijven (eigen wedstrijd, overlap, zondag, BS2) worden nu ook gefilterd
- 📊 Telling bij filters klopt nu volledig met daadwerkelijk beschikbare wedstrijden
- 🔍 "Hele overzicht" toont nog steeds alle wedstrijden inclusief niet-beschikbare

### v1.9.0 (2025-12-27)
**Filter verbeteringen:**
- 📊 "Boven niveau" toont nu alleen wedstrijden waar je kunt inschrijven
- 🔍 "Hele overzicht" toont ook wedstrijden waar je niet op kunt inschrijven
- 📈 Telling bij filters klopt nu met daadwerkelijk beschikbare wedstrijden

### v1.8.9 (2025-12-27)
**Bugfix niveau regels:**
- 📐 2e scheids max niveau = eigen niveau + 1 (was onbeperkt)
- 🎓 Uitzondering: met MSE als 1e scheids nog steeds geen limiet
- 📋 Sidebar toont nu correcte niveau regels

### v1.8.8 (2025-12-27)
**Performance:**
- ⚡ Individuele wijzigingen nu via single-record opslag (veel sneller)
- 🔄 Cache wordt in-place bijgewerkt i.p.v. volledig herladen
- 💾 Bewerken/opslaan scheidsrechters nu instant

### v1.8.7 (2025-12-27)
**UI:**
- 📐 Witruimte onder container verwijderd
- 🙈 Footer en "Made with Streamlit" verborgen
- 📌 Header blijft nu beter sticky

### v1.8.6 (2025-12-27)
**Performance:**
- ⚡ Caching toegevoegd voor wedstrijden en scheidsrechters
- 🔄 Cache wordt automatisch geinvalideerd bij wijzigingen
- 🚀 Veel snellere laadtijden na eerste load

### v1.8.5 (2025-12-27)
**Performance:**
- ⚡ Bulk import voor wedstrijden en scheidsrechters (veel sneller)
- 🔄 Batches van 100 items tegelijk

### v1.8.4 (2025-12-27)
**Bugfix:**
- 🔄 Import nu via bevestigingsknop (voorkomt rerun loop)
- 📋 Preview van aantal items voor import

### v1.8.3 (2025-12-27)
**Bugfix:**
- 🔄 Automatische refresh na import scheidsrechters/wedstrijden

### v1.8.2 (2025-12-27)
**Bugfix:**
- 🐛 Alle beloningsinstellingen velden toegevoegd aan database defaults

### v1.8.1 (2025-12-27)
**Bugfix:**
- 🐛 punten_voor_voucher toegevoegd aan database defaults

### v1.8.0 (2025-12-27)
**Supabase Database integratie:**
- 💾 Alle data nu opgeslagen in Supabase (PostgreSQL)
- 🔄 Data blijft behouden na reboot/redeploy
- ⚡ Snellere dataverwerking
- 🔒 Robuuste opslag

### v1.7.7 (2025-12-27)
**Bugfix + Huisstijl:**
- 🐛 Sticky header hersteld (CSS selector verwijderd)
- 🟠 Gebogen oranje lijn nu via HTML element

### v1.7.6 (2025-12-27)
**Huisstijl:**
- 🟠 Gebogen oranje lijn direct onder de statistieken blokken

### v1.7.5 (2025-12-27)
**Huisstijl:**
- 🟠 Oranje divider lijnen toegevoegd (zoals in mockup optie 4)

### v1.7.4 (2025-12-27)
**Bugfix:**
- 🐛 Sidebar toonde "max niveau 6" terwijl niveau 5 het hoogste is - nu gecorrigeerd

### v1.7.3 (2025-12-27)
**Slimmere tellingen bij filters:**
- 📊 Mijn niveau/Boven niveau tonen nu BESCHIKBARE wedstrijden (niet ingeschreven, nog plek)
- 📊 Hele overzicht toont extra wedstrijden buiten doelmaand
- 📊 Titel toont aantal gefilterde wedstrijden: "Wedstrijdenoverzicht januari (12)"
- 🎯 Mijn wed telt alleen wedstrijden in doelmaand

### v1.7.2 (2025-12-27)
**Filter toggles verbeterd:**
- 📊 Alle toggles tonen nu aantallen
- 🔄 "Buiten [maand]" vervangen door "Hele overzicht (+X)"
- 📝 Titel dynamisch: "Wedstrijdenoverzicht [maand]" of "Wedstrijdenoverzicht"
- 🧹 Geen "Geen wedstrijden" melding meer als filters uit staan

### v1.7.1 (2025-12-27)
**UI verbeteringen:**
- 🎨 Sidebar nu lichtgrijs
- 🔘 Nieuwe filter: "Mijn wed" voor eigen wedstrijden aan/uit
- 🚗 Uitwedstrijden: thuisteam nu eerst genoemd (conventie)
- 🏠 Thuiswedstrijden: duidelijker label

### v1.7.0 (2025-12-27)
**BOB Huisstijl geïmplementeerd:**
- 🎨 Sidebar: wit met blauwe border (#003082)
- 🎨 Sidebar titels: blauw met oranje onderstreping
- 📊 Metrics: blauwe top border, oranje waarden
- 📦 Wedstrijden container: oranje border
- 🔵 Subheaders in blauw
- 🟠 Buttons en accenten in huisstijl

### v1.6.0 (2025-12-27)
**Filter toggles in header:**
- 🎯 Ingeschreven (X) - toon/verberg ingeschreven wedstrijden met aantal
- 📊 Mijn niveau - filter wedstrijden op eigen niveau
- 📈 Boven niveau - filter wedstrijden boven eigen niveau  
- 📅 Buiten [maand] - toon wedstrijden buiten doelmaand

### v1.5.3 (2025-12-27)
**Agressievere CSS voor witruimte:**
- 📐 Extra selectors voor margin/padding removal
- 🔧 Deploy button verborgen

### v1.5.2 (2025-12-27)
**Minder witruimte bovenaan:**
- 📐 Padding-top verwijderd (was 0.5rem)
- 🔧 Toolbar verborgen

### v1.5.1 (2025-12-27)
**Scrollbare container aangepast:**
- 📐 Container hoogte verhoogd van 450px naar 600px

### v1.5.0 (2025-12-27)
**Compacte header layout met scrollbare wedstrijden:**
- 🎨 Twee logo's: Waterdragers links, BOB rechts
- 📐 Minder witruimte, compactere metrics
- 📋 Alle actie-items (klusjes, uitnodigingen, verzoeken) in header
- 🎓 Begeleiding toggle compact in header
- 📅 Status en deadline naast elkaar
- 📜 Wedstrijden in scrollbare container (header blijft vast)

### v1.4.0 (2025-12-27)
**Niveau-exceptie bij MSE-begeleiding:**
- 🎓 Met MSE als 1e scheids: geen niveau-restrictie voor 2e scheids
- 📐 Sidebar toont nieuwe regel: "Met MSE als 1e: geen limiet"

### v1.3.0 (2025-12-26)
**MSE-uitnodigingssysteem:**
- 🎓 MSE ziet overzicht van wedstrijden waar ze 1e scheids zijn
- 📋 Per wedstrijd: lijst van beschikbare spelers die begeleiding willen
- 📨 MSE kan speler uitnodigen als 2e scheids
- ✅ Speler kan uitnodiging accepteren of weigeren
- 🔍 Beschikbaarheidscheck: geen eigen wedstrijd, niet al ingepland elders

### v1.2.1 (2025-12-26)
**UX verbeteringen begeleiding:**
- 🎯 Alle velden (toggle, reden, telefoon) direct zichtbaar bij openen
- 📂 Expander blijft open na opslaan
- 💡 Voordelen info bovenaan (verdwijnt als begeleiding aan staat)

### v1.2.0 (2025-12-26)
**Begeleidingssysteem:**
- 🎓 Nieuw: Spelers kunnen aangeven open te staan voor begeleiding
- 📋 Motivatie-keuze: "Vind het spannend", "Wil naar BS2", etc.
- 📱 Optioneel telefoonnummer delen voor WhatsApp contact
- 🔍 Filter in beheer op spelers die begeleiding willen
- 📊 Begeleidingskolom in overzichtstabel
- 👥 MSE-spelers zien aparte begeleidingsrol-info

### v1.1.0 (2025-12-25)
**Dynamische beloningsinstellingen:**
- ⚙️ Nieuw: Beloningssysteem volledig configureerbaar via beheer
- 🎛️ Instellingen tab met drie secties: Algemeen, Beloningssysteem, Over
- 💰 Aanpasbaar: punten per wedstrijd, bonussen, voucher drempel
- ⚠️ Aanpasbaar: strike waarden, waarschuwingsdrempels
- 🔧 Aanpasbaar: strike reductie waarden
- 🔄 Optie: strikes vervallen aan einde seizoen
- ↩️ Reset naar defaults functie

### v1.0.0 (2025-12-25)
**Nieuwe features:**
- ⚡ Bulk bewerking voor scheidsrechters (niveau/minimum aanpassen)
- 🏀 BS2/MSE capaciteitsanalyse met prioriteitsbewaking
- 💡 Nudge systeem: waarschuwing bij 2+ niveaus onder eigen niveau
- ⭐ Positieve nudge: stimulans voor 2e scheids op hoger niveau
- 📊 Verbeterde capaciteitsmonitor met uitleg cumulatieve berekening
- 🔄 Session state caching voor betere performance
- 📋 Overzichtstabel scheidsrechters met sorteeropties
- 🏷️ Versiebeheer met changelog

**Verwijderd:**
- Maximum wedstrijden limiet (conflicteerde met puntensysteem)
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ============================================================
# HELP-TEKSTEN
# ============================================================
HELP_TEKSTEN = {
    "Aan de slag": {
        "icon": "🚀",
        "onderwerpen": {
            "Wat is BOB?": "BOB staat voor **Beschikbaarheid, Ontwikkelen, Belonen**. Je schrijft je in om wedstrijden te fluiten, krijgt begeleiding als je dat wilt, en verdient punten voor beloningen.",
            "Inloggen": "Je ontvangt een persoonlijke link met jouw NBB-nummer erin. De eerste keer op een nieuw apparaat vragen we je geboortedatum ter verificatie. Daarna onthouden we dat apparaat.",
            "Je profiel": "In de sidebar zie je: je niveau als 1e en 2e scheidsrechter, je minimum aantal wedstrijden, je eigen team(s), en je punten en strikes."
        }
    },
    "Beschikbaarheid": {
        "icon": "📅",
        "onderwerpen": {
            "Inschrijven": "In de kalender zie je alle wedstrijden. Klik op een wedstrijd om je in te schrijven. Je kunt alleen wedstrijden kiezen die bij je niveau passen.",
            "Afmelden": "Moet je afmelden? Probeer altijd zelf vervanging te regelen. Afmelden zonder vervanging kort voor de wedstrijd levert strikes op.",
            "Vervanging regelen": "Vraag een andere scheidsrechter om jouw wedstrijd over te nemen. Accepteert diegene? Dan ben je afgemeld zonder strikes."
        }
    },
    "Ontwikkelen": {
        "icon": "📈",
        "onderwerpen": {
            "Begeleiding aanvragen": "Vind je fluiten spannend of wil je beter worden? Zet in je profiel dat je open staat voor begeleiding. Een MSE-scheidsrechter kan dan met je meekijken.",
            "Motivatie aangeven": "Geef aan waarom je begeleiding wilt: 'Ik vind het spannend', 'Ik wil naar BS2', of 'Ik wil beter worden'.",
            "Fluiten met een MSE'er": "Fluit je samen met een MSE-scheidsrechter? Dan mag je ook wedstrijden doen boven je eigen niveau. Zo leer je sneller!"
        }
    },
    "Belonen": {
        "icon": "🏆",
        "onderwerpen": {
            "Punten verdienen": "Je verdient punten door extra wedstrijden te fluiten (boven je minimum). Bonus voor lastige tijdstippen en last-minute invallen!",
            "Strikes": "Strikes krijg je bij afmelden zonder vervanging: binnen 48u = 1 strike, binnen 24u = 2 strikes, no-show = 5 strikes. Met vervanging = 0 strikes!",
            "Strikes wegwerken": "Klusje doen (-1), extra wedstrijd fluiten (-1), of invallen binnen 48u (-2 strikes).",
            "Beloningen": "Top 3 zichtbaar in de app. Bij voldoende punten: clinic naar keuze. Einde seizoen: financiële beloning voor top 3!"
        }
    },
    "Voor MSE": {
        "icon": "🎓",
        "onderwerpen": {
            "Spelers begeleiden": "Je ziet in de app welke spelers open staan voor begeleiding en waarom. Zo kun je gericht helpen.",
            "Ik kom kijken": "Geef aan dat je komt kijken bij een wedstrijd. De speler krijgt hiervan een melding.",
            "Uitnodigen als 2e": "Nodig een speler uit om samen te fluiten. Jij bent 1e, zij leren als 2e. Ze mogen dan ook wedstrijden boven hun niveau doen."
        }
    }
}

# Custom CSS voor afwisselende dag-achtergronden
def inject_custom_css():
    st.markdown("""
    <style>
    .dag-even {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .dag-oneven {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .dag-header {
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #ff6b35;
    }
    .dag-header-even {
        border-bottom-color: #1e88e5;
    }
    .eigen-wedstrijd {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0 0.5rem 0.5rem 0;
    }
    .fluit-wedstrijd {
        background-color: #e3f2fd;
        border-left: 4px solid #1e88e5;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0 0.5rem 0.5rem 0;
    }
    /* Groene primary buttons - meerdere selectors voor compatibiliteit */
    button[kind="primary"],
    button[data-testid="baseButton-primary"],
    .stButton button[kind="primary"] {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
        color: white !important;
    }
    button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover,
    .stButton button[kind="primary"]:hover {
        background-color: #218838 !important;
        border-color: #1e7e34 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Configuratie
DATA_DIR = Path(__file__).parent / "data"
# Wachtwoord wordt nu veilig beheerd via database en Streamlit Secrets

# Teams waaruit scheidsrechters komen (vanaf U16, plus coaches van lagere teams)
SCHEIDSRECHTER_TEAMS = [
    "V12-2",  # Voor coaches
    "X14-1",  # Voor coaches
    "M16-1", "M16-2",
    "V16-1", "V16-2",
    "M18-1", "M18-2", "M18-3",
    "M20-1",
    "MSE-1"
]

# Redenen voor begeleiding (bij fluiten)
BEGELEIDING_REDENEN = [
    "Ik vind fluiten nog spannend",
    "Ik wil richting BS2 diploma",
    "Ik wil beter worden in fluiten",
    "Samen fluiten is gezelliger"
]

# Status opties voor scheidsrechters
SCHEIDSRECHTER_STATUS_OPTIES = [
    "Actief",           # Kan zelfstandig worden ingepland
    "Op te leiden",     # Moet nog getraind worden door TC-support
    "Inactief"          # Niet beschikbaar (gestopt, pauze, etc.)
]

def team_match(volledig_team: str, eigen_team: str) -> bool:
    """
    Check of een volledige teamnaam (bijv. 'Waterdragers - M18-3**') 
    matcht met een eigen team (bijv. 'M18-3').
    
    Het moet ZOWEL een Waterdragers team zijn ALS de teamcode matchen.
    Dit voorkomt dat bijv. 'Simple Dribble - M18-1' matcht met eigen team 'M18-1'.
    """
    if not volledig_team or not eigen_team:
        return False
    
    # Normaliseer: uppercase en verwijder sterretjes
    volledig = str(volledig_team).upper().replace("*", "").strip()
    eigen = str(eigen_team).upper().replace("*", "").strip()
    
    # Check of het een Waterdragers team is
    if "WATERDRAGERS" not in volledig:
        return False
    
    # Check of eigen team in de volledige naam zit
    return eigen in volledig

# Zorg dat data directory bestaat
DATA_DIR.mkdir(exist_ok=True)

# ============================================================
# DATA FUNCTIES
# ============================================================

def laad_json(bestand: str) -> dict | list:
    """Laad JSON bestand, retourneer lege dict/list als niet bestaat of corrupt."""
    pad = DATA_DIR / bestand
    if pad.exists():
        try:
            with open(pad, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, Exception) as e:
            # Maak backup van corrupt bestand
            backup_pad = DATA_DIR / f"{bestand}.corrupt.{datetime.now().strftime('%Y%m%d%H%M%S')}"
            try:
                import shutil
                shutil.copy(pad, backup_pad)
            except:
                pass
            # Log de fout
            print(f"FOUT bij laden {bestand}: {e}")
            return {}
    return {}

def sla_json_op(bestand: str, data: dict | list):
    """Sla data op als JSON met backup."""
    pad = DATA_DIR / bestand
    
    # Maak eerst backup als bestand bestaat
    if pad.exists():
        backup_pad = DATA_DIR / f"{bestand}.backup"
        try:
            import shutil
            shutil.copy(pad, backup_pad)
        except:
            pass
    
    # Schrijf nieuwe data
    try:
        with open(pad, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"FOUT bij opslaan {bestand}: {e}")
    
    # Clear cache voor dit bestand
    cache_key = f"_cache_{bestand}"
    if cache_key in st.session_state:
        del st.session_state[cache_key]

def _get_cached(bestand: str, loader_func) -> dict | list:
    """Haal data uit cache of laad opnieuw."""
    cache_key = f"_cache_{bestand}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = loader_func()
    return st.session_state[cache_key]

def _clear_cache(bestand: str = None):
    """Clear cache voor specifiek bestand of alles."""
    if bestand:
        cache_key = f"_cache_{bestand}"
        if cache_key in st.session_state:
            del st.session_state[cache_key]
    else:
        # Clear alle caches
        keys_to_delete = [k for k in st.session_state.keys() if k.startswith("_cache_")]
        for k in keys_to_delete:
            del st.session_state[k]

# Default beloningsinstellingen
DEFAULT_BELONINGSINSTELLINGEN = {
    # Punten
    "punten_per_wedstrijd": 1,
    "punten_lastig_tijdstip": 1,
    "punten_inval_48u": 3,
    "punten_inval_24u": 5,
    "punten_voor_voucher": 15,
    
    # Pool bonus (kritieke wedstrijden)
    "punten_pool_kritiek": 3,      # Pool ≤ 3
    "punten_pool_zeer_krap": 2,    # Pool 4-5
    "punten_pool_krap": 1,         # Pool 6-8
    "pool_kritiek_grens": 3,       # Pool ≤ deze waarde = kritiek
    "pool_zeer_krap_grens": 5,     # Pool ≤ deze waarde = zeer krap
    "pool_krap_grens": 8,          # Pool ≤ deze waarde = krap
    
    # Strikes
    "strikes_afmelding_48u": 1,
    "strikes_afmelding_24u": 2,
    "strikes_no_show": 5,
    "strikes_waarschuwing_bij": 2,
    "strikes_gesprek_bij": 3,
    
    # Strike reductie
    "strike_reductie_extra_wedstrijd": 1,
    "strike_reductie_invallen": 2,
    
    # Seizoen
    "strikes_vervallen_einde_seizoen": False
}

def laad_beloningsinstellingen() -> dict:
    """Laad beloningsinstellingen uit database."""
    return db.laad_beloningsinstellingen()

def sla_beloningsinstellingen_op(data: dict):
    db.sla_beloningsinstellingen_op(data)

def laad_scheidsrechters() -> dict:
    return db.laad_scheidsrechters()

def laad_wedstrijden() -> dict:
    return db.laad_wedstrijden()

def laad_inschrijvingen() -> dict:
    # Inschrijvingen zitten nu in wedstrijden (scheids_1, scheids_2)
    return {}

def laad_instellingen() -> dict:
    return db.laad_instellingen()

def sla_scheidsrechters_op(data: dict):
    db.sla_scheidsrechters_op(data)

def sla_scheidsrechter_op(nbb_nummer: str, data: dict):
    """Sla één scheidsrechter op (sneller dan bulk)"""
    db.sla_scheidsrechter_op(nbb_nummer, data)

def sla_wedstrijden_op(data: dict):
    db.sla_wedstrijden_op(data)

def sla_wedstrijd_op(wed_id: str, data: dict):
    """Sla één wedstrijd op (sneller dan bulk)"""
    db.sla_wedstrijd_op(wed_id, data)

def sla_inschrijvingen_op(data: dict):
    # Niet meer nodig - inschrijvingen zitten in wedstrijden
    pass

def sla_instellingen_op(data: dict):
    db.sla_instellingen_op(data)

def laad_beloningen() -> dict:
    """Laad beloningen (punten, strikes per speler)."""
    return db.laad_beloningen()

def sla_beloningen_op(data: dict):
    db.sla_beloningen_op(data)

def laad_klusjes() -> dict:
    """Laad klusjes (toegewezen aan spelers)."""
    return db.laad_klusjes()

def sla_klusjes_op(data: dict):
    db.sla_klusjes_op(data)

def laad_vervangingsverzoeken() -> dict:
    """Laad openstaande vervangingsverzoeken."""
    return db.laad_vervangingsverzoeken()

def sla_vervangingsverzoeken_op(data: dict):
    db.sla_vervangingsverzoeken_op(data)

def laad_begeleidingsuitnodigingen() -> dict:
    """Laad begeleidingsuitnodigingen (MSE nodigt speler uit als 2e scheids)."""
    return db.laad_begeleidingsuitnodigingen()

def sla_begeleidingsuitnodigingen_op(data: dict):
    db.sla_begeleidingsuitnodigingen_op(data)

def laad_begeleiding_feedback() -> dict:
    """Laad begeleiding feedback van spelers over begeleiders."""
    return db.laad_begeleiding_feedback()

def sla_begeleiding_feedback_op(feedback_id: str, data: dict) -> bool:
    """Sla begeleiding feedback op."""
    return db.sla_begeleiding_feedback_op(feedback_id, data)

def verwijder_begeleiding_feedback(feedback_id: str) -> bool:
    """Verwijder begeleiding feedback."""
    return db.verwijder_begeleiding_feedback(feedback_id)

def laad_beschikbare_klusjes() -> list:
    """Laad de lijst met beschikbare klusjes die TC kan toewijzen."""
    return db.laad_beschikbare_klusjes()

def sla_beschikbare_klusjes_op(data: list):
    db.sla_beschikbare_klusjes_op(data)

# ============================================================
# BELONINGSSYSTEEM FUNCTIES
# ============================================================

def get_speler_stats(nbb_nummer: str) -> dict:
    """Haal punten en strikes op voor een speler."""
    beloningen = laad_beloningen()
    speler_data = beloningen.get("spelers", {}).get(nbb_nummer, {})
    return {
        "punten": speler_data.get("punten", 0),
        "strikes": speler_data.get("strikes", 0),
        "gefloten_wedstrijden": speler_data.get("gefloten_wedstrijden", []),
        "strike_log": speler_data.get("strike_log", []),
        "punten_log": speler_data.get("punten_log", [])
    }

def get_top_scheidsrechters(n: int = 3) -> list:
    """Haal top N scheidsrechters op basis van punten."""
    beloningen = laad_beloningen()
    scheidsrechters = laad_scheidsrechters()
    
    punten_lijst = []
    for nbb, data in beloningen.get("spelers", {}).items():
        punten = data.get("punten", 0)
        if punten > 0 and nbb in scheidsrechters:
            naam = scheidsrechters[nbb].get("naam", "Onbekend")
            punten_lijst.append({"nbb": nbb, "naam": naam, "punten": punten})
    
    # Sorteer op punten (hoogste eerst)
    punten_lijst.sort(key=lambda x: x["punten"], reverse=True)
    return punten_lijst[:n]

def get_punten_klassement_met_positie(eigen_nbb: str) -> dict:
    """
    Haal punten klassement op met top 3 en eigen positie.
    Returns: {"top3": [...], "eigen": {"positie": N, "naam": ..., "punten": ...} of None}
    """
    beloningen = laad_beloningen()
    scheidsrechters = laad_scheidsrechters()
    
    punten_lijst = []
    for nbb, data in beloningen.get("spelers", {}).items():
        punten = data.get("punten", 0)
        if nbb in scheidsrechters:
            naam = scheidsrechters[nbb].get("naam", "Onbekend")
            punten_lijst.append({"nbb": nbb, "naam": naam, "punten": punten})
    
    # Sorteer op punten (hoogste eerst), dan op naam
    punten_lijst.sort(key=lambda x: (-x["punten"], x["naam"]))
    
    # Top 3
    top3 = punten_lijst[:3]
    
    # Eigen positie zoeken
    eigen = None
    for i, speler in enumerate(punten_lijst):
        if speler["nbb"] == eigen_nbb:
            eigen = {
                "positie": i + 1,
                "nbb": speler["nbb"],
                "naam": speler["naam"],
                "punten": speler["punten"]
            }
            break
    
    # Als eigen niet in lijst staat (0 punten), voeg toe
    if eigen is None and eigen_nbb in scheidsrechters:
        eigen_punten = beloningen.get("spelers", {}).get(eigen_nbb, {}).get("punten", 0)
        # Tel hoeveel spelers meer punten hebben
        positie = sum(1 for s in punten_lijst if s["punten"] > eigen_punten) + 1
        eigen = {
            "positie": positie,
            "nbb": eigen_nbb,
            "naam": scheidsrechters[eigen_nbb].get("naam", "Onbekend"),
            "punten": eigen_punten
        }
    
    return {"top3": top3, "eigen": eigen}

def get_top_begeleiders(n: int = 3) -> list:
    """
    Haal top N begeleiders (MSE's) op basis van aantal bevestigde begeleidingen.
    Een begeleiding telt alleen als er positieve feedback is ontvangen.
    Alleen spelers met "MSE" in hun eigen_teams tellen als MSE (niet alleen niveau 5).
    """
    scheidsrechters = laad_scheidsrechters()
    wedstrijden = laad_wedstrijden()
    feedback_data = laad_begeleiding_feedback()
    
    # Tel begeleidingen per MSE (alleen met positieve feedback)
    begeleiding_count = {}
    
    for wed_id, wed in wedstrijden.items():
        # Check of wedstrijd al gespeeld is
        try:
            wed_datum = datetime.strptime(wed.get("datum", ""), "%Y-%m-%d %H:%M")
            if wed_datum > datetime.now():
                continue  # Wedstrijd nog niet gespeeld
        except:
            continue
        
        # Tel niet-fluitende begeleider (alleen met positieve feedback)
        begeleider_nbb = wed.get("begeleider")
        if begeleider_nbb and begeleider_nbb in scheidsrechters:
            # Check of begeleider een echte MSE is
            begeleider = scheidsrechters.get(begeleider_nbb, {})
            is_mse_begeleider = any("MSE" in t.upper() for t in begeleider.get("eigen_teams", []))
            
            if is_mse_begeleider:
                # Check of er positieve feedback is van een van de scheidsrechters
                scheids_1 = wed.get("scheids_1")
                scheids_2 = wed.get("scheids_2")
                
                heeft_positieve_feedback = False
                for scheids_nbb in [scheids_1, scheids_2]:
                    if scheids_nbb:
                        fb = feedback_data.get(f"fb_{wed_id}_{scheids_nbb}")
                        if fb and fb.get("status") == "aanwezig_geholpen":
                            heeft_positieve_feedback = True
                            break
                
                if heeft_positieve_feedback:
                    if begeleider_nbb not in begeleiding_count:
                        begeleiding_count[begeleider_nbb] = 0
                    begeleiding_count[begeleider_nbb] += 1
        
        # Tel fluitende begeleiding (MSE als 1e scheids met speler die begeleiding wilde)
        # Dit telt alleen als:
        # 1. 1e scheids is een echte MSE (MSE in eigen_teams)
        # 2. 2e scheids had open_voor_begeleiding aan
        # 3. Er is positieve feedback gegeven
        scheids_1_nbb = wed.get("scheids_1")
        scheids_2_nbb = wed.get("scheids_2")
        
        if not scheids_1_nbb or not scheids_2_nbb:
            continue
        
        scheids_1 = scheidsrechters.get(scheids_1_nbb, {})
        scheids_2 = scheidsrechters.get(scheids_2_nbb, {})
        
        # Check of 1e scheids een echte MSE is (MSE in eigen_teams, niet alleen niveau 5)
        is_mse = any("MSE" in t.upper() for t in scheids_1.get("eigen_teams", []))
        
        if not is_mse:
            continue
        
        # Check of 2e scheids open stond voor begeleiding
        if not scheids_2.get("open_voor_begeleiding", False):
            continue
        
        # Check of er positieve feedback is van de 2e scheids
        fb = feedback_data.get(f"fb_{wed_id}_{scheids_2_nbb}")
        if fb and fb.get("status") == "aanwezig_geholpen":
            if scheids_1_nbb not in begeleiding_count:
                begeleiding_count[scheids_1_nbb] = 0
            begeleiding_count[scheids_1_nbb] += 1
    
    # Maak lijst en sorteer
    begeleiders_lijst = []
    for nbb, count in begeleiding_count.items():
        if count > 0:
            naam = scheidsrechters.get(nbb, {}).get("naam", "Onbekend")
            begeleiders_lijst.append({"nbb": nbb, "naam": naam, "begeleidingen": count})
    
    begeleiders_lijst.sort(key=lambda x: x["begeleidingen"], reverse=True)
    return begeleiders_lijst[:n]

def get_begeleiders_klassement_met_positie(eigen_nbb: str) -> dict:
    """
    Haal begeleiders klassement op met top 3 en eigen positie.
    Returns: {"top3": [...], "eigen": {"positie": N, "naam": ..., "begeleidingen": ...} of None}
    """
    scheidsrechters = laad_scheidsrechters()
    wedstrijden = laad_wedstrijden()
    feedback_data = laad_begeleiding_feedback()
    
    # Tel begeleidingen per MSE (zelfde logica als get_top_begeleiders)
    # Begeleiding telt alleen als:
    # 1. Begeleider is echte MSE (MSE in eigen_teams)
    # 2. Er is positieve feedback ontvangen
    begeleiding_count = {}
    
    for wed_id, wed in wedstrijden.items():
        # Check of wedstrijd al gespeeld is
        try:
            wed_datum = datetime.strptime(wed.get("datum", ""), "%Y-%m-%d %H:%M")
            if wed_datum > datetime.now():
                continue  # Wedstrijd nog niet gespeeld
        except:
            continue
        
        # Tel niet-fluitende begeleider (alleen met positieve feedback)
        begeleider_nbb = wed.get("begeleider")
        if begeleider_nbb and begeleider_nbb in scheidsrechters:
            # Check of begeleider een echte MSE is
            begeleider = scheidsrechters.get(begeleider_nbb, {})
            is_mse_begeleider = any("MSE" in t.upper() for t in begeleider.get("eigen_teams", []))
            
            if is_mse_begeleider:
                scheids_1 = wed.get("scheids_1")
                scheids_2 = wed.get("scheids_2")
                
                heeft_positieve_feedback = False
                for scheids_nbb in [scheids_1, scheids_2]:
                    if scheids_nbb:
                        fb = feedback_data.get(f"fb_{wed_id}_{scheids_nbb}")
                        if fb and fb.get("status") == "aanwezig_geholpen":
                            heeft_positieve_feedback = True
                            break
                
                if heeft_positieve_feedback:
                    if begeleider_nbb not in begeleiding_count:
                        begeleiding_count[begeleider_nbb] = 0
                    begeleiding_count[begeleider_nbb] += 1
        
        # Tel fluitende begeleiding (MSE als 1e scheids met speler die begeleiding wilde)
        scheids_1_nbb = wed.get("scheids_1")
        scheids_2_nbb = wed.get("scheids_2")
        
        if not scheids_1_nbb or not scheids_2_nbb:
            continue
        
        scheids_1 = scheidsrechters.get(scheids_1_nbb, {})
        scheids_2 = scheidsrechters.get(scheids_2_nbb, {})
        
        # Check of 1e scheids een echte MSE is (MSE in eigen_teams, niet alleen niveau 5)
        is_mse = any("MSE" in t.upper() for t in scheids_1.get("eigen_teams", []))
        
        if not is_mse:
            continue
        
        # Check of 2e scheids open stond voor begeleiding
        if not scheids_2.get("open_voor_begeleiding", False):
            continue
        
        # Check of er positieve feedback is van de 2e scheids
        fb = feedback_data.get(f"fb_{wed_id}_{scheids_2_nbb}")
        if fb and fb.get("status") == "aanwezig_geholpen":
            if scheids_1_nbb not in begeleiding_count:
                begeleiding_count[scheids_1_nbb] = 0
            begeleiding_count[scheids_1_nbb] += 1
    
    # Maak lijst en sorteer
    begeleiders_lijst = []
    for nbb, count in begeleiding_count.items():
        naam = scheidsrechters.get(nbb, {}).get("naam", "Onbekend")
        begeleiders_lijst.append({"nbb": nbb, "naam": naam, "begeleidingen": count})
    
    # Sorteer op begeleidingen (hoogste eerst), dan op naam
    begeleiders_lijst.sort(key=lambda x: (-x["begeleidingen"], x["naam"]))
    
    # Top 3
    top3 = begeleiders_lijst[:3]
    
    # Eigen positie zoeken
    eigen = None
    for i, begeleider in enumerate(begeleiders_lijst):
        if begeleider["nbb"] == eigen_nbb:
            eigen = {
                "positie": i + 1,
                "nbb": begeleider["nbb"],
                "naam": begeleider["naam"],
                "begeleidingen": begeleider["begeleidingen"]
            }
            break
    
    # Als eigen niet in lijst staat (0 begeleidingen)
    if eigen is None and eigen_nbb in scheidsrechters:
        eigen_count = begeleiding_count.get(eigen_nbb, 0)
        # Tel hoeveel begeleiders meer begeleidingen hebben
        positie = sum(1 for b in begeleiders_lijst if b["begeleidingen"] > eigen_count) + 1
        eigen = {
            "positie": positie,
            "nbb": eigen_nbb,
            "naam": scheidsrechters[eigen_nbb].get("naam", "Onbekend"),
            "begeleidingen": eigen_count
        }
    
    return {"top3": top3, "eigen": eigen}

def voeg_punten_toe(nbb_nummer: str, punten: int, reden: str, wed_id: str = None, berekening: dict = None):
    """Voeg punten toe aan een speler met volledige berekening voor transparantie."""
    beloningen = laad_beloningen()
    if nbb_nummer not in beloningen["spelers"]:
        beloningen["spelers"][nbb_nummer] = {"punten": 0, "strikes": 0, "gefloten_wedstrijden": [], "strike_log": []}
    
    beloningen["spelers"][nbb_nummer]["punten"] += punten
    if wed_id:
        registratie = {
            "wed_id": wed_id,
            "punten": punten,
            "reden": reden,
            "geregistreerd_op": datetime.now().isoformat()
        }
        if berekening:
            registratie["berekening"] = berekening
        beloningen["spelers"][nbb_nummer]["gefloten_wedstrijden"].append(registratie)
    sla_beloningen_op(beloningen)

def voeg_strike_toe(nbb_nummer: str, strikes: int, reden: str):
    """Voeg strikes toe aan een speler."""
    beloningen = laad_beloningen()
    if nbb_nummer not in beloningen["spelers"]:
        beloningen["spelers"][nbb_nummer] = {"punten": 0, "strikes": 0, "gefloten_wedstrijden": [], "strike_log": []}
    
    beloningen["spelers"][nbb_nummer]["strikes"] += strikes
    beloningen["spelers"][nbb_nummer]["strike_log"].append({
        "strikes": strikes,
        "reden": reden,
        "datum": datetime.now().isoformat()
    })
    sla_beloningen_op(beloningen)

def verwijder_strike(nbb_nummer: str, strikes: int, reden: str):
    """Verwijder strikes van een speler (door klusje of extra wedstrijd)."""
    beloningen = laad_beloningen()

def pas_punten_aan(nbb_nummer: str, punten: int, reden: str):
    """
    Pas punten aan voor een speler (positief = bijboeken, negatief = afboeken).
    Wordt gelogd in punten_log voor transparantie.
    """
    beloningen = laad_beloningen()
    if nbb_nummer not in beloningen["spelers"]:
        beloningen["spelers"][nbb_nummer] = {"punten": 0, "strikes": 0, "gefloten_wedstrijden": [], "strike_log": [], "punten_log": []}
    
    # Zorg dat punten_log bestaat (voor bestaande spelers)
    if "punten_log" not in beloningen["spelers"][nbb_nummer]:
        beloningen["spelers"][nbb_nummer]["punten_log"] = []
    
    oude_punten = beloningen["spelers"][nbb_nummer]["punten"]
    beloningen["spelers"][nbb_nummer]["punten"] = max(0, oude_punten + punten)  # Niet onder 0
    nieuwe_punten = beloningen["spelers"][nbb_nummer]["punten"]
    
    beloningen["spelers"][nbb_nummer]["punten_log"].append({
        "punten": punten,
        "oude_stand": oude_punten,
        "nieuwe_stand": nieuwe_punten,
        "reden": reden,
        "datum": datetime.now().isoformat(),
        "handmatig": True
    })
    sla_beloningen_op(beloningen)
    if nbb_nummer in beloningen["spelers"]:
        beloningen["spelers"][nbb_nummer]["strikes"] = max(0, beloningen["spelers"][nbb_nummer]["strikes"] - strikes)
        beloningen["spelers"][nbb_nummer]["strike_log"].append({
            "strikes": -strikes,
            "reden": reden,
            "datum": datetime.now().isoformat()
        })
        sla_beloningen_op(beloningen)

def is_lastig_tijdstip(nbb_nummer: str, wed_datum: datetime, wedstrijden: dict, scheidsrechters: dict) -> bool:
    """
    Check of dit een 'lastig tijdstip' is voor de speler.
    Lastig = >2u na eigen wedstrijd, >4u voor eigen thuiswedstrijd, of dag zonder eigen wedstrijd.
    """
    scheids = scheidsrechters.get(nbb_nummer, {})
    eigen_teams = scheids.get("eigen_teams", [])
    
    if not eigen_teams:
        return True  # Geen eigen wedstrijden = altijd lastig (moet apart komen)
    
    wed_dag = wed_datum.date()
    
    eigen_wedstrijden_vandaag = []
    for wed_id, wed in wedstrijden.items():
        # Check of dit een eigen wedstrijd is
        is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams)
        is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams)
        
        is_eigen_wed = False
        if wed.get("type") == "uit" and is_eigen_thuis:
            is_eigen_wed = True
        elif wed.get("type") != "uit" and (is_eigen_thuis or is_eigen_uit):
            is_eigen_wed = True
        
        if is_eigen_wed:
            eigen_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
            if eigen_datum.date() == wed_dag:
                eigen_wedstrijden_vandaag.append({
                    "datum": eigen_datum,
                    "type": wed.get("type", "thuis"),
                    "thuis": wed.get("type") != "uit"
                })
    
    # Geen eigen wedstrijd op deze dag = lastig tijdstip (moet apart komen)
    if not eigen_wedstrijden_vandaag:
        return True
    
    # Check elke eigen wedstrijd
    for eigen_wed in eigen_wedstrijden_vandaag:
        eigen_datum = eigen_wed["datum"]
        
        # Fluitwedstrijd is >2u NA eigen wedstrijd einde
        eigen_eind = eigen_datum + timedelta(hours=1, minutes=30)
        if wed_datum > eigen_eind + timedelta(hours=2):
            return True
        
        # Fluitwedstrijd is >4u VOOR eigen thuiswedstrijd
        if eigen_wed["thuis"] and wed_datum < eigen_datum - timedelta(hours=4):
            return True
    
    return False

def is_last_minute_inval(wed_id: str, wed_datum: datetime) -> dict:
    """
    Check of dit een last-minute inval is.
    Returns: {"is_inval": bool, "bonus": int, "uren": int}
    """
    beloningsinst = laad_beloningsinstellingen()
    nu = datetime.now()
    verschil = wed_datum - nu
    uren = verschil.total_seconds() / 3600
    
    if uren < 24:
        return {"is_inval": True, "bonus": beloningsinst["punten_inval_24u"], "uren": 24}
    elif uren < 48:
        return {"is_inval": True, "bonus": beloningsinst["punten_inval_48u"], "uren": 48}
    else:
        return {"is_inval": False, "bonus": 0, "uren": 0}

def bereken_punten_voor_wedstrijd(nbb_nummer: str, wed_id: str, wedstrijden: dict, scheidsrechters: dict, bron: str = "zelf") -> dict:
    """
    Bereken hoeveel punten een speler krijgt voor een wedstrijd.
    
    Args:
        nbb_nummer: NBB nummer van de scheidsrechter
        wed_id: ID van de wedstrijd
        wedstrijden: Dict van alle wedstrijden
        scheidsrechters: Dict van alle scheidsrechters
        bron: Hoe de inschrijving tot stand kwam:
              - "zelf": Speler schreef zichzelf in (geen last-minute bonus)
              - "vervanging": Via vervangingsverzoek van afmelder
              - "tc": Handmatig toegewezen door TC
              - "uitnodiging": Via MSE begeleidingsuitnodiging
              - "heraanmelding": Speler die zich eerder had afgemeld (GEEN bonussen!)
    
    Returns: {"basis": int, "lastig_tijdstip": int, "inval_bonus": int, "pool_bonus": int, "totaal": int, "details": str, "berekening": dict}
    """
    beloningsinst = laad_beloningsinstellingen()
    wed = wedstrijden.get(wed_id, {})
    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    nu = datetime.now()
    
    # Bereken uren tot wedstrijd
    verschil = wed_datum - nu
    uren_tot_wedstrijd = verschil.total_seconds() / 3600
    
    # NIEUW: Bij heraanmelding krijgt speler alleen basispunten, geen bonussen
    is_heraanmelding = bron == "heraanmelding"
    
    # Basis punten (altijd)
    basis = beloningsinst["punten_per_wedstrijd"]
    
    # Lastig tijdstip - NIET bij heraanmelding
    if is_heraanmelding:
        lastig = 0
    else:
        lastig = beloningsinst["punten_lastig_tijdstip"] if is_lastig_tijdstip(nbb_nummer, wed_datum, wedstrijden, scheidsrechters) else 0
    
    # Last-minute inval bonus - ALLEEN bij vervanging, TC-toewijzing of uitnodiging
    # Zelf inschrijven en heraanmelding geeft geen bonus
    inval_bonus = 0
    inval_info = {"is_inval": False, "bonus": 0, "uren": 0}
    
    if bron in ["vervanging", "tc", "uitnodiging"]:
        inval_info = is_last_minute_inval(wed_id, wed_datum)
        inval_bonus = inval_info["bonus"]
    
    # Pool bonus - beloning voor inschrijven op kritieke wedstrijden
    # NIET bij heraanmelding (om gaming te voorkomen: afmelden en dan bonus claimen)
    pool_bonus = 0
    pool_size = bereken_pool_voor_wedstrijd(wed_id, wedstrijden, scheidsrechters)
    pool_categorie = ""
    
    if not is_heraanmelding:  # Alleen bonus als het geen heraanmelding is
        if pool_size <= beloningsinst.get("pool_kritiek_grens", 3):
            pool_bonus = beloningsinst.get("punten_pool_kritiek", 3)
            pool_categorie = "kritiek"
        elif pool_size <= beloningsinst.get("pool_zeer_krap_grens", 5):
            pool_bonus = beloningsinst.get("punten_pool_zeer_krap", 2)
            pool_categorie = "zeer krap"
        elif pool_size <= beloningsinst.get("pool_krap_grens", 8):
            pool_bonus = beloningsinst.get("punten_pool_krap", 1)
            pool_categorie = "krap"
    
    totaal = basis + lastig + inval_bonus + pool_bonus
    
    details = []
    details.append(f"{basis} basis")
    if lastig:
        details.append(f"+{lastig} lastig tijdstip")
    if inval_bonus:
        details.append(f"+{inval_bonus} inval <{inval_info['uren']}u")
    if pool_bonus:
        details.append(f"+{pool_bonus} {pool_categorie} pool")
    if is_heraanmelding:
        details.append("(heraanmelding, geen bonus)")
    
    # Gedetailleerde berekening voor transparantie
    berekening = {
        "inschrijf_moment": nu.isoformat(),
        "inschrijf_moment_leesbaar": nu.strftime("%d-%m-%Y %H:%M"),
        "wedstrijd_datum": wed_datum.isoformat(),
        "wedstrijd_datum_leesbaar": wed_datum.strftime("%d-%m-%Y %H:%M"),
        "uren_tot_wedstrijd": round(uren_tot_wedstrijd, 1),
        "is_inval_48u": uren_tot_wedstrijd < 48,
        "is_inval_24u": uren_tot_wedstrijd < 24,
        "is_lastig_tijdstip": lastig > 0,
        "pool_size": pool_size,
        "pool_categorie": pool_categorie,
        "bron": bron,
        "is_heraanmelding": is_heraanmelding,
        "bonus_reden": "heraanmelding (geen bonus)" if is_heraanmelding else ("vervanging/TC" if bron in ["vervanging", "tc", "uitnodiging"] else "zelf ingeschreven (geen bonus)")
    }
    
    return {
        "basis": basis,
        "lastig_tijdstip": lastig,
        "inval_bonus": inval_bonus,
        "pool_bonus": pool_bonus,
        "totaal": totaal,
        "details": ", ".join(details),
        "berekening": berekening
    }

# ============================================================
# UI HELPER FUNCTIES
# ============================================================

def toon_error_met_scroll(melding: str):
    """
    Toon een error melding.
    Note: Auto-scroll is verwijderd omdat het niet goed werkt in Streamlit's container model.
    """
    st.error(melding)

def scroll_naar_warning():
    """
    Placeholder functie - scroll is uitgeschakeld.
    """
    pass  # Scroll werkt niet goed in Streamlit, dus uitgeschakeld

# ============================================================
# AFMELDREGISTRATIE FUNCTIES
# ============================================================

def registreer_afmelding(wed_id: str, nbb_nummer: str, positie: str, wedstrijden: dict) -> bool:
    """
    Registreer dat een scheidsrechter zich heeft afgemeld voor een wedstrijd.
    Dit zorgt ervoor dat:
    1. De scheidsrechter niet meer meetelt in de pool
    2. Bij heraanmelding geen bonus wordt gegeven
    3. TC kan zien wie zich eerder had afgemeld
    
    Args:
        wed_id: ID van de wedstrijd
        nbb_nummer: NBB nummer van de scheidsrechter die zich afmeldt
        positie: "scheids_1" of "scheids_2"
        wedstrijden: Dict van alle wedstrijden
    
    Returns:
        True bij succes
    """
    if wed_id not in wedstrijden:
        return False
    
    wed = wedstrijden[wed_id]
    
    # Initialiseer afgemeld_door lijst als die nog niet bestaat OF None is
    if not wed.get("afgemeld_door"):
        wed["afgemeld_door"] = []
    
    # Check of deze scheidsrechter al in de lijst staat
    bestaande_nbbs = [a.get("nbb") if isinstance(a, dict) else a for a in wed["afgemeld_door"]]
    if nbb_nummer in bestaande_nbbs:
        return True  # Al geregistreerd
    
    # Voeg afmelding toe met timestamp en positie
    afmelding = {
        "nbb": nbb_nummer,
        "positie": positie,
        "afgemeld_op": datetime.now().isoformat()
    }
    wed["afgemeld_door"].append(afmelding)
    
    return True

def is_eerder_afgemeld(wed_id: str, nbb_nummer: str, wedstrijden: dict) -> bool:
    """
    Check of een scheidsrechter zich eerder heeft afgemeld voor deze wedstrijd.
    Gebruikt om te bepalen of bonus moet worden toegekend bij heraanmelding.
    
    Returns:
        True als scheidsrechter zich eerder heeft afgemeld
    """
    if wed_id not in wedstrijden:
        return False
    
    wed = wedstrijden[wed_id]
    afgemeld_door = wed.get("afgemeld_door") or []
    afgemelde_nbbs = [a.get("nbb") if isinstance(a, dict) else a for a in afgemeld_door]
    
    return nbb_nummer in afgemelde_nbbs

def verwijder_afmelding(wed_id: str, nbb_nummer: str, wedstrijden: dict) -> bool:
    """
    Verwijder een afmelding wanneer iemand zich heraanmeldt.
    Wordt aangeroepen wanneer TC of de speler zelf zich heraanmeldt.
    
    Returns:
        True bij succes
    """
    if wed_id not in wedstrijden:
        return False
    
    wed = wedstrijden[wed_id]
    afgemeld_door = wed.get("afgemeld_door") or []
    
    # Filter de afmelding van deze scheidsrechter eruit
    wed["afgemeld_door"] = [
        a for a in afgemeld_door 
        if (a.get("nbb") if isinstance(a, dict) else a) != nbb_nummer
    ]
    
    return True

def get_afmeldingen_voor_wedstrijd(wed_id: str, wedstrijden: dict, scheidsrechters: dict) -> list:
    """
    Haal lijst van afmeldingen op voor een wedstrijd, met namen.
    Voor TC weergave.
    
    Returns:
        Lijst van dicts met nbb, naam, positie, afgemeld_op
    """
    if wed_id not in wedstrijden:
        return []
    
    wed = wedstrijden[wed_id]
    afgemeld_door = wed.get("afgemeld_door") or []  # Fix: None wordt ook []
    
    resultaat = []
    for afmelding in afgemeld_door:
        if isinstance(afmelding, dict):
            nbb = afmelding.get("nbb")
            positie = afmelding.get("positie", "onbekend")
            afgemeld_op = afmelding.get("afgemeld_op", "")
        else:
            nbb = afmelding
            positie = "onbekend"
            afgemeld_op = ""
        
        naam = scheidsrechters.get(nbb, {}).get("naam", f"NBB {nbb}")
        resultaat.append({
            "nbb": nbb,
            "naam": naam,
            "positie": positie,
            "afgemeld_op": afgemeld_op
        })
    
    return resultaat

def schrijf_in_als_scheids(nbb_nummer: str, wed_id: str, positie: str, wedstrijden: dict, scheidsrechters: dict, bron: str = "zelf") -> dict:
    """
    Schrijf een scheidsrechter in voor een wedstrijd.
    
    Args:
        nbb_nummer: NBB nummer van de scheidsrechter
        wed_id: ID van de wedstrijd
        positie: "scheids_1" of "scheids_2"
        wedstrijden: Dict van alle wedstrijden
        scheidsrechters: Dict van alle scheidsrechters
        bron: Hoe de inschrijving tot stand kwam:
              - "zelf": Speler schreef zichzelf in (geen last-minute bonus)
              - "vervanging": Via vervangingsverzoek van afmelder
              - "tc": Handmatig toegewezen door TC
              - "uitnodiging": Via MSE begeleidingsuitnodiging
              - "heraanmelding": Speler die zich eerder had afgemeld meldt zich opnieuw aan
    
    Returns:
        dict met punten_info bij succes, {"error": "bezet", ...} bij race condition
    
    De punten worden BEREKEND en OPGESLAGEN bij de wedstrijd, maar NIET toegekend aan de speler.
    Punten worden pas toegekend wanneer de TC de wedstrijd bevestigt als "gefloten".
    
    BELANGRIJK: Bij heraanmelding (speler had zich eerder afgemeld) wordt GEEN bonus gegeven.
    """
    # KRITIEKE FIX: Laad verse data uit database ZONDER CACHE om race conditions te voorkomen
    # Dit haalt de actuele staat direct uit Supabase, niet uit de sessie-cache
    verse_wed = db.laad_wedstrijd_vers(wed_id)
    
    if not verse_wed:
        return None  # Wedstrijd bestaat niet meer
    
    # Check of positie nog vrij is (met verse data uit database!)
    huidige_scheids = verse_wed.get(positie)
    if huidige_scheids is not None and huidige_scheids != nbb_nummer:
        # Positie is al bezet door iemand anders!
        # Retourneer info over wie er staat zodat UI dit kan tonen
        huidige_naam = scheidsrechters.get(huidige_scheids, {}).get("naam", f"NBB {huidige_scheids}")
        return {"error": "bezet", "huidige_scheids": huidige_scheids, "huidige_naam": huidige_naam}
    
    # NIEUW: Check of dit een heraanmelding is (speler had zich eerder afgemeld)
    # Gebruik verse_wed in een tijdelijke dict voor de is_eerder_afgemeld check
    temp_wedstrijden = {wed_id: verse_wed}
    was_eerder_afgemeld = is_eerder_afgemeld(wed_id, nbb_nummer, temp_wedstrijden)
    
    # Bij heraanmelding: gebruik bron "heraanmelding" om geen bonus te geven
    effectieve_bron = "heraanmelding" if was_eerder_afgemeld else bron
    
    # Positie is vrij of al van deze speler - ga door met inschrijving
    # Gebruik verse data voor punten berekening
    punten_info = bereken_punten_voor_wedstrijd(nbb_nummer, wed_id, temp_wedstrijden, scheidsrechters, effectieve_bron)
    
    # Markeer in de punten_info dat dit een heraanmelding is
    if was_eerder_afgemeld:
        punten_info["is_heraanmelding"] = True
        punten_info["berekening"]["is_heraanmelding"] = True
        punten_info["berekening"]["heraanmelding_info"] = "Geen bonus bij heraanmelding na eerdere afmelding"
    
    # Bepaal punten kolom naam
    punten_kolom = "scheids_1_punten_berekend" if positie == "scheids_1" else "scheids_2_punten_berekend"
    details_kolom = "scheids_1_punten_details" if positie == "scheids_1" else "scheids_2_punten_details"
    
    # Update verse wedstrijd data met scheidsrechter EN berekende punten
    verse_wed[positie] = nbb_nummer
    verse_wed[punten_kolom] = punten_info["totaal"]
    verse_wed[details_kolom] = punten_info  # Volledige details voor transparantie
    
    # Bij heraanmelding: verwijder uit afgemeld_door lijst (zodat pool-berekening weer klopt)
    # Maar behoud de afmelding info voor TC logging (in een apart veld)
    if was_eerder_afgemeld:
        # Bewaar info over heraanmelding voor logging
        if not verse_wed.get("heraanmeldingen"):
            verse_wed["heraanmeldingen"] = []
        verse_wed["heraanmeldingen"].append({
            "nbb": nbb_nummer,
            "positie": positie,
            "heraangemeld_op": datetime.now().isoformat()
        })
        # Verwijder uit afgemeld_door
        afgemeld_door = verse_wed.get("afgemeld_door") or []
        verse_wed["afgemeld_door"] = [
            a for a in afgemeld_door 
            if (a.get("nbb") if isinstance(a, dict) else a) != nbb_nummer
        ]
    
    # Sla op naar database
    sla_wedstrijd_op(wed_id, verse_wed)
    
    # Update ook de lokale cache zodat UI correct is
    wedstrijden[wed_id] = verse_wed
    
    # Log de inschrijving voor gedragsanalyse
    try:
        wed_datum = datetime.strptime(verse_wed["datum"], "%Y-%m-%d %H:%M")
        actie = "heraanmelden" if was_eerder_afgemeld else "inschrijven"
        db.log_registratie(nbb_nummer, wed_id, positie, actie, wed_datum)
    except:
        pass  # Logging failure mag inschrijving niet blokkeren
    
    return punten_info

def bevestig_wedstrijd_gefloten(wed_id: str, positie: str, bevestigd_door: str) -> bool:
    """
    Bevestig dat een scheidsrechter de wedstrijd heeft gefloten.
    Kent de opgeslagen punten toe aan de speler.
    
    Args:
        wed_id: ID van de wedstrijd
        positie: "scheids_1" of "scheids_2"
        bevestigd_door: Naam/ID van TC-lid die bevestigt
    
    Returns:
        True bij succes, False bij fout
    """
    wedstrijden = laad_wedstrijden()
    wed = wedstrijden.get(wed_id)
    
    if not wed:
        return False
    
    # Bepaal kolom namen
    scheids_kolom = positie
    status_kolom = f"{positie}_status"
    bevestigd_op_kolom = f"{positie}_bevestigd_op"
    bevestigd_door_kolom = f"{positie}_bevestigd_door"
    punten_kolom = f"{positie}_punten_berekend"
    details_kolom = f"{positie}_punten_details"
    
    nbb_nummer = wed.get(scheids_kolom)
    if not nbb_nummer:
        return False
    
    # Haal opgeslagen punten op
    punten = wed.get(punten_kolom, 0)
    punten_details = wed.get(details_kolom, {})
    
    # Update status
    wed[status_kolom] = "gefloten"
    wed[bevestigd_op_kolom] = datetime.now().isoformat()
    wed[bevestigd_door_kolom] = bevestigd_door
    
    # Sla wedstrijd update op
    sla_wedstrijden_op(wedstrijden)
    
    # Ken punten toe aan speler
    if punten and punten > 0:
        reden = punten_details.get("details", f"Wedstrijd {wed.get('thuisteam')} vs {wed.get('uitteam')}")
        voeg_punten_toe(nbb_nummer, punten, reden, wed_id, punten_details.get("berekening"))
    
    return True

def markeer_no_show(wed_id: str, positie: str, bevestigd_door: str) -> bool:
    """
    Markeer een scheidsrechter als no-show.
    Kent no-show strikes toe.
    
    Args:
        wed_id: ID van de wedstrijd
        positie: "scheids_1" of "scheids_2"
        bevestigd_door: Naam/ID van TC-lid die markeert
    
    Returns:
        True bij succes, False bij fout
    """
    wedstrijden = laad_wedstrijden()
    wed = wedstrijden.get(wed_id)
    
    if not wed:
        return False
    
    # Bepaal kolom namen
    scheids_kolom = positie
    status_kolom = f"{positie}_status"
    bevestigd_op_kolom = f"{positie}_bevestigd_op"
    bevestigd_door_kolom = f"{positie}_bevestigd_door"
    
    nbb_nummer = wed.get(scheids_kolom)
    if not nbb_nummer:
        return False
    
    # Update status
    wed[status_kolom] = "no_show"
    wed[bevestigd_op_kolom] = datetime.now().isoformat()
    wed[bevestigd_door_kolom] = bevestigd_door
    
    # Sla wedstrijd update op
    sla_wedstrijden_op(wedstrijden)
    
    # Ken no-show strikes toe
    beloningsinst = laad_beloningsinstellingen()
    strikes = beloningsinst.get("strikes_no_show", 5)
    reden = f"No-show: {wed.get('thuisteam')} vs {wed.get('uitteam')}"
    voeg_strike_toe(nbb_nummer, strikes, reden)
    
    return True

def markeer_no_show_met_invaller(wed_id: str, positie: str, invaller_nbb: str, bevestigd_door: str) -> dict:
    """
    Markeer een scheidsrechter als no-show en registreer een invaller.
    De oorspronkelijke scheids krijgt strikes, de invaller krijgt punten.
    
    Args:
        wed_id: ID van de wedstrijd
        positie: "scheids_1" of "scheids_2"
        invaller_nbb: NBB nummer van de invaller
        bevestigd_door: Naam/ID van TC-lid die markeert
    
    Returns:
        dict met resultaat info of None bij fout
    """
    wedstrijden = laad_wedstrijden()
    scheidsrechters = laad_scheidsrechters()
    wed = wedstrijden.get(wed_id)
    
    if not wed:
        return None
    
    # Bepaal kolom namen
    scheids_kolom = positie
    status_kolom = f"{positie}_status"
    bevestigd_op_kolom = f"{positie}_bevestigd_op"
    bevestigd_door_kolom = f"{positie}_bevestigd_door"
    punten_kolom = f"{positie}_punten_berekend"
    details_kolom = f"{positie}_punten_details"
    
    oorspronkelijke_nbb = wed.get(scheids_kolom)
    if not oorspronkelijke_nbb:
        return None
    
    oorspronkelijke_naam = scheidsrechters.get(oorspronkelijke_nbb, {}).get("naam", "Onbekend")
    invaller_naam = scheidsrechters.get(invaller_nbb, {}).get("naam", "Onbekend")
    
    # Bereken punten voor invaller (met inval bonus - wedstrijd is al geweest dus altijd <24u)
    beloningsinst = laad_beloningsinstellingen()
    
    # Basis punten + inval bonus (wedstrijd is al gespeeld, dus maximale bonus)
    basis_punten = beloningsinst.get("punten_per_wedstrijd", 1)
    inval_bonus = beloningsinst.get("punten_inval_24u", 5)  # Maximale bonus want last-minute
    
    # Check lastig tijdstip voor invaller
    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    lastig_bonus = beloningsinst.get("punten_lastig_tijdstip", 1) if is_lastig_tijdstip(invaller_nbb, wed_datum, wedstrijden, scheidsrechters) else 0
    
    totaal_punten = basis_punten + inval_bonus + lastig_bonus
    
    punten_details = {
        "basis": basis_punten,
        "lastig_tijdstip": lastig_bonus,
        "inval_bonus": inval_bonus,
        "pool_bonus": 0,  # Niet van toepassing bij no-show vervanging (wedstrijd al gespeeld)
        "totaal": totaal_punten,
        "details": f"{basis_punten} basis, +{inval_bonus} inval (no-show vervanging)" + (f", +{lastig_bonus} lastig tijdstip" if lastig_bonus else ""),
        "berekening": {
            "type": "no_show_vervanging",
            "oorspronkelijke_scheids": oorspronkelijke_nbb,
            "bevestigd_op": datetime.now().isoformat()
        }
    }
    
    # Update wedstrijd: nieuwe scheids, status gefloten
    wed[scheids_kolom] = invaller_nbb
    wed[status_kolom] = "gefloten"
    wed[bevestigd_op_kolom] = datetime.now().isoformat()
    wed[bevestigd_door_kolom] = bevestigd_door
    wed[punten_kolom] = totaal_punten
    wed[details_kolom] = punten_details
    
    # Sla wedstrijd update op
    sla_wedstrijden_op(wedstrijden)
    
    # Ken no-show strikes toe aan oorspronkelijke scheids
    strikes = beloningsinst.get("strikes_no_show", 5)
    strike_reden = f"No-show (vervangen door {invaller_naam}): {wed.get('thuisteam')} vs {wed.get('uitteam')}"
    voeg_strike_toe(oorspronkelijke_nbb, strikes, strike_reden)
    
    # Ken punten toe aan invaller
    punten_reden = f"Inval voor no-show ({oorspronkelijke_naam}): {wed.get('thuisteam')} vs {wed.get('uitteam')}"
    voeg_punten_toe(invaller_nbb, totaal_punten, punten_reden, wed_id, punten_details.get("berekening"))
    
    return {
        "oorspronkelijke_scheids": oorspronkelijke_naam,
        "oorspronkelijke_nbb": oorspronkelijke_nbb,
        "strikes": strikes,
        "invaller": invaller_naam,
        "invaller_nbb": invaller_nbb,
        "punten": totaal_punten,
        "punten_details": punten_details["details"]
    }

def get_te_bevestigen_wedstrijden() -> list:
    """
    Haal wedstrijden op die in het verleden liggen en nog niet volledig bevestigd zijn.
    
    Returns:
        Lijst van wedstrijden met openstaande bevestigingen
    """
    wedstrijden = laad_wedstrijden()
    scheidsrechters = laad_scheidsrechters()
    nu = datetime.now()
    
    te_bevestigen = []
    
    for wed_id, wed in wedstrijden.items():
        if wed.get("geannuleerd", False):
            continue
        
        # Parse datum
        try:
            wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        except:
            continue
        
        # Alleen wedstrijden in het verleden
        if wed_datum > nu:
            continue
        
        # Check scheids_1
        scheids_1 = wed.get("scheids_1")
        scheids_1_status = wed.get("scheids_1_status")
        
        # Check scheids_2
        scheids_2 = wed.get("scheids_2")
        scheids_2_status = wed.get("scheids_2_status")
        
        # Heeft deze wedstrijd openstaande bevestigingen?
        scheids_1_open = scheids_1 and not scheids_1_status
        scheids_2_open = scheids_2 and not scheids_2_status
        
        if scheids_1_open or scheids_2_open:
            te_bevestigen.append({
                "wed_id": wed_id,
                "datum": wed["datum"],
                "wed_datum": wed_datum,
                "thuisteam": wed.get("thuisteam", ""),
                "uitteam": wed.get("uitteam", ""),
                "niveau": wed.get("niveau", 1),
                "scheids_1": scheids_1,
                "scheids_1_naam": scheidsrechters.get(scheids_1, {}).get("naam", "Onbekend") if scheids_1 else None,
                "scheids_1_status": scheids_1_status,
                "scheids_1_punten": wed.get("scheids_1_punten_berekend", 0),
                "scheids_2": scheids_2,
                "scheids_2_naam": scheidsrechters.get(scheids_2, {}).get("naam", "Onbekend") if scheids_2 else None,
                "scheids_2_status": scheids_2_status,
                "scheids_2_punten": wed.get("scheids_2_punten_berekend", 0),
                "scheids_1_open": scheids_1_open,
                "scheids_2_open": scheids_2_open
            })
    
    # Sorteer op datum (oudste eerst)
    return sorted(te_bevestigen, key=lambda x: x["wed_datum"])

def get_ranglijst() -> list:
    """Haal ranglijst op (gesorteerd op punten, aflopend)."""
    beloningen = laad_beloningen()
    scheidsrechters = laad_scheidsrechters()
    
    ranglijst = []
    for nbb, data in beloningen.get("spelers", {}).items():
        scheids = scheidsrechters.get(nbb, {})
        ranglijst.append({
            "nbb_nummer": nbb,
            "naam": scheids.get("naam", "Onbekend"),
            "punten": data.get("punten", 0),
            "strikes": data.get("strikes", 0)
        })
    
    return sorted(ranglijst, key=lambda x: (-x["punten"], x["strikes"]))

# ============================================================
# HELPER FUNCTIES
# ============================================================

def is_inschrijving_open() -> bool:
    """Check of inschrijfperiode nog loopt (backwards compatible)."""
    instellingen = laad_instellingen()
    deadline = datetime.strptime(instellingen["inschrijf_deadline"], "%Y-%m-%d")
    return datetime.now() <= deadline

def is_inschrijving_open_voor_wedstrijd(wed_datum: datetime) -> bool:
    """
    Check of inschrijving open is voor een specifieke wedstrijd.
    De deadline sluit alleen de maand waar de deadline voor geldt.
    Wedstrijden in latere maanden blijven open voor inschrijving.
    
    Voorbeeld: Deadline 15 januari
    - Wedstrijd 20 januari → DICHT (zelfde maand)
    - Wedstrijd 5 februari → OPEN (latere maand)
    """
    instellingen = laad_instellingen()
    deadline = datetime.strptime(instellingen["inschrijf_deadline"], "%Y-%m-%d")
    nu = datetime.now()
    
    # Bepaal de maand waar de deadline betrekking op heeft
    # Als deadline <= 15e van de maand → geldt voor die maand
    # Als deadline > 15e van de maand → geldt voor volgende maand
    if deadline.day <= 15:
        deadline_maand = deadline.month
        deadline_jaar = deadline.year
    else:
        if deadline.month == 12:
            deadline_maand = 1
            deadline_jaar = deadline.year + 1
        else:
            deadline_maand = deadline.month + 1
            deadline_jaar = deadline.year
    
    # Wedstrijd maand en jaar
    wed_maand = wed_datum.month
    wed_jaar = wed_datum.year
    
    # Als we nog voor de deadline zijn, is alles open
    if nu <= deadline:
        return True
    
    # Na de deadline: check of wedstrijd in de afgesloten maand valt
    # De afgesloten maand is de deadline_maand/deadline_jaar
    if wed_jaar == deadline_jaar and wed_maand == deadline_maand:
        # Wedstrijd valt in de afgesloten maand
        return False
    elif wed_jaar < deadline_jaar or (wed_jaar == deadline_jaar and wed_maand < deadline_maand):
        # Wedstrijd is in het verleden (voor de afgesloten maand)
        return False
    else:
        # Wedstrijd is in een latere maand - open voor inschrijving
        return True

def get_deadline_maand_info() -> dict:
    """
    Haal informatie op over de huidige deadline en welke maand afgesloten is.
    Returns: {"deadline": datetime, "gesloten_maand": int, "gesloten_jaar": int, "is_verlopen": bool}
    """
    instellingen = laad_instellingen()
    deadline = datetime.strptime(instellingen["inschrijf_deadline"], "%Y-%m-%d")
    nu = datetime.now()
    
    if deadline.day <= 15:
        gesloten_maand = deadline.month
        gesloten_jaar = deadline.year
    else:
        if deadline.month == 12:
            gesloten_maand = 1
            gesloten_jaar = deadline.year + 1
        else:
            gesloten_maand = deadline.month + 1
            gesloten_jaar = deadline.year
    
    return {
        "deadline": deadline,
        "gesloten_maand": gesloten_maand,
        "gesloten_jaar": gesloten_jaar,
        "is_verlopen": nu > deadline
    }

def is_aankomend_weekend(wed_datum: datetime) -> bool:
    """
    Check of een wedstrijd in het aankomend weekend valt.
    Aankomend weekend = wedstrijden die:
    - Op zaterdag of zondag vallen
    - Nog niet gespeeld zijn (in de toekomst liggen)
    - Binnen 7 dagen vallen
    """
    nu = datetime.now()
    wed_date = wed_datum.date()
    vandaag = nu.date()
    
    # Moet in de toekomst zijn (of vandaag)
    if wed_date < vandaag:
        return False
    
    # Moet op zaterdag (5) of zondag (6) vallen
    if wed_datum.weekday() not in [5, 6]:
        return False
    
    # Moet binnen 7 dagen zijn
    dagen_vooruit = (wed_date - vandaag).days
    return dagen_vooruit <= 7

def is_inschrijving_open_incl_weekend(wed_datum: datetime, wed: dict):
    """
    Check of inschrijving open is, inclusief uitzondering voor aankomend weekend.
    
    Returns: (is_open, is_weekend_uitzondering)
    - is_open: True als speler zich mag inschrijven
    - is_weekend_uitzondering: True als dit via de weekend-uitzondering is (geen bonus)
    """
    # Eerst normale deadline check
    if is_inschrijving_open_voor_wedstrijd(wed_datum):
        return (True, False)
    
    # Deadline is voorbij - check weekend uitzondering
    # Alleen als wedstrijd in aankomend weekend EN er nog een open positie is
    if is_aankomend_weekend(wed_datum):
        heeft_open_positie = not wed.get("scheids_1") or not wed.get("scheids_2")
        if heeft_open_positie:
            return (True, True)  # Open via weekend-uitzondering (geen bonus)
    
    return (False, False)

def heeft_eigen_wedstrijd(nbb_nummer: str, datum_tijd: datetime, wedstrijden: dict, scheidsrechters: dict) -> bool:
    """
    Check of scheidsrechter op dit tijdstip een eigen wedstrijd heeft.
    Houdt rekening met reistijd bij uitwedstrijden.
    """
    scheids = scheidsrechters.get(nbb_nummer, {})
    eigen_teams = scheids.get("eigen_teams", [])
    
    if not eigen_teams:
        return False
    
    for wed_id, wed in wedstrijden.items():
        # Check of dit een wedstrijd is van een eigen team (flexibele matching)
        is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams)
        is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams)
        
        is_eigen_wed = False
        if wed.get("type") == "uit":
            # Bij uitwedstrijd: thuisteam is het eigen team dat uit speelt
            if is_eigen_thuis:
                is_eigen_wed = True
        else:
            # Bij thuiswedstrijd: check beide teams
            if is_eigen_thuis or is_eigen_uit:
                is_eigen_wed = True
        
        if not is_eigen_wed:
            continue
        
        # Bereken tijdsvenster van deze wedstrijd
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        
        # Wedstrijd duurt ongeveer 1,5 uur
        wed_duur = timedelta(hours=1, minutes=30)
        
        # Bij uitwedstrijden: reistijd ervoor en erna
        if wed.get("type") == "uit":
            reistijd = timedelta(minutes=wed.get("reistijd_minuten", 60))
            wed_start = wed_datum - reistijd
            wed_eind = wed_datum + wed_duur + reistijd
        else:
            # Thuiswedstrijd: 30 min ervoor aanwezig
            wed_start = wed_datum - timedelta(minutes=30)
            wed_eind = wed_datum + wed_duur
        
        # Check overlap: kan niet fluiten als eigen wedstrijd overlapt
        # Fluitwedstrijd duurt ook ~1,5 uur, moet 30 min van tevoren aanwezig zijn
        fluit_start = datum_tijd - timedelta(minutes=30)
        fluit_eind = datum_tijd + wed_duur
        
        # Overlap als: fluit_start < wed_eind AND fluit_eind > wed_start
        if fluit_start < wed_eind and fluit_eind > wed_start:
            return True
    
    return False

def heeft_overlappende_fluitwedstrijd(nbb_nummer: str, huidige_wed_id: str, datum_tijd: datetime, wedstrijden: dict) -> bool:
    """
    Check of scheidsrechter al is ingeschreven voor een andere wedstrijd die overlapt.
    Wedstrijden duren ~1,5 uur, scheidsrechter moet 30 min van tevoren aanwezig zijn.
    """
    wed_duur = timedelta(hours=1, minutes=30)
    aanwezig_voor = timedelta(minutes=30)
    
    # Tijdsvenster van de wedstrijd waar we naar kijken
    nieuwe_start = datum_tijd - aanwezig_voor
    nieuwe_eind = datum_tijd + wed_duur
    
    for wed_id, wed in wedstrijden.items():
        # Skip de huidige wedstrijd
        if wed_id == huidige_wed_id:
            continue
        
        # Check of speler is ingeschreven voor deze wedstrijd
        if wed.get("scheids_1") != nbb_nummer and wed.get("scheids_2") != nbb_nummer:
            continue
        
        # Bereken tijdsvenster van de bestaande wedstrijd
        bestaande_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        bestaande_start = bestaande_datum - aanwezig_voor
        bestaande_eind = bestaande_datum + wed_duur
        
        # Check overlap
        if nieuwe_start < bestaande_eind and nieuwe_eind > bestaande_start:
            return True
    
    return False

def is_beschikbaar_voor_begeleiding(nbb_nummer: str, wed_id: str, wedstrijden: dict, scheidsrechters: dict) -> tuple[bool, str]:
    """
    Check of een speler beschikbaar is om als 2e scheids mee te fluiten bij een wedstrijd.
    
    Returns: (beschikbaar: bool, reden: str)
    """
    scheids = scheidsrechters.get(nbb_nummer, {})
    wed = wedstrijden.get(wed_id, {})
    
    if not wed:
        return False, "Wedstrijd niet gevonden"
    
    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    
    # Check: niet op zondag
    if scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6:
        return False, "Niet beschikbaar op zondag"
    
    # Check: eigen wedstrijd
    if heeft_eigen_wedstrijd(nbb_nummer, wed_datum, wedstrijden, scheidsrechters):
        return False, "Heeft eigen wedstrijd"
    
    # Check: al ingeschreven voor andere wedstrijd
    if heeft_overlappende_fluitwedstrijd(nbb_nummer, wed_id, wed_datum, wedstrijden):
        return False, "Fluit al andere wedstrijd"
    
    # Check: al ingeschreven voor deze wedstrijd
    if wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer:
        return False, "Al ingeschreven voor deze wedstrijd"
    
    return True, "Beschikbaar"

def analyseer_scheids_conflicten(nbb_nummer: str, wed_id: str, nieuwe_datum_tijd: datetime, 
                                   wedstrijden: dict, scheidsrechters: dict) -> list:
    """
    Analyseer mogelijke conflicten voor een scheidsrechter bij een nieuwe datum/tijd.
    
    Returns: Lijst van conflict beschrijvingen
    """
    conflicten = []
    scheids = scheidsrechters.get(nbb_nummer, {})
    eigen_teams = scheids.get("eigen_teams", [])
    
    wed_duur = timedelta(hours=1, minutes=30)
    aanwezig_voor = timedelta(minutes=30)
    
    # Tijdsvenster van de nieuwe tijd
    nieuwe_start = nieuwe_datum_tijd - aanwezig_voor
    nieuwe_eind = nieuwe_datum_tijd + wed_duur
    
    # Check zondag restrictie
    if scheids.get("niet_op_zondag", False) and nieuwe_datum_tijd.weekday() == 6:
        conflicten.append({
            "type": "zondag",
            "beschrijving": f"{scheids.get('naam', 'Onbekend')} kan niet op zondag fluiten"
        })
    
    # Check eigen wedstrijden
    for other_wed_id, wed in wedstrijden.items():
        if other_wed_id == wed_id:
            continue
            
        # Skip geannuleerde wedstrijden
        if wed.get("geannuleerd", False):
            continue
        
        # Check of dit een eigen wedstrijd is
        is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams)
        is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams)
        
        is_eigen_wed = False
        if wed.get("type") == "uit":
            if is_eigen_thuis:
                is_eigen_wed = True
        else:
            if is_eigen_thuis or is_eigen_uit:
                is_eigen_wed = True
        
        if is_eigen_wed:
            # Bereken tijdsvenster van deze wedstrijd
            wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
            
            if wed.get("type") == "uit":
                reistijd = timedelta(minutes=wed.get("reistijd_minuten", 60))
                wed_start = wed_datum - reistijd
                wed_eind = wed_datum + wed_duur + reistijd
            else:
                wed_start = wed_datum - timedelta(minutes=30)
                wed_eind = wed_datum + wed_duur
            
            # Check overlap
            if nieuwe_start < wed_eind and nieuwe_eind > wed_start:
                dag = ["ma", "di", "wo", "do", "vr", "za", "zo"][wed_datum.weekday()]
                conflicten.append({
                    "type": "eigen_wedstrijd",
                    "beschrijving": f"{scheids.get('naam', 'Onbekend')} speelt zelf: {wed['thuisteam']} - {wed['uitteam']} ({dag} {wed_datum.strftime('%H:%M')})"
                })
        
        # Check andere fluitwedstrijden
        elif wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer:
            wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
            bestaande_start = wed_datum - aanwezig_voor
            bestaande_eind = wed_datum + wed_duur
            
            if nieuwe_start < bestaande_eind and nieuwe_eind > bestaande_start:
                dag = ["ma", "di", "wo", "do", "vr", "za", "zo"][wed_datum.weekday()]
                positie = "1e" if wed.get("scheids_1") == nbb_nummer else "2e"
                conflicten.append({
                    "type": "andere_fluitwedstrijd",
                    "beschrijving": f"{scheids.get('naam', 'Onbekend')} fluit al ({positie}): {wed['thuisteam']} - {wed['uitteam']} ({dag} {wed_datum.strftime('%H:%M')})"
                })
    
    return conflicten

def bepaal_scheids_status(nbb_nummer: str, wed: dict, scheids: dict, wedstrijden: dict, scheidsrechters: dict, als_eerste: bool) -> dict:
    """
    Bepaal de status van een scheidsrechter positie voor een wedstrijd.
    
    Returns dict met:
    - ingeschreven_zelf: bool - deze speler is zelf ingeschreven
    - bezet: bool - iemand anders is ingeschreven
    - naam: str - naam van ingeschreven persoon (indien bezet)
    - beschikbaar: bool - positie is open en speler mag zich inschrijven
    - reden: str - reden waarom niet beschikbaar (indien niet beschikbaar)
    """
    positie = "scheids_1" if als_eerste else "scheids_2"
    
    # Check of zelf ingeschreven
    if wed.get(positie) == nbb_nummer:
        return {"ingeschreven_zelf": True, "bezet": False, "naam": "", "beschikbaar": False, "reden": ""}
    
    # Check of iemand anders ingeschreven
    if wed.get(positie):
        andere_nbb = wed.get(positie)
        andere_scheids = scheidsrechters.get(andere_nbb, {})
        naam = andere_scheids.get("naam", "Onbekend")
        wil_begeleiding = andere_scheids.get("open_voor_begeleiding", False)
        return {"ingeschreven_zelf": False, "bezet": True, "naam": naam, "beschikbaar": False, "reden": "", "nbb": andere_nbb, "wil_begeleiding": wil_begeleiding}
    
    # Positie is open - check of speler mag inschrijven
    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    
    # Check BS2 vereiste - dit geldt ALTIJD, ook voor 2e scheidsrechter
    if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
        return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": "BS2 vereist"}
    
    # Check niveau
    wed_niveau = wed["niveau"]
    
    if als_eerste:
        # 1e scheidsrechter: gewoon niveau check
        max_niveau = scheids.get("niveau_1e_scheids", 1)
        if wed_niveau > max_niveau:
            return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": f"niveau {wed_niveau} te hoog (max {max_niveau})"}
    else:
        # 2e scheidsrechter: complexere logica
        niveau_1e = scheids.get("niveau_1e_scheids", 1)
        
        # Check of er al een 1e scheids is en of die MSE is
        eerste_scheids_nbb = wed.get("scheids_1")
        if eerste_scheids_nbb:
            eerste_scheids = scheidsrechters.get(eerste_scheids_nbb, {})
            is_mse = eerste_scheids.get("niveau_1e_scheids", 1) == 5 or any("MSE" in t.upper() for t in eerste_scheids.get("eigen_teams", []))
            
            if is_mse:
                # MSE als 1e scheids: geen niveau-restrictie voor 2e scheids
                pass
            else:
                # Met 1e scheids (geen MSE): max 1 niveau hoger dan eigen niveau
                max_niveau_2e = min(niveau_1e + 1, 5)
                if wed_niveau > max_niveau_2e:
                    return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": f"niveau {wed_niveau} te hoog (max {max_niveau_2e})"}
        else:
            # Nog geen 1e scheids: zelfstandig max 1 niveau hoger
            max_niveau_2e = min(niveau_1e + 1, 5)
            if wed_niveau > max_niveau_2e:
                return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": f"niveau {wed_niveau} te hoog (max {max_niveau_2e} zonder 1e scheids)"}
    
    # Check eigen team
    eigen_teams = scheids.get("eigen_teams", [])
    is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams)
    is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams)
    if is_eigen_thuis or is_eigen_uit:
        return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": "eigen team"}
    
    # Check zondag
    if scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6:
        return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": "zondag"}
    
    # Check eigen wedstrijd overlap
    if heeft_eigen_wedstrijd(nbb_nummer, wed_datum, wedstrijden, scheidsrechters):
        return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": "speelt zelf"}
    
    # Check of niet al andere positie bij deze wedstrijd
    andere_positie = "scheids_2" if als_eerste else "scheids_1"
    if wed.get(andere_positie) == nbb_nummer:
        return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": "al 2e scheids" if als_eerste else "al 1e scheids"}
    
    # Check overlap met andere fluitwedstrijden
    overlap_wed = heeft_overlappende_fluitwedstrijd(nbb_nummer, wed.get("id", ""), wed_datum, wedstrijden)
    if overlap_wed:
        return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": "overlap andere wedstrijd"}
    
    # Alles ok - beschikbaar
    return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": True, "reden": ""}

def get_beschikbare_wedstrijden(nbb_nummer: str, als_eerste: bool) -> list:
    """
    Haal wedstrijden op waar deze scheidsrechter zich voor kan inschrijven.
    Filtert op niveau, eigen teams, zondag-restrictie, etc.
    Sorteert zodat wedstrijden van eigen niveau eerst komen.
    """
    scheidsrechters = laad_scheidsrechters()
    wedstrijden = laad_wedstrijden()
    inschrijvingen = laad_inschrijvingen()
    
    if nbb_nummer not in scheidsrechters:
        return []
    
    scheids = scheidsrechters[nbb_nummer]
    niveau_1e = scheids.get("niveau_1e_scheids", 1)
    # Voor 2e scheids: standaard max 1 niveau hoger dan eigen niveau
    max_niveau_2e = min(niveau_1e + 1, 5)
    
    beschikbaar = []
    for wed_id, wed in wedstrijden.items():
        # Alleen thuiswedstrijden tonen (uitwedstrijden zijn alleen voor blokkade)
        if wed.get("type") == "uit":
            continue
        
        # Check BS2 vereiste - dit geldt ALTIJD
        if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
            continue
        
        # Check niveau
        wed_niveau = wed["niveau"]
        
        if als_eerste:
            # 1e scheidsrechter: gewoon niveau check
            if wed_niveau > niveau_1e:
                continue
        else:
            # 2e scheidsrechter: complexere logica
            if wed_niveau > max_niveau_2e:
                # Check of er een MSE als 1e scheids is (dan geen limiet)
                eerste_scheids_nbb = wed.get("scheids_1")
                if eerste_scheids_nbb:
                    eerste_scheids = scheidsrechters.get(eerste_scheids_nbb, {})
                    is_mse = eerste_scheids.get("niveau_1e_scheids", 1) == 5 or any("MSE" in t.upper() for t in eerste_scheids.get("eigen_teams", []))
                    if not is_mse:
                        continue  # Te hoog, geen MSE
                else:
                    continue  # Te hoog, nog geen 1e scheids
        
        # Check eigen team (thuiswedstrijd van eigen team) - flexibele matching
        eigen_teams = scheids.get("eigen_teams", [])
        is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams)
        is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams)
        if is_eigen_thuis or is_eigen_uit:
            continue
        
        # Check zondag
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        if scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6:
            continue
        
        # Check of scheidsrechter op dit tijdstip een eigen wedstrijd heeft
        if heeft_eigen_wedstrijd(nbb_nummer, wed_datum, wedstrijden, scheidsrechters):
            continue
        
        # Check of al ingeschreven of toegewezen
        positie = "scheids_1" if als_eerste else "scheids_2"
        if wed.get(positie):
            continue
        
        beschikbaar.append({
            "id": wed_id,
            **wed
        })
    
    # Sorteer: eerst wedstrijden van eigen niveau (hoogste dat ze mogen), dan aflopend niveau, dan datum
    # Voorbeeld: scheids niveau 3 ziet eerst niveau 3, dan 2, dan 1
    return sorted(beschikbaar, key=lambda x: (
        0 if x["niveau"] == max_niveau else 1,  # Eigen niveau eerst
        -x["niveau"],  # Dan hoogste niveau eerst
        x["datum"]  # Dan op datum
    ))

def tel_wedstrijden_scheidsrechter(nbb_nummer: str, alleen_niveau: int = None) -> int:
    """
    Tel aantal wedstrijden waar scheidsrechter is ingeschreven/toegewezen.
    
    Args:
        nbb_nummer: NBB nummer van de scheidsrechter
        alleen_niveau: Indien opgegeven, tel alleen wedstrijden van exact dit niveau
    """
    wedstrijden = laad_wedstrijden()
    
    count = 0
    for wed_id, wed in wedstrijden.items():
        # Skip geannuleerde wedstrijden
        if wed.get("geannuleerd", False):
            continue
            
        if wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer:
            if alleen_niveau is not None:
                # Tel alleen wedstrijden van exact dit niveau
                if wed.get("niveau", 1) == alleen_niveau:
                    count += 1
            else:
                count += 1
    
    return count

def tel_open_posities_op_niveau(nbb_nummer: str, niveau: int) -> dict:
    """
    Tel hoeveel open scheidsrechterposities er zijn op een bepaald niveau
    waar deze scheidsrechter voor in aanmerking komt.
    
    Returns dict met:
    - totaal_open: aantal open posities (1e + 2e scheids)
    - als_1e_open: aantal open 1e scheidsrechter posities
    - als_2e_open: aantal open 2e scheidsrechter posities
    - wedstrijden: lijst met open wedstrijden
    """
    scheidsrechters = laad_scheidsrechters()
    wedstrijden = laad_wedstrijden()
    nu = datetime.now()
    
    if nbb_nummer not in scheidsrechters:
        return {"totaal_open": 0, "als_1e_open": 0, "als_2e_open": 0, "wedstrijden": []}
    
    scheids = scheidsrechters[nbb_nummer]
    eigen_teams = scheids.get("eigen_teams", [])
    
    als_1e_open = 0
    als_2e_open = 0
    open_wedstrijden = []
    
    for wed_id, wed in wedstrijden.items():
        # Alleen thuiswedstrijden op het gevraagde niveau
        if wed.get("type", "thuis") != "thuis":
            continue
        if wed.get("geannuleerd", False):
            continue
        if wed.get("niveau", 1) != niveau:
            continue
        
        # Alleen toekomstige wedstrijden
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        if wed_datum <= nu:
            continue
        
        # Skip als dit eigen team is
        is_eigen_team = False
        if eigen_teams:
            is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams)
            is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams)
            is_eigen_team = is_eigen_thuis or is_eigen_uit
        
        if is_eigen_team:
            continue
        
        # Check of al ingeschreven voor deze wedstrijd
        if wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer:
            continue
        
        # Tel open posities
        wed_info = {
            "id": wed_id,
            "datum": wed["datum"],
            "teams": f"{wed['thuisteam']} - {wed['uitteam']}"
        }
        
        if not wed.get("scheids_1"):
            als_1e_open += 1
            wed_info["positie_1e_open"] = True
        if not wed.get("scheids_2"):
            als_2e_open += 1
            wed_info["positie_2e_open"] = True
        
        if not wed.get("scheids_1") or not wed.get("scheids_2"):
            open_wedstrijden.append(wed_info)
    
    return {
        "totaal_open": als_1e_open + als_2e_open,
        "als_1e_open": als_1e_open,
        "als_2e_open": als_2e_open,
        "wedstrijden": open_wedstrijden
    }

def tel_wedstrijden_op_eigen_niveau(nbb_nummer: str) -> dict:
    """
    Tel wedstrijden op eigen niveau of hoger voor minimum check.
    
    Returns dict met:
    - totaal: totaal aantal wedstrijden
    - op_niveau: aantal wedstrijden op eigen niveau OF HOGER (stimuleert ontwikkeling)
    - niveau: het eigen niveau van de scheidsrechter
    - min_wedstrijden: minimum aantal dat op eigen niveau moet
    - voldaan: of aan minimum is voldaan
    """
    scheidsrechters = laad_scheidsrechters()
    wedstrijden = laad_wedstrijden()
    
    if nbb_nummer not in scheidsrechters:
        return {"totaal": 0, "op_niveau": 0, "niveau": 1, "min_wedstrijden": 0, "voldaan": True}
    
    scheids = scheidsrechters[nbb_nummer]
    eigen_niveau = scheids.get("niveau_1e_scheids", 1)
    min_wed = scheids.get("min_wedstrijden", 0)
    
    totaal = 0
    op_niveau = 0
    
    for wed_id, wed in wedstrijden.items():
        # Skip geannuleerde wedstrijden
        if wed.get("geannuleerd", False):
            continue
            
        if wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer:
            totaal += 1
            # Tel als "op niveau" als wedstrijd niveau >= eigen niveau (hoger niveau telt ook!)
            if wed.get("niveau", 1) >= eigen_niveau:
                op_niveau += 1
    
    return {
        "totaal": totaal,
        "op_niveau": op_niveau,
        "niveau": eigen_niveau,
        "min_wedstrijden": min_wed,
        "voldaan": op_niveau >= min_wed
    }

def get_kandidaten_voor_wedstrijd(wed_id: str, als_eerste: bool) -> list:
    """Haal geschikte kandidaten op voor een wedstrijd (voor beheerder)."""
    scheidsrechters = laad_scheidsrechters()
    wedstrijden = laad_wedstrijden()
    
    if wed_id not in wedstrijden:
        return []
    
    wed = wedstrijden[wed_id]
    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    wed_niveau = wed.get("niveau", 1)
    
    # NIEUW: Haal lijst van afgemelde scheidsrechters op
    afgemeld_door = wed.get("afgemeld_door") or []
    afgemelde_nbbs = [a.get("nbb") if isinstance(a, dict) else a for a in afgemeld_door]
    
    kandidaten = []
    for nbb, scheids in scheidsrechters.items():
        niveau_1e = scheids.get("niveau_1e_scheids", 1)
        # Voor 2e scheids: standaard max 1 niveau hoger dan eigen niveau
        max_niveau_2e = min(niveau_1e + 1, 5)
        
        # Check BS2 vereiste - dit geldt ALTIJD, ook voor 2e scheidsrechter
        if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
            continue
        
        # Check niveau
        wed_niveau = wed["niveau"]
        
        if als_eerste:
            # 1e scheidsrechter: gewoon niveau check
            if wed_niveau > niveau_1e:
                continue
        else:
            # 2e scheidsrechter: complexere logica
            if wed_niveau > max_niveau_2e:
                # Check of er een MSE als 1e scheids is (dan geen limiet)
                eerste_scheids_nbb = wed.get("scheids_1")
                if eerste_scheids_nbb:
                    eerste_scheids = scheidsrechters.get(eerste_scheids_nbb, {})
                    is_mse = eerste_scheids.get("niveau_1e_scheids", 1) == 5 or any("MSE" in t.upper() for t in eerste_scheids.get("eigen_teams", []))
                    if not is_mse:
                        continue  # Te hoog, geen MSE
                else:
                    continue  # Te hoog, nog geen 1e scheids
        
        # Check eigen team (thuiswedstrijd van eigen team) - flexibele matching
        eigen_teams_scheids = scheids.get("eigen_teams", [])
        is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams_scheids)
        is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams_scheids)
        if is_eigen_thuis or is_eigen_uit:
            continue
        
        # Check zondag
        if scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6:
            continue
        
        # Check blessure status
        geblesseerd_tm = scheids.get("geblesseerd_tm", "")
        if geblesseerd_tm:
            # Parse de blessure maand (bijv. "januari 2025")
            try:
                maand_namen = ["januari", "februari", "maart", "april", "mei", "juni", 
                              "juli", "augustus", "september", "oktober", "november", "december"]
                delen = geblesseerd_tm.split()
                if len(delen) == 2:
                    maand_naam, jaar = delen[0].lower(), int(delen[1])
                    if maand_naam in maand_namen:
                        blessure_maand = maand_namen.index(maand_naam) + 1
                        # Wedstrijd valt in of voor de blessure maand?
                        if (wed_datum.year < jaar or 
                            (wed_datum.year == jaar and wed_datum.month <= blessure_maand)):
                            continue  # Geblesseerd, niet beschikbaar
            except:
                pass  # Bij parse fout gewoon doorgaan
        
        # Check geblokkeerde dagen (speler heeft zelf aangegeven niet beschikbaar te zijn)
        geblokkeerde_dagen = scheids.get("geblokkeerde_dagen", [])
        if geblokkeerde_dagen:
            wed_dag_str = wed_datum.strftime("%Y-%m-%d")
            if wed_dag_str in geblokkeerde_dagen:
                continue  # Speler heeft deze dag geblokkeerd
        
        # Check of scheidsrechter op dit tijdstip een eigen wedstrijd heeft
        if heeft_eigen_wedstrijd(nbb, wed_datum, wedstrijden, scheidsrechters):
            continue
        
        # Tel huidig aantal wedstrijden
        huidig_totaal = tel_wedstrijden_scheidsrechter(nbb)
        
        # Check of niet al andere positie bij deze wedstrijd
        andere_positie = "scheids_2" if als_eerste else "scheids_1"
        if wed.get(andere_positie) == nbb:
            continue
        
        # Check overlap met andere fluitwedstrijden
        if heeft_overlappende_fluitwedstrijd(nbb, wed_id, wed_datum, wedstrijden):
            continue
        
        # Bereken "urgentie" op basis van niveau
        # Tekort = hoeveel wedstrijden op eigen niveau nog nodig
        niveau_stats = tel_wedstrijden_op_eigen_niveau(nbb)
        min_wed = scheids.get("min_wedstrijden", 0)
        op_niveau = niveau_stats["op_niveau"]
        
        # Is deze wedstrijd op eigen niveau of hoger?
        is_op_eigen_niveau_of_hoger = wed_niveau >= niveau_1e
        
        # Tekort berekenen: relevant als wedstrijd op eigen niveau of hoger is
        if is_op_eigen_niveau_of_hoger:
            tekort = max(0, min_wed - op_niveau)
        else:
            tekort = 0  # Wedstrijd onder eigen niveau telt niet mee voor minimum
        
        kandidaten.append({
            "nbb_nummer": nbb,
            "naam": scheids["naam"],
            "huidig_aantal": huidig_totaal,
            "op_niveau": op_niveau,
            "eigen_niveau": niveau_1e,
            "min_wedstrijden": min_wed,
            "tekort": tekort,
            "is_op_eigen_niveau": is_op_eigen_niveau_of_hoger,
            "is_passief": huidig_totaal == 0,  # Nog nergens voor ingeschreven
            "is_eerder_afgemeld": nbb in afgemelde_nbbs  # NIEUW: Heeft zich eerder afgemeld
        })
    
    # Sorteer: 
    # 1. Passieve spelers eerst (nog nergens ingeschreven)
    # 2. Dan wie tekort heeft op eigen niveau
    # 3. Dan op minste wedstrijden (zodat actieven onderaan staan)
    return sorted(kandidaten, key=lambda x: (
        not x["is_passief"],  # False (passief) komt voor True (actief)
        -x["tekort"],         # Hoogste tekort eerst
        x["huidig_aantal"]    # Minste wedstrijden eerst
    ))

# ============================================================
# POOL-INDICATOR FUNCTIES
# ============================================================

def bereken_pool_voor_wedstrijd(wed_id: str, wedstrijden: dict, scheidsrechters: dict) -> int:
    """
    Bereken het aantal scheidsrechters dat beschikbaar is voor een wedstrijd.
    Houdt rekening met: niveau, BS2, eigen team, zondag, blessures, blokkades, tijdsoverlap, al ingeschreven.
    
    BELANGRIJK: Scheidsrechters die zich hebben afgemeld worden NIET meegeteld in de pool.
    Dit voorkomt dat de pool onterecht stijgt na een afmelding.
    """
    if wed_id not in wedstrijden:
        return 0
    
    wed = wedstrijden[wed_id]
    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    wed_niveau = wed.get("niveau", 1)
    
    # Haal lijst van afgemelde scheidsrechters op (die tellen niet mee in pool)
    afgemeld_door = wed.get("afgemeld_door") or []
    afgemelde_nbbs = [a.get("nbb") if isinstance(a, dict) else a for a in afgemeld_door]
    
    pool_count = 0
    for nbb, scheids in scheidsrechters.items():
        # Check of uitgesloten van pool (testgebruikers, reserves)
        if scheids.get("uitgesloten_van_pool", False):
            continue
        
        # Check of al toegewezen aan deze wedstrijd
        if wed.get("scheids_1") == nbb or wed.get("scheids_2") == nbb:
            continue
        
        # NIEUW: Check of deze scheidsrechter zich heeft afgemeld - die telt niet mee in pool
        if nbb in afgemelde_nbbs:
            continue
        
        niveau_1e = scheids.get("niveau_1e_scheids", 1)
        
        # Check BS2 vereiste
        if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
            continue
        
        # Check niveau (moet op of boven wedstrijdniveau kunnen fluiten)
        if wed_niveau > niveau_1e:
            continue
        
        # Check eigen team
        eigen_teams_scheids = scheids.get("eigen_teams", [])
        is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams_scheids)
        is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams_scheids)
        if is_eigen_thuis or is_eigen_uit:
            continue
        
        # Check zondag
        if scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6:
            continue
        
        # Check blessure status
        geblesseerd_tm = scheids.get("geblesseerd_tm", "")
        if geblesseerd_tm:
            try:
                maand_namen = ["januari", "februari", "maart", "april", "mei", "juni", 
                              "juli", "augustus", "september", "oktober", "november", "december"]
                delen = geblesseerd_tm.split()
                if len(delen) == 2:
                    maand_naam, jaar = delen[0].lower(), int(delen[1])
                    if maand_naam in maand_namen:
                        blessure_maand = maand_namen.index(maand_naam) + 1
                        if (wed_datum.year < jaar or 
                            (wed_datum.year == jaar and wed_datum.month <= blessure_maand)):
                            continue
            except:
                pass
        
        # Check geblokkeerde dagen
        geblokkeerde_dagen = scheids.get("geblokkeerde_dagen", [])
        if geblokkeerde_dagen:
            wed_dag_str = wed_datum.strftime("%Y-%m-%d")
            if wed_dag_str in geblokkeerde_dagen:
                continue
        
        # Check of scheidsrechter op dit tijdstip een eigen wedstrijd heeft
        if heeft_eigen_wedstrijd(nbb, wed_datum, wedstrijden, scheidsrechters):
            continue
        
        # Check of scheidsrechter al ingeschreven is voor een overlappende fluitwedstrijd
        if heeft_overlappende_fluitwedstrijd(nbb, wed_id, wed_datum, wedstrijden):
            continue
        
        pool_count += 1
    
    return pool_count


def get_pool_indicator(pool_size: int) -> tuple[str, str]:
    """
    Bepaal de kleur-indicator op basis van pool-grootte.
    Returns: (emoji, css_kleur)
    """
    if pool_size < 5:
        return "🔴", "#f44336"  # Kritiek
    elif pool_size <= 8:
        return "🟠", "#FF9800"  # Krap
    else:
        return "🟢", "#4CAF50"  # Ruim


def get_beschikbare_teams_voor_dag(dag_datum: datetime, dag_items: list, wedstrijden: dict, scheidsrechters: dict) -> list[str]:
    """
    Bepaal welke teams op een bepaalde dag kunnen fluiten voor de wedstrijden die er zijn.
    Kijkt naar: niveau van wedstrijden, beschikbaarheid, eigen wedstrijden.
    Returns een lijst van teamnamen, gesorteerd op niveau (hoogste eerst).
    """
    # Verzamel ALLE wedstrijden van deze dag (niet alleen de gefilterde dag_items)
    dag_str = dag_datum.strftime("%Y-%m-%d")
    alle_wed_van_dag = []
    for wed_id, wed in wedstrijden.items():
        if wed.get("geannuleerd", False):
            continue
        if wed.get("type") == "uit":
            continue
        wed_datum_str = wed["datum"][:10]  # "YYYY-MM-DD"
        if wed_datum_str == dag_str:
            alle_wed_van_dag.append({
                "id": wed_id,
                "niveau": wed.get("niveau", 1),
                "thuisteam": wed.get("thuisteam", ""),
                "uitteam": wed.get("uitteam", ""),
                "wed_datum": datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M"),
                "vereist_bs2": wed.get("vereist_bs2", False)
            })
    
    if not alle_wed_van_dag:
        return []
    
    # Bepaal het laagste niveau van de wedstrijden op deze dag
    laagste_wed_niveau = min(w["niveau"] for w in alle_wed_van_dag)
    
    teams_met_niveau = {}
    
    for nbb, scheids in scheidsrechters.items():
        # Check of uitgesloten van pool (testgebruikers, reserves)
        if scheids.get("uitgesloten_van_pool", False):
            continue
        
        niveau_1e = scheids.get("niveau_1e_scheids", 1)
        
        # Check of deze scheidsrechter minstens één wedstrijd kan fluiten qua niveau
        if niveau_1e < laagste_wed_niveau:
            continue  # Niveau te laag voor alle wedstrijden
        
        # Check zondag
        if scheids.get("niet_op_zondag", False) and dag_datum.weekday() == 6:
            continue
        
        # Check blessure status
        geblesseerd_tm = scheids.get("geblesseerd_tm", "")
        if geblesseerd_tm:
            try:
                maand_namen = ["januari", "februari", "maart", "april", "mei", "juni", 
                              "juli", "augustus", "september", "oktober", "november", "december"]
                delen = geblesseerd_tm.split()
                if len(delen) == 2:
                    maand_naam, jaar = delen[0].lower(), int(delen[1])
                    if maand_naam in maand_namen:
                        blessure_maand = maand_namen.index(maand_naam) + 1
                        if (dag_datum.year < jaar or 
                            (dag_datum.year == jaar and dag_datum.month <= blessure_maand)):
                            continue
            except:
                pass
        
        # Check geblokkeerde dagen
        geblokkeerde_dagen = scheids.get("geblokkeerde_dagen", [])
        if geblokkeerde_dagen:
            if dag_str in geblokkeerde_dagen:
                continue
        
        # Check of scheidsrechter kan fluiten voor minstens één wedstrijd
        # (niet eigen team, geen tijdsoverlap met eigen wedstrijd)
        kan_minstens_een = False
        eigen_teams_scheids = scheids.get("eigen_teams", [])
        
        for wed in alle_wed_van_dag:
            wed_niveau = wed["niveau"]
            if wed_niveau > niveau_1e:
                continue  # Dit niveau kan deze scheids niet
            
            # Check BS2 vereiste
            if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
                continue
            
            # Check eigen team
            is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams_scheids)
            is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams_scheids)
            if is_eigen_thuis or is_eigen_uit:
                continue
            
            # Check tijdsoverlap met eigen wedstrijd
            if heeft_eigen_wedstrijd(nbb, wed["wed_datum"], wedstrijden, scheidsrechters):
                continue
            
            # Check of al ingeschreven voor overlappende fluitwedstrijd
            if heeft_overlappende_fluitwedstrijd(nbb, wed["id"], wed["wed_datum"], wedstrijden):
                continue
            
            kan_minstens_een = True
            break
        
        if not kan_minstens_een:
            continue
        
        # Haal teams van deze scheidsrechter
        for team in eigen_teams_scheids:
            if team not in teams_met_niveau:
                teams_met_niveau[team] = niveau_1e
            else:
                # Houd hoogste niveau bij voor dit team
                teams_met_niveau[team] = max(teams_met_niveau[team], niveau_1e)
    
    # Sorteer op niveau (hoogste eerst) en dan alfabetisch
    gesorteerd = sorted(teams_met_niveau.items(), key=lambda x: (-x[1], x[0]))
    return [team for team, niveau in gesorteerd]


def format_beschikbare_teams(teams: list[str], max_tonen: int = 3) -> str:
    """
    Formatteer de lijst van beschikbare teams voor weergave.
    Toont max_tonen teams en dan +X voor de rest.
    """
    if not teams:
        return ""
    
    if len(teams) <= max_tonen:
        return ", ".join(teams)
    else:
        getoonde = ", ".join(teams[:max_tonen])
        rest = len(teams) - max_tonen
        return f"{getoonde} +{rest}"


def bereken_dag_indicator(dag_items: list, wedstrijden: dict, scheidsrechters: dict, nbb_nummer: str) -> tuple[str, str]:
    """
    Bereken de dag-indicator op basis van de laagste pool van wedstrijden die nog open posities hebben.
    Returns: (emoji, css_kleur)
    """
    laagste_pool = float('inf')
    
    for item in dag_items:
        if item.get("type") != "fluiten":
            continue
        
        # Skip wedstrijden die volledig bezet zijn (beide scheidsrechters toegewezen)
        wed = wedstrijden.get(item["id"], {})
        if wed.get("scheids_1") and wed.get("scheids_2"):
            continue
        
        pool = bereken_pool_voor_wedstrijd(item["id"], wedstrijden, scheidsrechters)
        laagste_pool = min(laagste_pool, pool)
    
    if laagste_pool == float('inf'):
        return "🟢", "#4CAF50"  # Geen wedstrijden met open posities
    
    return get_pool_indicator(laagste_pool)


# ============================================================
# SPELER VIEW
# ============================================================

def toon_speler_view(nbb_nummer: str):
    """Toon de inschrijfpagina voor een speler."""
    scheidsrechters = laad_scheidsrechters()
    
    if nbb_nummer not in scheidsrechters:
        st.error("❌ Onbekend NBB-nummer. Neem contact op met de TC.")
        return
    
    scheids = scheidsrechters[nbb_nummer]
    wedstrijden = laad_wedstrijden()
    instellingen = laad_instellingen()
    
    # Haal speler stats vroeg op voor gebruik in sidebar
    speler_stats = get_speler_stats(nbb_nummer)
    
    # Bepaal of speler MSE is (voor begeleiding features)
    is_mse = scheids.get("niveau_1e_scheids", 1) == 5 or any("MSE" in t.upper() for t in scheids.get("eigen_teams", []))
    
    # CSS voor compacte layout met BOB huisstijl (optie 4: subtiel met gekleurde borders)
    st.markdown("""
    <style>
        /* BOB Huisstijl kleuren */
        :root {
            --bob-blauw: #003082;
            --bob-oranje: #FF6600;
        }
        
        /* Verberg standaard Streamlit header alleen op desktop */
        @media (min-width: 769px) {
            header[data-testid="stHeader"] {
                display: none;
            }
        }
        
        /* Op mobiel: header volledig met rust laten - Streamlit default */
        
        /* Verberg toolbar alleen op desktop */
        @media (min-width: 769px) {
            [data-testid="stToolbar"] {
                display: none;
            }
        }
        
        /* Verberg deploy button alleen op desktop */
        @media (min-width: 769px) {
            .stDeployButton {
                display: none;
            }
        }
        
        /* Minimale padding op alle niveaus */
        .main .block-container {
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        
        /* App container */
        .stApp {
            margin-top: 0 !important;
        }
        
        /* Eerste element naar boven duwen */
        .main .block-container > div:first-child {
            margin-top: 0 !important;
            padding-top: 0 !important;
        }
        
        /* Section padding */
        section[data-testid="stMain"] > div {
            padding-top: 0 !important;
        }
        
        /* Sidebar styling - lichtgrijs met blauwe border */
        /* Meerdere selectors voor compatibiliteit met verschillende Streamlit versies */
        section[data-testid="stSidebar"],
        [data-testid="stSidebar"],
        .st-emotion-cache-1gv3huu,
        .stSidebar,
        aside {
            background-color: #f8f9fa !important;
        }
        
        /* Blauwe border en breedte alleen op desktop */
        @media (min-width: 769px) {
            section[data-testid="stSidebar"],
            [data-testid="stSidebar"],
            .stSidebar,
            aside {
                border-right: 3px solid #003082 !important;
                min-width: 320px !important;
                width: 320px !important;
            }
            
            section[data-testid="stSidebar"] > div:first-child,
            [data-testid="stSidebar"] > div:first-child {
                width: 320px !important;
            }
        }
        
        /* Sidebar inner content ook lichtgrijs */
        section[data-testid="stSidebar"] > div,
        [data-testid="stSidebar"] > div,
        .stSidebar > div {
            background-color: #f8f9fa !important;
        }
        
        /* ============================================ */
        /* MOBIELE OPTIMALISATIES                      */
        /* ============================================ */
        
        @media (max-width: 768px) {
            /* Metrics compacter op mobiel */
            [data-testid="stMetricValue"] {
                font-size: 1.2rem !important;
            }
            
            [data-testid="stMetricLabel"] {
                font-size: 0.7rem !important;
            }
            
            /* Expanders volle breedte */
            .streamlit-expanderHeader {
                font-size: 0.9rem !important;
            }
            
            /* GEEN sidebar width aanpassingen op mobiel - Streamlit default gebruiken */
        }
        
        section[data-testid="stSidebar"] [data-testid="stMarkdown"] h3,
        [data-testid="stSidebar"] [data-testid="stMarkdown"] h3,
        .stSidebar h3 {
            color: #003082 !important;
            border-bottom: 2px solid #FF6600 !important;
            padding-bottom: 5px !important;
        }
        
        /* Metrics met blauwe top border en oranje waarden */
        [data-testid="stMetric"] {
            background-color: #f8f9fa;
            padding: 0.3rem;
            border-radius: 0.5rem;
            border-top: 3px solid #003082 !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.2rem;
            color: #FF6600 !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.7rem;
            color: #003082 !important;
        }
        
        /* Divider/horizontal rule in oranje */
        hr {
            border-color: #FF6600 !important;
            border-top: 2px solid #FF6600 !important;
        }
        
        /* Compacte alerts */
        .stAlert {
            padding: 0.3rem 0.6rem !important;
            margin-bottom: 0.3rem !important;
        }
        .stAlert p {
            margin-bottom: 0 !important;
        }
        
        /* Compacte expanders */
        details summary {
            padding: 0.3rem 0 !important;
            font-size: 0.9rem;
        }
        
        /* Scrollbare container styling - oranje border */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border: 2px solid #FF6600 !important;
            border-radius: 0.5rem;
        }
        
        /* Subheaders in blauw */
        .main [data-testid="stMarkdown"] h2,
        .main [data-testid="stMarkdown"] h3,
        .main [data-testid="stSubheader"] {
            color: #003082 !important;
        }
        
        /* Success alerts met oranje accent */
        .stAlert[data-baseweb="notification"] {
            border-left-color: #FF6600 !important;
        }
        
        /* Warning in oranje */
        div[data-testid="stAlert"][kind="warning"] {
            border-left-color: #FF6600 !important;
        }
        
        /* Buttons */
        .stButton > button[kind="primary"] {
            background-color: #003082 !important;
            border-color: #003082 !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #004db3 !important;
            border-color: #004db3 !important;
        }
        
        /* Toggle switches */
        [data-testid="stToggle"] label span {
            color: #003082 !important;
        }
        
        /* Verberg footer */
        footer {
            display: none !important;
        }
        
        /* Minimale ruimte na scrollbare container */
        [data-testid="stVerticalBlockBorderWrapper"] {
            margin-bottom: 0 !important;
        }
        
        /* Verwijder extra ruimte onderaan main */
        section[data-testid="stMain"] {
            padding-bottom: 0 !important;
        }
        
        /* Verberg "Made with Streamlit" */
        .viewerBadge_container__r5tak {
            display: none !important;
        }
        
        /* Bottom bar verbergen */
        .stBottom {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar met legenda
    with st.sidebar:
        # ============================================================
        # KLASSEMENT (NIET SAMENGEVOUWEN)
        # ============================================================
        st.markdown("### 🏆 Klassement")
        punten_klassement = get_punten_klassement_met_positie(nbb_nummer)
        
        if punten_klassement["top3"]:
            medailles = ["🥇", "🥈", "🥉"]
            eigen_in_top3 = False
            
            for i, scheids_info in enumerate(punten_klassement["top3"]):
                is_eigen = scheids_info["nbb"] == nbb_nummer
                if is_eigen:
                    eigen_in_top3 = True
                    st.markdown(f"{medailles[i]} **{scheids_info['naam']}** - {scheids_info['punten']} pt 👈")
                else:
                    st.markdown(f"{medailles[i]} **{scheids_info['naam']}** - {scheids_info['punten']} pt")
            
            # Toon eigen positie als niet in top 3
            if not eigen_in_top3 and punten_klassement["eigen"]:
                eigen = punten_klassement["eigen"]
                st.caption("...")
                st.markdown(f"**{eigen['positie']}.** {eigen['naam']} - {eigen['punten']} pt 👈")
        else:
            st.caption("*Nog geen punten verdiend*")
        
        # ============================================================
        # TOP BEGELEIDERS (NIET SAMENGEVOUWEN)
        # ============================================================
        st.markdown("### 🎓 Top Begeleiders")
        beg_klassement = get_begeleiders_klassement_met_positie(nbb_nummer)
        
        if beg_klassement["top3"]:
            medailles = ["🥇", "🥈", "🥉"]
            eigen_in_top3 = False
            
            for i, begeleider in enumerate(beg_klassement["top3"]):
                is_eigen = begeleider["nbb"] == nbb_nummer
                if is_eigen:
                    eigen_in_top3 = True
                    st.markdown(f"{medailles[i]} **{begeleider['naam']}** - {begeleider['begeleidingen']}x 👈")
                else:
                    st.markdown(f"{medailles[i]} **{begeleider['naam']}** - {begeleider['begeleidingen']}x")
            
            # Toon eigen positie als niet in top 3
            if not eigen_in_top3 and beg_klassement["eigen"]:
                eigen = beg_klassement["eigen"]
                st.caption("...")
                st.markdown(f"**{eigen['positie']}.** {eigen['naam']} - {eigen['begeleidingen']}x 👈")
        else:
            st.caption("*Nog geen begeleidingen*")
        
        st.divider()
        
        # ============================================================
        # JOUW GEGEVENS (SAMENGEVOUWEN)
        # ============================================================
        eigen_niveau = scheids.get("niveau_1e_scheids", 1)
        max_niveau_2e = min(eigen_niveau + 1, 5)
        
        with st.expander("👤 Jouw gegevens"):
            st.markdown(f"**1e scheids niveau:** {eigen_niveau}")
            st.markdown(f"**2e scheids niveau:** {max_niveau_2e}")
            if scheids.get("bs2_diploma", False):
                st.markdown("✅ BS2 diploma")
            eigen_teams = scheids.get("eigen_teams", [])
            if eigen_teams:
                st.markdown(f"**Teams:** {', '.join(eigen_teams)}")
            if scheids.get("open_voor_begeleiding", False):
                st.markdown("🎓 Open voor begeleiding")
            
            st.divider()
            st.caption("**Niveau regels:**")
            st.markdown(f"""
            - 1e scheids: max niveau **{eigen_niveau}**
            - 2e scheids: max niveau **{max_niveau_2e}**
            - *Met MSE als 1e: **geen limiet** 🎓*
            - BS2 wedstrijden: alleen met diploma
            """)
        
        # ============================================================
        # PUNTEN & STRIKES (SAMENGEVOUWEN)
        # ============================================================
        beloningsinst = laad_beloningsinstellingen()
        
        with st.expander("🏆 Punten & Strikes"):
            st.markdown("**Punten verdienen:**")
            st.markdown(f"""
            | Actie | Punten |
            |-------|--------|
            | Wedstrijd fluiten | {beloningsinst['punten_per_wedstrijd']} |
            | Lastig tijdstip* | +{beloningsinst['punten_lastig_tijdstip']} |
            | Invallen <48 uur | +{beloningsinst['punten_inval_48u']} |
            | Invallen <24 uur | +{beloningsinst['punten_inval_24u']} |
            
            *Lastig = apart terugkomen om te fluiten  
            **{beloningsinst['punten_voor_voucher']} punten** = voucher Clinic!
            """)
            
            st.markdown("**🏆 Pool Bonus:**")
            st.markdown(f"""
            Extra punten voor wedstrijden met weinig beschikbare scheids:
            
            | Pool grootte | Bonus |
            |--------------|-------|
            | 🔴 ≤{beloningsinst.get('pool_kritiek_grens', 3)} (kritiek) | +{beloningsinst.get('punten_pool_kritiek', 3)} |
            | 🟠 {beloningsinst.get('pool_kritiek_grens', 3)+1}-{beloningsinst.get('pool_zeer_krap_grens', 5)} (zeer krap) | +{beloningsinst.get('punten_pool_zeer_krap', 2)} |
            | 🟡 {beloningsinst.get('pool_zeer_krap_grens', 5)+1}-{beloningsinst.get('pool_krap_grens', 8)} (krap) | +{beloningsinst.get('punten_pool_krap', 1)} |
            | 🟢 >{beloningsinst.get('pool_krap_grens', 8)} | geen bonus |
            
            *De pool zie je bij elke wedstrijd*
            """)
            
            st.divider()
            
            st.markdown("**Strikes:**")
            strikes_vervallen_tekst = "*Vervallen einde seizoen*" if beloningsinst['strikes_vervallen_einde_seizoen'] else ""
            st.markdown(f"""
            | Situatie | Strikes |
            |----------|---------|
            | Afmelding <48u | {beloningsinst['strikes_afmelding_48u']} |
            | Afmelding <24u | {beloningsinst['strikes_afmelding_24u']} |
            | No-show | {beloningsinst['strikes_no_show']} |
            
            **Met vervanging** = geen strike!
            
            ⚠️ {beloningsinst['strikes_waarschuwing_bij']} strikes = Let op!  
            ❌ {beloningsinst['strikes_gesprek_bij']} strikes = Gesprek TC
            
            **Wegwerken:** Klusje (-1), Extra wedstrijd (-{beloningsinst['strike_reductie_extra_wedstrijd']}), Invallen <48u (-{beloningsinst['strike_reductie_invallen']})
            
            {strikes_vervallen_tekst}
            """)
        
        # ============================================================
        # JOUW HISTORIE (SAMENGEVOUWEN - alleen als er data is)
        # ============================================================
        if speler_stats["punten"] > 0 or speler_stats["strikes"] > 0:
            with st.expander(f"📊 Jouw historie ({speler_stats['punten']} pt, {speler_stats['strikes']} strikes)"):
                # Combineer wedstrijd punten en handmatige aanpassingen
                heeft_punten_historie = speler_stats["gefloten_wedstrijden"] or speler_stats.get("punten_log", [])
                
                if heeft_punten_historie:
                    st.markdown("**🏆 Punten:**")
                    # Wedstrijd punten
                    for wed_reg in reversed(speler_stats["gefloten_wedstrijden"][-5:]):
                        berekening = wed_reg.get("berekening", {})
                        if berekening:
                            st.caption(f"+{wed_reg['punten']} op {berekening.get('inschrijf_moment_leesbaar', '?')}")
                        else:
                            st.caption(f"+{wed_reg['punten']} - {wed_reg.get('reden', '')}")
                    
                    # Handmatige aanpassingen
                    for entry in reversed(speler_stats.get("punten_log", [])[-3:]):
                        teken = "+" if entry["punten"] > 0 else ""
                        st.caption(f"{teken}{entry['punten']} - {entry['reden']}")
                
                if speler_stats["strike_log"]:
                    st.divider()
                    st.markdown("**⚠️ Strikes:**")
                    for strike in reversed(speler_stats["strike_log"][-5:]):
                        teken = "+" if strike["strikes"] > 0 else ""
                        st.caption(f"{teken}{strike['strikes']} - {strike['reden']}")
        
        # ============================================================
        # LEGENDA (SAMENGEVOUWEN)
        # ============================================================
        with st.expander("📋 Legenda"):
            # Niveau uitleg
            st.markdown("**Niveaus:**")
            niveaus = instellingen.get("niveaus", {})
            for niveau in sorted(niveaus.keys(), key=int):
                omschrijving = niveaus[niveau]
                st.caption(f"**{niveau}** - {omschrijving}")
            
            st.divider()
            
            # Kleuren uitleg
            st.markdown("**Kleuren:**")
            st.markdown("""
            <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 0.3rem; margin: 0.15rem 0; border-radius: 0 0.25rem 0.25rem 0; font-size: 0.75rem;">
                ⭐ Jouw niveau
            </div>
            """, unsafe_allow_html=True)
            st.markdown("""
            <div style="background-color: #f0f2f6; border-left: 4px solid #6c757d; padding: 0.3rem; margin: 0.15rem 0; border-radius: 0 0.25rem 0.25rem 0; font-size: 0.75rem;">
                🏀 Onder jouw niveau
            </div>
            """, unsafe_allow_html=True)
            st.markdown("""
            <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 0.3rem; margin: 0.15rem 0; border-radius: 0 0.25rem 0.25rem 0; font-size: 0.75rem;">
                🏠🚗 Eigen wedstrijd
            </div>
            """, unsafe_allow_html=True)
            
            st.divider()
            
            # Symbolen uitleg
            st.markdown("**Symbolen:**")
            st.caption("🙋 Jij bent ingeschreven")
            st.caption("👤 Iemand anders")
            st.caption("📋 Beschikbaar")
            st.caption("🎓 Begeleider (MSE)")
            if is_mse:
                st.caption("👤🎓 Wil begeleiding ontvangen")
        
        # ============================================================
        # MIJN FEEDBACK (SAMENGEVOUWEN - alleen als er data is)
        # ============================================================
        feedback_data = laad_begeleiding_feedback()
        mijn_feedback = [fb for fb_id, fb in feedback_data.items() 
                         if fb.get("speler_nbb") == nbb_nummer 
                         and fb.get("status") != "begeleider_gezien"
                         and fb.get("begeleider_nbb") != nbb_nummer]
        
        if mijn_feedback:
            with st.expander(f"📝 Mijn feedback ({len(mijn_feedback)})"):
                for fb in sorted(mijn_feedback, key=lambda x: x.get("feedback_datum", ""), reverse=True)[:5]:
                    wed = wedstrijden.get(fb.get("wed_id"), {})
                    if not wed:
                        continue
                    begeleider_naam = scheidsrechters.get(fb.get("begeleider_nbb"), {}).get("naam", "?")
                    status_icons = {
                        "aanwezig_geholpen": "✅",
                        "aanwezig_niet_geholpen": "⚠️",
                        "niet_aanwezig": "❌",
                        "bevestigd": "👁️"
                    }
                    status_icon = status_icons.get(fb.get("status"), "?")
                    
                    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                    st.caption(f"{status_icon} {wed_datum.strftime('%d-%m')} - {begeleider_naam}")
                    
                    # Wijzig knop (alleen voor echte feedback, niet voor bevestigingen)
                    if fb.get("status") != "bevestigd":
                        wed_id = fb.get("wed_id")
                        mijn_nbb = fb.get("speler_nbb")
                        
                        scheids_1_nbb = wed.get("scheids_1")
                        scheids_2_nbb = wed.get("scheids_2")
                        
                        if mijn_nbb == scheids_1_nbb:
                            andere_scheids = scheids_2_nbb
                        elif mijn_nbb == scheids_2_nbb:
                            andere_scheids = scheids_1_nbb
                        else:
                            andere_scheids = None
                        
                        andere_bevestigd = False
                        if andere_scheids:
                            andere_fb_id = f"fb_{wed_id}_{andere_scheids}"
                            andere_fb = feedback_data.get(andere_fb_id)
                            if andere_fb and andere_fb.get("status") == "bevestigd":
                                andere_bevestigd = True
                        
                        if andere_bevestigd:
                            st.caption("*Collega heeft bevestigd*")
                        else:
                            if st.button("✏️ Wijzig", key=f"wijzig_fb_{fb.get('feedback_id')}", help="Feedback wijzigen"):
                                verwijder_begeleiding_feedback(fb.get("feedback_id"))
                                st.rerun()
        
        # ============================================================
        # NIET BESCHIKBAAR (SAMENGEVOUWEN)
        # ============================================================
        with st.expander("🚫 Niet beschikbaar"):
            st.caption("Vink dagen aan waarop je niet kunt fluiten. Je wordt dan niet gevraagd als vervanger en niet ingedeeld door de TC.")
            
            # Haal unieke wedstrijddagen op (alleen toekomst, alleen thuiswedstrijden)
            nu = datetime.now()
            vandaag_str = nu.strftime("%Y-%m-%d")
            wedstrijd_dagen = set()
            for wed_id, wed in wedstrijden.items():
                if wed.get("type", "thuis") != "thuis":
                    continue
                if wed.get("geannuleerd", False):
                    continue
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                if wed_datum > nu:
                    # Alleen de datum (zonder tijd)
                    wedstrijd_dagen.add(wed_datum.strftime("%Y-%m-%d"))
            
            # Huidige blokkades ophalen
            huidige_blokkades = scheids.get("geblokkeerde_dagen", [])
            if not isinstance(huidige_blokkades, list):
                huidige_blokkades = []
            
            # Splits blokkades in verleden (vastgezet) en toekomst (aanpasbaar)
            verleden_blokkades = [d for d in huidige_blokkades if d < vandaag_str]
            
            if wedstrijd_dagen or verleden_blokkades:
                # Sorteer op datum
                gesorteerde_dagen = sorted(wedstrijd_dagen)
                
                # Groepeer per maand voor overzichtelijkheid
                dagen_per_maand = {}
                maand_namen = ["jan", "feb", "mrt", "apr", "mei", "jun", 
                              "jul", "aug", "sep", "okt", "nov", "dec"]
                dag_namen = ["ma", "di", "wo", "do", "vr", "za", "zo"]
                
                for dag_str in gesorteerde_dagen:
                    dag_dt = datetime.strptime(dag_str, "%Y-%m-%d")
                    maand_key = f"{maand_namen[dag_dt.month - 1]} {dag_dt.year}"
                    if maand_key not in dagen_per_maand:
                        dagen_per_maand[maand_key] = []
                    dagen_per_maand[maand_key].append(dag_str)
                
                nieuwe_blokkades = list(verleden_blokkades)  # Verleden blokkades blijven altijd behouden
                
                for maand, dagen in dagen_per_maand.items():
                    st.caption(f"**{maand}**")
                    
                    # Toon dagen in rijen van 4
                    for i in range(0, len(dagen), 4):
                        cols = st.columns(4)
                        for j, col in enumerate(cols):
                            if i + j < len(dagen):
                                dag_str = dagen[i + j]
                                dag_dt = datetime.strptime(dag_str, "%Y-%m-%d")
                                dag_label = f"{dag_namen[dag_dt.weekday()]} {dag_dt.day}"
                                
                                is_geblokkeerd = dag_str in huidige_blokkades
                                
                                with col:
                                    if st.checkbox(dag_label, value=is_geblokkeerd, key=f"blokkade_{dag_str}"):
                                        nieuwe_blokkades.append(dag_str)
                
                # Check of er iets is gewijzigd
                if set(nieuwe_blokkades) != set(huidige_blokkades):
                    # Check welke dagen nieuw geblokkeerd worden
                    nieuw_geblokkeerde_dagen = set(nieuwe_blokkades) - set(huidige_blokkades)
                    
                    # Check of speler is ingedeeld op een van de nieuw geblokkeerde dagen
                    conflicten = []
                    for dag_str in nieuw_geblokkeerde_dagen:
                        for wed_id, wed in wedstrijden.items():
                            if wed.get("type", "thuis") != "thuis":
                                continue
                            if wed.get("geannuleerd", False):
                                continue
                            wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                            wed_dag_str = wed_datum.strftime("%Y-%m-%d")
                            
                            if wed_dag_str == dag_str:
                                # Check of speler is ingedeeld voor deze wedstrijd
                                positie = None
                                if wed.get("scheids_1") == nbb_nummer:
                                    positie = "scheids_1"
                                elif wed.get("scheids_2") == nbb_nummer:
                                    positie = "scheids_2"
                                
                                if positie:
                                    conflicten.append({
                                        "wed_id": wed_id,
                                        "wed": wed,
                                        "positie": positie,
                                        "datum": wed["datum"]
                                    })
                    
                    # Als er conflicten zijn: automatisch uitschrijven
                    if conflicten:
                        uitgeschreven_wedstrijden = []
                        for conflict in conflicten:
                            wed_id = conflict["wed_id"]
                            positie = conflict["positie"]
                            wed = conflict["wed"]
                            
                            # Registreer afmelding
                            registreer_afmelding(wed_id, nbb_nummer, positie, wedstrijden)
                            
                            # Verwijder toewijzing
                            wedstrijden[wed_id][positie] = None
                            wedstrijden[wed_id][f"{positie}_punten_berekend"] = None
                            wedstrijden[wed_id][f"{positie}_punten_details"] = None
                            sla_wedstrijd_op(wed_id, wedstrijden[wed_id])
                            
                            # Log
                            uitgeschreven_wedstrijden.append(f"{wed['thuisteam']} vs {wed['uitteam']} ({conflict['datum'][:10]})")
                        
                        # Toon melding
                        st.warning(f"⚠️ Je bent automatisch uitgeschreven voor {len(uitgeschreven_wedstrijden)} wedstrijd(en) op geblokkeerde dag(en):\n" + "\n".join([f"• {w}" for w in uitgeschreven_wedstrijden]))
                    
                    # Update scheidsrechter data
                    scheids["geblokkeerde_dagen"] = nieuwe_blokkades
                    sla_scheidsrechter_op(nbb_nummer, scheids)
                    st.rerun()
                
                # Toon samenvatting
                actieve_blokkades = [d for d in nieuwe_blokkades if d >= vandaag_str]
                if actieve_blokkades or verleden_blokkades:
                    samenvatting = []
                    if actieve_blokkades:
                        samenvatting.append(f"{len(actieve_blokkades)} komend")
                    if verleden_blokkades:
                        samenvatting.append(f"{len(verleden_blokkades)} verleden")
                    st.caption(f"*Geblokkeerd: {', '.join(samenvatting)}*")
                    
                    if verleden_blokkades:
                        st.caption("*🔒 Verleden blokkades kunnen niet worden verwijderd*")
            else:
                st.caption("*Geen toekomstige wedstrijddagen*")
        
        # ============================================================
        # APPARATEN (SAMENGEVOUWEN)
        # ============================================================
        device_count = db.get_device_count(nbb_nummer)
        pending_devices = db.get_pending_devices(nbb_nummer)
        
        apparaat_label = f"📱 Apparaten ({device_count})"
        if pending_devices:
            apparaat_label += f" ⏳{len(pending_devices)}"
        
        with st.expander(apparaat_label):
            # Pending approvals
            if pending_devices:
                st.warning(f"⏳ {len(pending_devices)} wacht op goedkeuring!")
                for device in pending_devices:
                    device_name = device.get("device_name", "Onbekend")
                    created = db.format_datetime(device.get("created_at", ""))
                    
                    st.markdown(f"**{device_name}**")
                    st.caption(f"Aangevraagd: {created}")
                    
                    col_approve, col_reject = st.columns(2)
                    with col_approve:
                        if st.button("✅", key=f"approve_{device['id']}", use_container_width=True, help="Goedkeuren"):
                            if db.approve_device(device["id"], nbb_nummer):
                                st.success("Goedgekeurd!")
                                st.rerun()
                    with col_reject:
                        if st.button("❌", key=f"reject_{device['id']}", use_container_width=True, help="Weigeren"):
                            if db.reject_device(device["id"], nbb_nummer):
                                st.success("Geweigerd!")
                                st.rerun()
                    st.divider()
            
            # Gekoppelde apparaten
            devices = db.get_devices(nbb_nummer)
            approved_devices = [d for d in devices if d.get("approved", True)]
            
            if approved_devices:
                st.caption("**Gekoppeld:**")
                for device in approved_devices:
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        device_name = device.get("device_name", "Onbekend")
                        fingerprint = device.get("fingerprint", "")[:6] if device.get("fingerprint") else ""
                        st.caption(f"{device_name} ({fingerprint})")
                    with col_btn:
                        if st.button("🗑️", key=f"del_device_{device['id']}", help="Verwijder"):
                            if db.remove_device(device["id"], nbb_nummer):
                                st.rerun()
            
            st.divider()
            
            # Instellingen (compact)
            st.caption("**Instellingen:**")
            settings = db.get_speler_device_settings(nbb_nummer)
            
            current_max = settings.get("max_devices")
            max_options = {"Geen limiet": None, "1": 1, "2": 2, "3": 3, "5": 5}
            current_label = next((k for k, v in max_options.items() if v == current_max), "Geen limiet")
            
            new_max_label = st.selectbox(
                "Max apparaten",
                options=list(max_options.keys()),
                index=list(max_options.keys()).index(current_label),
                key="device_max_select",
                label_visibility="collapsed"
            )
            new_max = max_options[new_max_label]
            
            require_approval = st.checkbox(
                "Goedkeuring vereist",
                value=settings.get("require_approval", False),
                key="device_require_approval"
            )
            
            if st.button("💾 Opslaan", key="save_device_settings", use_container_width=True):
                if db.save_speler_device_settings(nbb_nummer, new_max, require_approval):
                    st.success("Opgeslagen!")
                    st.rerun()
        
        # ============================================================
        # FOOTER
        # ============================================================
        st.divider()
        st.caption(f"Ref Planner v{APP_VERSIE}")
        
        # Netwerk info (samengevouwen)
        ip_info = db.get_ip_info()
        with st.expander("🌍 Netwerk"):
            st.caption(f"IP: {ip_info['ip']}")
            st.caption(f"Land: {ip_info['country']}")
            if ip_info['allowed']:
                st.caption("✅ Toegang OK")
            else:
                st.caption("❌ Geblokkeerd")
    
    # ============================================================
    # COMPACTE HEADER
    # ============================================================
    
    # Logo's en titel - responsive via CSS
    logo_path = Path(__file__).parent / "logo.png"
    bob_logo_path = Path(__file__).parent / "bob-logo.svg"
    
    # Lees logo's als base64 voor HTML embedding
    import base64
    logo_b64 = ""
    bob_logo_b64 = ""
    
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
    
    if bob_logo_path.exists():
        with open(bob_logo_path, "rb") as f:
            bob_logo_b64 = base64.b64encode(f.read()).decode()
    
    # Responsive header met CSS
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" class="header-logo" alt="Logo">' if logo_b64 else ""
    bob_html = f'<img src="data:image/svg+xml;base64,{bob_logo_b64}" class="header-logo" alt="BOB Logo">' if bob_logo_b64 else ""
    
    st.markdown(f"""
    <style>
        /* Desktop header: logo - titel - logo */
        .desktop-header {{
            display: flex;
            flex-direction: row;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.5rem;
        }}
        .header-logo {{
            width: 80px;
            height: auto;
        }}
        .header-title {{
            flex: 1;
            text-align: center;
            font-size: 1.3rem;
            font-weight: bold;
            margin: 0;
        }}
        
        /* Mobiele header: logo's naast elkaar, titel eronder */
        .mobile-header {{
            display: none;
            flex-direction: column;
            align-items: center;
            margin-bottom: 0.5rem;
        }}
        .mobile-logos {{
            display: flex;
            gap: 2rem;
            justify-content: center;
            margin-bottom: 0.3rem;
        }}
        .mobile-header .header-logo {{
            width: 60px;
        }}
        .mobile-title {{
            font-size: 1.1rem;
            font-weight: bold;
            text-align: center;
            margin: 0;
        }}
        
        /* Switch tussen desktop en mobiel */
        @media (max-width: 768px) {{
            .desktop-header {{
                display: none !important;
            }}
            .mobile-header {{
                display: flex !important;
            }}
        }}
    </style>
    
    <!-- Desktop header -->
    <div class="desktop-header">
        {logo_html}
        <p class="header-title">🏀 Welkom, {scheids['naam']}</p>
        {bob_html}
    </div>
    
    <!-- Mobiele header -->
    <div class="mobile-header">
        <div class="mobile-logos">
            {logo_html}
            {bob_html}
        </div>
        <p class="mobile-title">🏀 Welkom, {scheids['naam']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Status metrics in compacte rij - korte labels voor mobiel
    niveau_stats = tel_wedstrijden_op_eigen_niveau(nbb_nummer)
    huidig_aantal = niveau_stats["totaal"]
    op_niveau = niveau_stats["op_niveau"]
    eigen_niveau = niveau_stats["niveau"]
    min_wed = scheids.get("min_wedstrijden", 0)
    beloningsinst = laad_beloningsinstellingen()
    strikes = speler_stats["strikes"]
    
    # Custom CSS voor responsive layout
    st.markdown("""
    <style>
        /* ============================================ */
        /* METRICS: altijd naast elkaar, ook op mobiel */
        /* ============================================ */
        @media (max-width: 768px) {
            /* Target alleen rijen die metrics bevatten */
            [data-testid="stHorizontalBlock"]:has([data-testid="stMetricValue"]) {
                flex-wrap: nowrap !important;
                gap: 0.2rem !important;
            }
            
            [data-testid="stHorizontalBlock"]:has([data-testid="stMetricValue"]) > div {
                flex: 1 1 0 !important;
                min-width: 0 !important;
                width: auto !important;
            }
            
            /* Metric waarde kleiner */
            [data-testid="stMetricValue"] {
                font-size: 1.1rem !important;
            }
            
            /* Metric label kleiner */
            [data-testid="stMetricLabel"] {
                font-size: 0.6rem !important;
            }
            
            /* Metric delta kleiner */
            [data-testid="stMetricDelta"] {
                font-size: 0.55rem !important;
            }
            
            /* ============================================ */
            /* FILTERS: onder elkaar op mobiel             */
            /* ============================================ */
            /* Target rijen die toggles bevatten */
            [data-testid="stHorizontalBlock"]:has([data-testid="stToggle"]) {
                flex-wrap: wrap !important;
            }
            
            [data-testid="stHorizontalBlock"]:has([data-testid="stToggle"]) > div {
                flex: 0 0 100% !important;
                max-width: 100% !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Totaal", huidig_aantal)
    with col2:
        st.metric(f"Niv{eigen_niveau}+", op_niveau)
    with col3:
        st.metric("Min", min_wed)
    with col4:
        st.metric("🏆", speler_stats["punten"])
    with col5:
        if strikes >= beloningsinst["strikes_gesprek_bij"]:
            st.metric("⚠️", strikes, delta="!", delta_color="inverse")
        elif strikes >= beloningsinst["strikes_waarschuwing_bij"]:
            st.metric("⚠️", strikes, delta="!", delta_color="inverse")
        else:
            st.metric("⚠️", strikes)
    
    # Gebogen oranje lijn onder metrics (zelfde styling als blauwe border-top, 180° geroteerd)
    st.markdown("""
    <div style="
        border-top: 3px solid #FF6600;
        border-radius: 0.5rem;
        height: 0.5rem;
        transform: rotate(180deg);
        margin: 0.3rem 0;
    "></div>
    """, unsafe_allow_html=True)
    
    # ============================================================
    # PUNTEN KLASSEMENT (altijd zichtbaar)
    # ============================================================
    
    punten_klas = get_punten_klassement_met_positie(nbb_nummer)
    
    # Bouw klassement regel
    klassement_items = []
    if punten_klas["top3"]:
        medailles = ["🥇", "🥈", "🥉"]
        for i, s in enumerate(punten_klas["top3"]):
            if s["nbb"] == nbb_nummer:
                klassement_items.append(f'{medailles[i]} **{s["naam"]}** ({s["punten"]})')
            else:
                klassement_items.append(f'{medailles[i]} {s["naam"]} ({s["punten"]})')
        
        # Toon eigen positie als niet in top 3
        eigen_in_top3 = any(s["nbb"] == nbb_nummer for s in punten_klas["top3"])
        if not eigen_in_top3 and punten_klas["eigen"]:
            eigen = punten_klas["eigen"]
            klassement_items.append(f'··· **#{eigen["positie"]} Jij** ({eigen["punten"]})')
    
    # Wrap in div die alleen op mobiel zichtbaar is
    if klassement_items:
        st.markdown(f"🏆 **Klassement:** {' · '.join(klassement_items)}")
    else:
        st.caption("🏆 *Klassement: nog geen punten verdiend*")
    
    # Status + Deadline in één rij
    tekort = max(0, min_wed - op_niveau)
    deadline_info = get_deadline_maand_info()
    deadline = deadline_info["deadline"]
    dagen_over = (deadline - datetime.now()).days
    maand_namen_vol = ["", "januari", "februari", "maart", "april", "mei", "juni", 
                       "juli", "augustus", "september", "oktober", "november", "december"]
    
    gesloten_maand_naam = maand_namen_vol[deadline_info["gesloten_maand"]]
    
    col_status, col_deadline = st.columns(2)
    with col_status:
        if tekort > 0:
            st.warning(f"⚠️ Nog **{tekort}** wedstrijd(en) kiezen op niveau {eigen_niveau}+")
        else:
            st.success(f"✅ Minimum voldaan ({op_niveau}/{min_wed})")
    with col_deadline:
        if deadline_info["is_verlopen"]:
            st.info(f"📅 **{gesloten_maand_naam}** gesloten, latere maanden open")
        else:
            st.info(f"📅 Deadline **{dagen_over}** dagen voor {gesloten_maand_naam}")
    
    # Begeleiding status (compact)
    open_voor_begeleiding = scheids.get("open_voor_begeleiding", False)
    begeleiding_reden = scheids.get("begeleiding_reden", "")
    telefoon_begeleiding = scheids.get("telefoon_begeleiding", "")
    
    # Klusjes, uitnodigingen en verzoeken ophalen voor header alerts
    klusjes = laad_klusjes()
    mijn_klusjes = [k for k_id, k in klusjes.items() if k.get("nbb_nummer") == nbb_nummer and not k.get("afgerond", False)]
    
    uitnodigingen = laad_begeleidingsuitnodigingen()
    mijn_uitnodigingen = [u for u_id, u in uitnodigingen.items() 
                          if u.get("speler_nbb") == nbb_nummer 
                          and u.get("status") == "pending"]
    
    verzoeken = laad_vervangingsverzoeken()
    inkomende_verzoeken = [v for v_id, v in verzoeken.items() 
                          if v.get("vervanger_nbb") == nbb_nummer 
                          and v.get("status") == "pending"]
    
    # Begeleiding feedback: wedstrijden met begeleider die al gespeeld zijn
    nu = datetime.now()
    feedback_data = laad_begeleiding_feedback()
    
    # Zoek wedstrijden waar ik scheidsrechter was, met begeleider, die al gespeeld zijn
    wedstrijden_voor_feedback = []
    wedstrijden_collega_feedback = []  # Wedstrijden waar collega al feedback gaf
    
    for wed_id, wed in wedstrijden.items():
        if wed.get("geannuleerd", False):
            continue
        begeleider_nbb = wed.get("begeleider")
        if not begeleider_nbb:
            continue
        
        # Ben ik zelf de begeleider? Dan geen feedback over mezelf
        if begeleider_nbb == nbb_nummer:
            continue
        
        # Was ik scheidsrechter bij deze wedstrijd?
        was_scheids = wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer
        if not was_scheids:
            continue
        
        # Is de wedstrijd al gespeeld?
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        wed_eind = wed_datum + timedelta(hours=1, minutes=30)
        if wed_eind > nu:
            continue  # Wedstrijd nog niet afgelopen
        
        # Heb ik al feedback gegeven?
        feedback_id = f"fb_{wed_id}_{nbb_nummer}"
        if feedback_id in feedback_data:
            continue  # Al feedback gegeven (of bevestigd)
        
        # Check of de andere scheidsrechter al feedback heeft gegeven
        andere_scheids = wed.get("scheids_2") if wed.get("scheids_1") == nbb_nummer else wed.get("scheids_1")
        andere_feedback = None
        if andere_scheids:
            andere_feedback_id = f"fb_{wed_id}_{andere_scheids}"
            andere_fb = feedback_data.get(andere_feedback_id)
            # Alleen echte feedback telt, niet bevestigingen
            if andere_fb and andere_fb.get("status") != "bevestigd":
                andere_feedback = andere_fb
        
        if andere_feedback:
            # Collega heeft echte feedback gegeven
            wedstrijden_collega_feedback.append({
                "wed_id": wed_id,
                "wed": wed,
                "wed_datum": wed_datum,
                "begeleider_nbb": begeleider_nbb,
                "feedback_id": feedback_id,
                "collega_nbb": andere_scheids,
                "collega_feedback": andere_feedback
            })
        else:
            # Nog geen feedback van collega
            wedstrijden_voor_feedback.append({
                "wed_id": wed_id,
                "wed": wed,
                "wed_datum": wed_datum,
                "begeleider_nbb": begeleider_nbb,
                "feedback_id": feedback_id
            })
    
    # Toon wedstrijden waar collega al feedback gaf (alleen OK knop nodig)
    if wedstrijden_collega_feedback:
        st.info(f"ℹ️ **Collega heeft al feedback gegeven over {len(wedstrijden_collega_feedback)} begeleiding(en)**")
        for fb_item in wedstrijden_collega_feedback:
            wed = fb_item["wed"]
            wed_datum = fb_item["wed_datum"]
            begeleider_naam = scheidsrechters.get(fb_item["begeleider_nbb"], {}).get("naam", "Onbekend")
            collega_naam = scheidsrechters.get(fb_item["collega_nbb"], {}).get("naam", "Collega")
            collega_status = fb_item["collega_feedback"].get("status", "")
            dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
            
            status_tekst = {
                "aanwezig_geholpen": "✅ was aanwezig en heeft geholpen",
                "aanwezig_niet_geholpen": "⚠️ was aanwezig maar heeft niet geholpen",
                "niet_aanwezig": "❌ is niet komen opdagen"
            }.get(collega_status, collega_status)
            
            with st.container():
                st.markdown(f"**{dag} {wed_datum.strftime('%d-%m')}** - {wed['thuisteam']} vs {wed['uitteam']}")
                st.markdown(f"*{collega_naam}* gaf aan dat **{begeleider_naam}** {status_tekst}")
                
                if st.button("✓ OK", key=f"fb_ok_{fb_item['feedback_id']}", help="Bevestig dat je dit gezien hebt"):
                    # Sla op als "bevestigd" - dit betekent dat de speler gezien heeft wat collega zei
                    success = sla_begeleiding_feedback_op(fb_item["feedback_id"], {
                        "wed_id": fb_item["wed_id"],
                        "speler_nbb": nbb_nummer,
                        "begeleider_nbb": fb_item["begeleider_nbb"],
                        "status": "bevestigd",
                        "feedback_datum": datetime.now().isoformat()
                    })
                    if success:
                        st.rerun()
                    else:
                        st.error("Fout bij opslaan. Controleer of de tabel bestaat in Supabase.")
                st.divider()
    
    # Toon feedback enquête voor wedstrijden waar nog geen feedback is
    if wedstrijden_voor_feedback:
        st.warning(f"📋 **Feedback gevraagd over {len(wedstrijden_voor_feedback)} begeleiding(en)**")
        for fb_item in wedstrijden_voor_feedback:
            wed = fb_item["wed"]
            wed_datum = fb_item["wed_datum"]
            begeleider_naam = scheidsrechters.get(fb_item["begeleider_nbb"], {}).get("naam", "Onbekend")
            dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
            
            with st.container():
                st.markdown(f"**{dag} {wed_datum.strftime('%d-%m')}** - {wed['thuisteam']} vs {wed['uitteam']} · Begeleider: **{begeleider_naam}**")
                
                col_select, col_submit = st.columns([3, 1])
                with col_select:
                    feedback_opties = {
                        "": "-- Kies feedback --",
                        "aanwezig_geholpen": "✅ Was aanwezig en heeft geholpen",
                        "aanwezig_niet_geholpen": "⚠️ Was aanwezig maar heeft niet geholpen",
                        "niet_aanwezig": "❌ Is niet komen opdagen"
                    }
                    selectie = st.selectbox(
                        "Feedback",
                        options=list(feedback_opties.keys()),
                        format_func=lambda x: feedback_opties[x],
                        key=f"fb_select_{fb_item['feedback_id']}",
                        label_visibility="collapsed"
                    )
                with col_submit:
                    if st.button("📨 Verstuur", key=f"fb_submit_{fb_item['feedback_id']}", disabled=not selectie):
                        if selectie:
                            sla_begeleiding_feedback_op(fb_item["feedback_id"], {
                                "wed_id": fb_item["wed_id"],
                                "speler_nbb": nbb_nummer,
                                "begeleider_nbb": fb_item["begeleider_nbb"],
                                "status": selectie,
                                "feedback_datum": datetime.now().isoformat()
                            })
                            st.rerun()
                st.divider()
    
    # Toon feedback aan begeleider (als ik begeleider was)
    # Zoek wedstrijden waar ik begeleider was en waar feedback is gegeven
    wedstrijden_als_begeleider = []
    for wed_id, wed in wedstrijden.items():
        if wed.get("geannuleerd", False):
            continue
        if wed.get("begeleider") != nbb_nummer:
            continue
        
        # Is de wedstrijd al gespeeld?
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        wed_eind = wed_datum + timedelta(hours=1, minutes=30)
        if wed_eind > nu:
            continue
        
        # Is er feedback gegeven door scheidsrechters?
        scheids_1 = wed.get("scheids_1")
        scheids_2 = wed.get("scheids_2")
        
        fb_1 = feedback_data.get(f"fb_{wed_id}_{scheids_1}") if scheids_1 else None
        fb_2 = feedback_data.get(f"fb_{wed_id}_{scheids_2}") if scheids_2 else None
        
        # Filter alleen echte feedback (niet "bevestigd")
        if fb_1 and fb_1.get("status") == "bevestigd":
            fb_1 = None
        if fb_2 and fb_2.get("status") == "bevestigd":
            fb_2 = None
        
        # Heb ik als begeleider al bevestigd?
        begeleider_fb_id = f"fb_beg_{wed_id}_{nbb_nummer}"
        al_gezien = feedback_data.get(begeleider_fb_id)
        
        if (fb_1 or fb_2) and not al_gezien:
            wedstrijden_als_begeleider.append({
                "wed_id": wed_id,
                "wed": wed,
                "wed_datum": wed_datum,
                "fb_1": fb_1,
                "fb_2": fb_2,
                "scheids_1": scheids_1,
                "scheids_2": scheids_2,
                "begeleider_fb_id": begeleider_fb_id
            })
    
    if wedstrijden_als_begeleider:
        st.success(f"🎓 **Feedback ontvangen over {len(wedstrijden_als_begeleider)} begeleiding(en)**")
        for item in wedstrijden_als_begeleider:
            wed = item["wed"]
            wed_datum = item["wed_datum"]
            dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
            
            status_tekst = {
                "aanwezig_geholpen": "✅ was aanwezig en heeft geholpen",
                "aanwezig_niet_geholpen": "⚠️ was aanwezig maar heeft niet geholpen",
                "niet_aanwezig": "❌ is niet komen opdagen"
            }
            
            with st.container():
                st.markdown(f"**{dag} {wed_datum.strftime('%d-%m')}** - {wed['thuisteam']} vs {wed['uitteam']}")
                
                # Toon feedback van scheidsrechters
                if item["fb_1"]:
                    scheids_naam = scheidsrechters.get(item["scheids_1"], {}).get("naam", "?")
                    fb_status = item["fb_1"].get("status", "?")
                    st.markdown(f"*{scheids_naam}* gaf aan dat je {status_tekst.get(fb_status, fb_status)}")
                
                if item["fb_2"]:
                    scheids_naam = scheidsrechters.get(item["scheids_2"], {}).get("naam", "?")
                    fb_status = item["fb_2"].get("status", "?")
                    st.markdown(f"*{scheids_naam}* gaf aan dat je {status_tekst.get(fb_status, fb_status)}")
                
                if st.button("✓ OK", key=f"begel_main_ok_{item['wed_id']}", help="Bevestig dat je dit gezien hebt"):
                    # Sla op in database zodat het persistent is
                    sla_begeleiding_feedback_op(item["begeleider_fb_id"], {
                        "wed_id": item["wed_id"],
                        "speler_nbb": nbb_nummer,  # begeleider
                        "begeleider_nbb": nbb_nummer,  # zelfde
                        "status": "begeleider_gezien",
                        "feedback_datum": datetime.now().isoformat()
                    })
                    st.rerun()
                st.divider()
    
    # Toon alerts voor actie-items
    if mijn_klusjes:
        with st.expander(f"🔧 **{len(mijn_klusjes)} open klusje(s)**", expanded=False):
            for klusje in mijn_klusjes:
                st.write(f"• {klusje['naam']} (-{klusje['strikes_waarde']} strike)")
    
    if mijn_uitnodigingen:
        with st.expander(f"🎓 **{len(mijn_uitnodigingen)} begeleidingsuitnodiging(en)**", expanded=True):
            for uitnodiging in mijn_uitnodigingen:
                wed = wedstrijden.get(uitnodiging["wed_id"], {})
                if not wed:
                    continue
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
                mse_naam = scheidsrechters.get(uitnodiging["mse_nbb"], {}).get("naam", "?")
                
                col_info, col_accept, col_reject = st.columns([3, 1, 1])
                with col_info:
                    st.write(f"**{mse_naam}** nodigt je uit: {dag} {wed_datum.strftime('%d-%m %H:%M')} - {wed['thuisteam']} vs {wed['uitteam']}")
                with col_accept:
                    if st.button("✅", key=f"beg_acc_{uitnodiging['id']}", help="Accepteren"):
                        wedstrijden[uitnodiging["wed_id"]]["scheids_2"] = nbb_nummer
                        # Bereken en sla punten op - uitnodiging geeft recht op last-minute bonus
                        punten_info = bereken_punten_voor_wedstrijd(nbb_nummer, uitnodiging["wed_id"], wedstrijden, scheidsrechters, bron="uitnodiging")
                        wedstrijden[uitnodiging["wed_id"]]["scheids_2_punten_berekend"] = punten_info["totaal"]
                        wedstrijden[uitnodiging["wed_id"]]["scheids_2_punten_details"] = punten_info
                        sla_wedstrijd_op(uitnodiging["wed_id"], wedstrijden[uitnodiging["wed_id"]])
                        uitnodigingen[uitnodiging["id"]]["status"] = "accepted"
                        uitnodigingen[uitnodiging["id"]]["bevestigd_op"] = datetime.now().isoformat()
                        sla_begeleidingsuitnodigingen_op(uitnodigingen)
                        st.rerun()
                with col_reject:
                    if st.button("❌", key=f"beg_rej_{uitnodiging['id']}", help="Kan niet"):
                        uitnodigingen[uitnodiging["id"]]["status"] = "rejected"
                        uitnodigingen[uitnodiging["id"]]["afgewezen_op"] = datetime.now().isoformat()
                        sla_begeleidingsuitnodigingen_op(uitnodigingen)
                        st.rerun()
    
    if inkomende_verzoeken:
        with st.expander(f"📨 **{len(inkomende_verzoeken)} vervangingsverzoek(en)**", expanded=True):
            for verzoek in inkomende_verzoeken:
                wed = wedstrijden.get(verzoek["wed_id"], {})
                if not wed:
                    continue
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
                aanvrager = scheidsrechters.get(verzoek["aanvrager_nbb"], {}).get("naam", "?")
                # Preview met vervanging-bonus (omdat dit een vervangingsverzoek is)
                punten_info = bereken_punten_voor_wedstrijd(nbb_nummer, verzoek["wed_id"], wedstrijden, scheidsrechters, bron="vervanging")
                
                col_info, col_accept, col_reject = st.columns([3, 1, 1])
                with col_info:
                    st.write(f"**{aanvrager}** vraagt vervanging: {dag} {wed_datum.strftime('%d-%m %H:%M')} (+{punten_info['totaal']}🏆 na bevestiging)")
                with col_accept:
                    if st.button("✅", key=f"verz_acc_{verzoek['id']}", help="Accepteren"):
                        positie_key = "scheids_1" if verzoek["positie"] == "1e scheidsrechter" else "scheids_2"
                        # Vervanging via uitnodiging: bonus op basis van moment uitnodiging
                        resultaat = schrijf_in_als_scheids(nbb_nummer, verzoek["wed_id"], positie_key, wedstrijden, scheidsrechters, bron="vervanging")
                        if resultaat is None or (isinstance(resultaat, dict) and resultaat.get("error")):
                            naam = resultaat.get("huidige_naam", "iemand anders") if isinstance(resultaat, dict) else "iemand anders"
                            st.error(f"⚠️ Deze positie is al door **{naam}** ingenomen.")
                        else:
                            verzoeken[verzoek["id"]]["status"] = "accepted"
                            verzoeken[verzoek["id"]]["bevestigd_op"] = datetime.now().isoformat()
                            sla_vervangingsverzoeken_op(verzoeken)
                            st.rerun()
                with col_reject:
                    if st.button("❌", key=f"verz_rej_{verzoek['id']}", help="Kan niet"):
                        verzoeken[verzoek["id"]]["status"] = "rejected"
                        verzoeken[verzoek["id"]]["afgewezen_op"] = datetime.now().isoformat()
                        sla_vervangingsverzoeken_op(verzoeken)
                        st.rerun()
    
    # Begeleiding toggle (compact)
    if f"begeleiding_expander_{nbb_nummer}" not in st.session_state:
        st.session_state[f"begeleiding_expander_{nbb_nummer}"] = False
    
    if is_mse:
        # MSE: toon alleen samenvatting van begeleidingen (details in wedstrijdoverzicht)
        nu = datetime.now()
        mijn_begeleidingen = [(wed_id, wed) for wed_id, wed in wedstrijden.items() 
                              if wed.get("begeleider") == nbb_nummer 
                              and datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M") > nu
                              and not wed.get("geannuleerd", False)]
        
        mijn_wed_als_1e_zonder_2e = [(wed_id, wed) for wed_id, wed in wedstrijden.items()
                                     if wed.get("scheids_1") == nbb_nummer 
                                     and not wed.get("scheids_2")
                                     and datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M") > nu
                                     and not wed.get("geannuleerd", False)]
        
        if mijn_begeleidingen or mijn_wed_als_1e_zonder_2e:
            info_parts = []
            if mijn_begeleidingen:
                info_parts.append(f"🎓 {len(mijn_begeleidingen)} begeleiding(en)")
            if mijn_wed_als_1e_zonder_2e:
                info_parts.append(f"📨 {len(mijn_wed_als_1e_zonder_2e)} wed. zonder 2e scheids")
            st.info(" | ".join(info_parts))
    else:
        # Normale speler begeleiding toggle
        begeleiding_label = "🎓 Begeleiding" + (" ✓" if open_voor_begeleiding else "")
        with st.expander(begeleiding_label, expanded=st.session_state[f"begeleiding_expander_{nbb_nummer}"]):
            if not open_voor_begeleiding:
                st.caption("Zet aan om MSE-scheidsrechters je te laten uitnodigen voor samen fluiten")
            
            with st.form("begeleiding_form"):
                nieuwe_open = st.toggle("Open voor begeleiding", value=open_voor_begeleiding)
                
                col_reden, col_tel = st.columns(2)
                with col_reden:
                    nieuwe_reden = st.selectbox("Reden", [""] + BEGELEIDING_REDENEN,
                        index=BEGELEIDING_REDENEN.index(begeleiding_reden) + 1 if begeleiding_reden in BEGELEIDING_REDENEN else 0,
                        label_visibility="collapsed")
                with col_tel:
                    nieuwe_tel = st.text_input("Telefoon (optioneel)", value=telefoon_begeleiding, 
                        placeholder="06-...", label_visibility="collapsed")
                
                if st.form_submit_button("💾 Opslaan", type="primary"):
                    scheidsrechters[nbb_nummer]["open_voor_begeleiding"] = nieuwe_open
                    scheidsrechters[nbb_nummer]["begeleiding_reden"] = nieuwe_reden if nieuwe_open else ""
                    scheidsrechters[nbb_nummer]["telefoon_begeleiding"] = nieuwe_tel if nieuwe_open else ""
                    sla_scheidsrechter_op(nbb_nummer, scheidsrechters[nbb_nummer])
                    st.session_state[f"begeleiding_expander_{nbb_nummer}"] = True
                    st.rerun()
    
    # ============================================================
    # FILTER TOGGLES
    # ============================================================
    
    # Bereken doelmaand voor filter
    deadline_dt = datetime.strptime(instellingen["inschrijf_deadline"], "%Y-%m-%d")
    if deadline_dt.day <= 15:
        doel_maand = deadline_dt.month
        doel_jaar = deadline_dt.year
    else:
        if deadline_dt.month == 12:
            doel_maand = 1
            doel_jaar = deadline_dt.year + 1
        else:
            doel_maand = deadline_dt.month + 1
            doel_jaar = deadline_dt.year
    
    maand_namen_kort = ["", "jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
    maand_namen_lang = ["", "januari", "februari", "maart", "april", "mei", "juni", 
                        "juli", "augustus", "september", "oktober", "november", "december"]
    
    # Tel ingeschreven wedstrijden (alle, inclusief verleden)
    nu = datetime.now()
    aantal_ingeschreven = sum(1 for wed in wedstrijden.values() 
                              if (wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer))
    
    # Tel eigen wedstrijden (thuis + uit) in doelmaand
    eigen_teams = scheids.get("eigen_teams", [])
    aantal_eigen_wed = sum(1 for wed in wedstrijden.values() 
                          if datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M") > nu
                          and not wed.get("geannuleerd", False)
                          and datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M").month == doel_maand
                          and datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M").year == doel_jaar
                          and (any(team_match(wed["thuisteam"], et) for et in eigen_teams) 
                               or any(team_match(wed["uitteam"], et) for et in eigen_teams)))
    
    # Tel BESCHIKBARE wedstrijden per niveau (niet ingeschreven, nog plek vrij, KAN inschrijven)
    aantal_mijn_niveau = 0
    aantal_boven_niveau = 0
    aantal_buiten_maand = 0
    max_niveau_2e = min(eigen_niveau + 1, 5)  # Max niveau als 2e scheids
    
    for wed_id, wed in wedstrijden.items():
        # Skip uitwedstrijden (die zijn voor blokkade, niet voor fluiten)
        if wed.get("type") == "uit":
            continue
            
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        if wed_datum < nu or wed.get("geannuleerd", False):
            continue
        
        # Check of dit een eigen wedstrijd is (waar je zelf speelt)
        is_eigen = (any(team_match(wed["thuisteam"], et) for et in eigen_teams) 
                    or any(team_match(wed["uitteam"], et) for et in eigen_teams))
        
        if is_eigen:
            continue  # Eigen wedstrijden niet meetellen voor niveau filters
        
        # Check of je al ingeschreven bent
        al_ingeschreven = (wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer)
        if al_ingeschreven:
            continue  # Al ingeschreven, niet meer beschikbaar
        
        # Check of er nog plek is en of je kunt inschrijven
        scheids_1_bezet = wed.get("scheids_1") is not None
        scheids_2_bezet = wed.get("scheids_2") is not None
        if scheids_1_bezet and scheids_2_bezet:
            continue  # Geen plek meer
        
        # Extra beschikbaarheid checks
        heeft_eigen = heeft_eigen_wedstrijd(nbb_nummer, wed_datum, wedstrijden, scheidsrechters)
        if heeft_eigen:
            continue  # Eigen wedstrijd op dit tijdstip
        
        heeft_overlap = heeft_overlappende_fluitwedstrijd(nbb_nummer, wed_id, wed_datum, wedstrijden)
        if heeft_overlap:
            continue  # Overlap met andere fluitwedstrijd
        
        zondag_blocked = scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6
        if zondag_blocked:
            continue  # Zondag restrictie
        
        bs2_blocked = wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False)
        if bs2_blocked:
            continue  # BS2 vereist maar geen diploma
        
        wed_niveau = wed.get("niveau", 1)
        is_in_doelmaand = wed_datum.month == doel_maand and wed_datum.year == doel_jaar
        
        # Check of je kunt inschrijven op deze wedstrijd
        kan_als_1e = not scheids_1_bezet and wed_niveau <= eigen_niveau
        kan_als_2e = not scheids_2_bezet
        
        if kan_als_2e and wed_niveau > max_niveau_2e:
            # Boven max niveau voor 2e scheids - check of er MSE als 1e is
            if scheids_1_bezet:
                eerste_scheids = scheidsrechters.get(wed.get("scheids_1"), {})
                is_mse = eerste_scheids.get("niveau_1e_scheids", 1) == 5 or any("MSE" in t.upper() for t in eerste_scheids.get("eigen_teams", []))
                kan_als_2e = is_mse  # Alleen mogelijk met MSE
            else:
                kan_als_2e = False  # Geen 1e scheids, niveau te hoog
        
        kan_inschrijven = kan_als_1e or kan_als_2e
        
        # Check deadline per maand (met weekend uitzondering)
        deadline_open, _ = is_inschrijving_open_incl_weekend(wed_datum, wed)
        if not deadline_open:
            kan_inschrijven = False
        
        if not kan_inschrijven:
            continue  # Kan niet inschrijven, niet meetellen
        
        if is_in_doelmaand:
            if wed_niveau == eigen_niveau:
                aantal_mijn_niveau += 1
            elif wed_niveau > eigen_niveau:
                aantal_boven_niveau += 1
        else:
            aantal_buiten_maand += 1
    
    # Filter toggles (op mobiel onder elkaar via CSS :has selector)
    st.markdown("**Filters:**")
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
    
    with col_f1:
        filter_ingeschreven = st.toggle(f"Ingeschreven ({aantal_ingeschreven})", value=True, key="filter_ingeschreven")
    with col_f2:
        filter_eigen_niveau = st.toggle(f"Mijn niveau ({aantal_mijn_niveau})", value=True, key="filter_eigen_niveau")
    with col_f3:
        filter_boven_niveau = st.toggle(f"Boven niveau ({aantal_boven_niveau})", value=True, key="filter_boven_niveau")
    with col_f4:
        filter_eigen_wedstrijd = st.toggle(f"Mijn wed ({aantal_eigen_wed})", value=True, key="filter_eigen_wedstrijd")
    with col_f5:
        filter_hele_overzicht = st.toggle(f"Hele overzicht (+{aantal_buiten_maand})", value=False, key="filter_hele_overzicht")
    
    # Blauwe lijn boven wedstrijden container (visuele scheiding)
    st.markdown("""
    <div style="
        border-top: 3px solid #003082;
        border-radius: 0.5rem;
        height: 0.5rem;
        margin: 0.5rem 0;
    "></div>
    """, unsafe_allow_html=True)
    
    # Scrollbare container voor wedstrijden
    with st.container(height=600, border=True):
        
        # Toon huidige inschrijvingen (indien filter aan)
        if filter_ingeschreven:
            st.subheader(f"🎯 Ingeschreven ({aantal_ingeschreven})")
    
            mijn_wedstrijden = []
            for wed_id, wed in wedstrijden.items():
                if wed.get("scheids_1") == nbb_nummer:
                    mijn_wedstrijden.append({**wed, "id": wed_id, "rol": "1e scheidsrechter"})
                elif wed.get("scheids_2") == nbb_nummer:
                    mijn_wedstrijden.append({**wed, "id": wed_id, "rol": "2e scheidsrechter"})
    
            if mijn_wedstrijden:
                for wed in sorted(mijn_wedstrijden, key=lambda x: x["datum"]):
                    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                    dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
            
                    # Check of er al een openstaand vervangingsverzoek is
                    verzoeken = laad_vervangingsverzoeken()
                    heeft_openstaand_verzoek = any(
                    v.get("wed_id") == wed["id"] and 
                    v.get("aanvrager_nbb") == nbb_nummer and 
                    v.get("status") == "pending"
                    for v in verzoeken.values()
                    )
            
                    with st.container():
                        col1, col2, col3 = st.columns([2, 3, 2])
                        with col1:
                            st.write(f"**{dag} {wed_datum.strftime('%d-%m %H:%M')}**")
                        with col2:
                            st.write(f"{wed['thuisteam']} - {wed['uitteam']}")
                        with col3:
                            st.write(f"*{wed['rol']}*")
                    
                        if heeft_openstaand_verzoek:
                            st.warning("⏳ Wacht op bevestiging van vervanger...")
                        elif wed_datum > datetime.now():
                            # Afmelden met expander voor opties (alleen voor toekomstige wedstrijden)
                            with st.expander("❌ Afmelden"):
                                st.write("**Hoe wil je afmelden?**")
                            
                                # Bereken hoeveel uur tot de wedstrijd
                                uren_tot_wed = (wed_datum - datetime.now()).total_seconds() / 3600
                            
                                if uren_tot_wed < 48:
                                    if uren_tot_wed < 24:
                                        st.error("⚠️ **Let op:** Afmelden zonder vervanging binnen 24 uur geeft **2 strikes**.")
                                    else:
                                        st.warning("⚠️ **Let op:** Afmelden zonder vervanging binnen 48 uur geeft **1 strike**.")
                            
                                col_zonder, col_met = st.columns(2)
                            
                                with col_zonder:
                                    st.write("**Zonder vervanging**")
                                    strikes_tekst = ""
                                    if uren_tot_wed < 24:
                                        strikes_tekst = " (2 strikes)"
                                    elif uren_tot_wed < 48:
                                        strikes_tekst = " (1 strike)"
                                
                                    if st.button(f"❌ Afmelden{strikes_tekst}", key=f"afmeld_zonder_{wed['id']}", type="secondary"):
                                        positie = "scheids_1" if wed["rol"] == "1e scheidsrechter" else "scheids_2"
                                        punten_kolom = f"{positie}_punten_berekend"
                                        details_kolom = f"{positie}_punten_details"
                                        
                                        # NIEUW: Registreer afmelding VOORDAT we de scheidsrechter verwijderen
                                        registreer_afmelding(wed["id"], nbb_nummer, positie, wedstrijden)
                                        
                                        wedstrijden[wed["id"]][positie] = None
                                        wedstrijden[wed["id"]][punten_kolom] = None
                                        wedstrijden[wed["id"]][details_kolom] = None
                                        sla_wedstrijd_op(wed["id"], wedstrijden[wed["id"]])
                                    
                                        # Log de uitschrijving
                                        try:
                                            db.log_registratie(nbb_nummer, wed["id"], positie, "uitschrijven", wed_datum)
                                        except:
                                            pass
                                    
                                        # Strikes toekennen indien nodig
                                        if uren_tot_wed < 24:
                                            voeg_strike_toe(nbb_nummer, 2, f"Afmelding <24u voor {wed['thuisteam']} vs {wed['uitteam']}")
                                        elif uren_tot_wed < 48:
                                            voeg_strike_toe(nbb_nummer, 1, f"Afmelding <48u voor {wed['thuisteam']} vs {wed['uitteam']}")
                                    
                                        st.rerun()
                            
                                with col_met:
                                    st.write("**Met vervanging** (geen strike)")
                                
                                    # Haal geschikte vervangers op
                                    positie = wed["rol"]
                                    als_eerste = positie == "1e scheidsrechter"
                                    kandidaten = get_kandidaten_voor_wedstrijd(wed["id"], als_eerste)
                                
                                    # Filter jezelf eruit
                                    kandidaten = [k for k in kandidaten if k["nbb_nummer"] != nbb_nummer]
                                
                                    if kandidaten:
                                        vervanger_opties = {
                                            ("😴 " if k.get('is_passief') else "") + f"{k['naam']} ({k['huidig_aantal']} wed)": k['nbb_nummer'] 
                                            for k in kandidaten
                                        }
                                    
                                        geselecteerde = st.selectbox(
                                            "Selecteer vervanger",
                                            options=list(vervanger_opties.keys()),
                                            key=f"vervanger_{wed['id']}"
                                        )
                                    
                                        if st.button("📤 Verstuur verzoek", key=f"verzoek_{wed['id']}", type="primary"):
                                            vervanger_nbb = vervanger_opties[geselecteerde]
                                        
                                            # Maak vervangingsverzoek aan
                                            verzoek_id = f"verz_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                                            verzoeken[verzoek_id] = {
                                                "id": verzoek_id,
                                                "wed_id": wed["id"],
                                                "aanvrager_nbb": nbb_nummer,
                                                "vervanger_nbb": vervanger_nbb,
                                                "positie": positie,
                                                "status": "pending",
                                                "aangemaakt_op": datetime.now().isoformat()
                                            }
                                            sla_vervangingsverzoeken_op(verzoeken)
                                        
                                            vervanger_naam = scheidsrechters.get(vervanger_nbb, {}).get("naam", "")
                                            st.success(f"Verzoek verstuurd naar {vervanger_naam}. Zorg dat die persoon het bevestigt!")
                                            st.rerun()
                                    else:
                                        st.caption("*Geen geschikte vervangers beschikbaar*")
            else:
                st.write("*Je hebt je nog niet ingeschreven voor wedstrijden.*")
    
        st.divider()
    
        # Verzamel eerst alle items om het aantal te kunnen tonen
        eigen_teams = scheids.get("eigen_teams", [])
    
        # Verzamel ALLE wedstrijden (thuiswedstrijden om te fluiten + eigen wedstrijden)
        alle_items = []
    
        for wed_id, wed in wedstrijden.items():
            wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        
            # Skip geannuleerde wedstrijden
            if wed.get("geannuleerd", False):
                continue
        
            # Filter op toekomst
            if wed_datum < datetime.now():
                continue
        
            # Filter op doelmaand indien nodig
            if not filter_hele_overzicht:
                if wed_datum.month != doel_maand or wed_datum.year != doel_jaar:
                    continue
        
            # Check of dit een eigen wedstrijd is
            is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams)
            is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams)
        
            if wed.get("type") == "uit":
                # Uitwedstrijd van eigen team
                if is_eigen_thuis:
                    if not filter_eigen_wedstrijd:
                        continue
                    reistijd = wed.get("reistijd_minuten", 45)
                    terug_tijd = wed_datum + timedelta(minutes=reistijd) + timedelta(hours=1, minutes=30) + timedelta(minutes=reistijd)
                    alle_items.append({
                        "id": wed_id,
                        "type": "eigen_uit",
                        "datum": wed["datum"],
                        "wed_datum": wed_datum,
                        "thuisteam": wed["thuisteam"],
                        "uitteam": wed["uitteam"],
                        "tegenstander": wed["uitteam"],
                        "terug_tijd": terug_tijd
                    })
            else:
                # Thuiswedstrijd
                if is_eigen_thuis or is_eigen_uit:
                    if not filter_eigen_wedstrijd:
                        continue
                    # Eigen thuiswedstrijd (speler speelt zelf)
                    eind_tijd = wed_datum + timedelta(hours=1, minutes=30)
                    alle_items.append({
                        "id": wed_id,
                        "type": "eigen_thuis",
                        "datum": wed["datum"],
                        "wed_datum": wed_datum,
                        "thuisteam": wed["thuisteam"],
                        "uitteam": wed["uitteam"],
                        "eind_tijd": eind_tijd
                    })
                else:
                    # Wedstrijd om te fluiten - pas niveau filters toe
                    wed_niveau = wed.get("niveau", 1)
                    max_niveau_2e = min(eigen_niveau + 1, 5)
                    
                    # Filter op niveau
                    is_eigen_niv = wed_niveau == eigen_niveau
                    is_boven_niv = wed_niveau > eigen_niveau
                    
                    # Check of je kunt inschrijven op deze wedstrijd
                    scheids_1_bezet = wed.get("scheids_1") is not None
                    scheids_2_bezet = wed.get("scheids_2") is not None
                    
                    # Al ingeschreven op andere positie?
                    al_ingeschreven = wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer
                    
                    # Eigen wedstrijd op dit tijdstip?
                    heeft_eigen = heeft_eigen_wedstrijd(nbb_nummer, wed_datum, wedstrijden, scheidsrechters)
                    
                    # Overlap met andere fluitwedstrijd?
                    heeft_overlap = heeft_overlappende_fluitwedstrijd(nbb_nummer, wed_id, wed_datum, wedstrijden)
                    
                    # Zondag restrictie?
                    zondag_blocked = scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6
                    
                    # BS2 vereist maar geen diploma?
                    bs2_blocked = wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False)
                    
                    kan_als_1e = not scheids_1_bezet and wed_niveau <= eigen_niveau
                    kan_als_2e = not scheids_2_bezet
                    
                    if kan_als_2e and wed_niveau > max_niveau_2e:
                        # Boven max niveau voor 2e scheids - check of er MSE als 1e is
                        if scheids_1_bezet:
                            eerste_scheids = scheidsrechters.get(wed.get("scheids_1"), {})
                            is_mse = eerste_scheids.get("niveau_1e_scheids", 1) == 5 or any("MSE" in t.upper() for t in eerste_scheids.get("eigen_teams", []))
                            kan_als_2e = is_mse
                        else:
                            kan_als_2e = False
                    
                    # Combineer alle checks inclusief deadline per maand (met weekend uitzondering)
                    deadline_open, is_weekend_uitzondering = is_inschrijving_open_incl_weekend(wed_datum, wed)
                    kan_inschrijven = (kan_als_1e or kan_als_2e) and not al_ingeschreven and not heeft_eigen and not heeft_overlap and not zondag_blocked and not bs2_blocked and deadline_open
                    
                    # MSE's kunnen ook begeleiden (zonder te fluiten), maar alleen als ze BS2 hebben voor MSE wedstrijden
                    kan_begeleiden = False
                    if is_mse and not heeft_eigen and not heeft_overlap and not al_ingeschreven and not bs2_blocked:
                        al_begeleider = wed.get("begeleider") == nbb_nummer
                        heeft_begeleider = wed.get("begeleider") is not None
                        if not al_begeleider and not heeft_begeleider:
                            kan_begeleiden = True
                    
                    # Kan iets doen met deze wedstrijd?
                    kan_iets = kan_inschrijven or kan_begeleiden or al_ingeschreven or wed.get("begeleider") == nbb_nummer
                    
                    # Check filters
                    if is_eigen_niv and not filter_eigen_niveau:
                        continue
                    if is_boven_niv:
                        if not filter_boven_niveau:
                            continue
                        # Bij "Boven niveau": alleen tonen als je iets kunt doen
                        # Tenzij "Hele overzicht" aan staat
                        if not kan_iets and not filter_hele_overzicht:
                            continue
                    
                    # Ook voor eigen niveau: alleen tonen als je iets kunt doen
                    # Tenzij "Hele overzicht" aan staat
                    if is_eigen_niv and not kan_iets and not filter_hele_overzicht:
                        continue
                    
                    # Onder eigen niveau: ook alleen tonen als je iets kunt doen
                    is_onder_niv = wed_niveau < eigen_niveau
                    if is_onder_niv and not kan_iets and not filter_hele_overzicht:
                        continue
                    
                    alle_items.append({
                        "id": wed_id,
                        "datum": wed["datum"],
                        "wed_datum": wed_datum,
                        "kan_inschrijven": kan_inschrijven,
                        "is_weekend_uitzondering": is_weekend_uitzondering,
                        **wed,
                        "type": "fluiten",  # Na **wed zodat het niet overschreven wordt
                    })
    
        # Sorteer chronologisch
        alle_items = sorted(alle_items, key=lambda x: x["datum"])
        
        # Titel met aantal gefilterde wedstrijden
        if filter_hele_overzicht:
            st.subheader(f"📝 Wedstrijdenoverzicht ({len(alle_items)})")
        else:
            st.subheader(f"📝 Wedstrijdenoverzicht {maand_namen_lang[doel_maand]} ({len(alle_items)})")
    
        if alle_items:
            # Groepeer items per dag
            dagen = {}
            for item in alle_items:
                dag_key = item["wed_datum"].strftime("%Y-%m-%d")
                if dag_key not in dagen:
                    dagen[dag_key] = []
                dagen[dag_key].append(item)
        
            dag_nummer = 0
            for dag_key, dag_items in dagen.items():
                dag_nummer += 1
                eerste_item = dag_items[0]
                wed_datum = eerste_item["wed_datum"]
                dag_naam = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"][wed_datum.weekday()]
                buiten_doelmaand = wed_datum.month != doel_maand or wed_datum.year != doel_jaar
            
                # Afwisselende kleuren voor dag-headers
                if dag_nummer % 2 == 1:
                    header_kleur = "#1e88e5"  # Blauw
                    bg_kleur = "#e3f2fd"
                else:
                    header_kleur = "#ff6b35"  # Oranje
                    bg_kleur = "#fff3e0"
            
                # Dag header met gekleurde balk
                buiten_tekst = " *(buiten periode)*" if buiten_doelmaand else ""
                
                # Bereken beschikbare teams en dag-indicator
                beschikbare_teams = get_beschikbare_teams_voor_dag(wed_datum, dag_items, wedstrijden, scheidsrechters)
                teams_tekst = format_beschikbare_teams(beschikbare_teams)
                dag_emoji, dag_kleur = bereken_dag_indicator(dag_items, wedstrijden, scheidsrechters, nbb_nummer)
                
                st.markdown(f"""
                <div style="background-color: {header_kleur}; color: white; padding: 0.5rem 1rem; border-radius: 0.5rem 0.5rem 0 0; margin-top: 1rem; display: flex; justify-content: space-between; align-items: center;">
                    <div><strong>📆 {dag_naam} {wed_datum.strftime('%d-%m-%Y')}</strong>{buiten_tekst}</div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 0.85rem; opacity: 0.9;">{teams_tekst}</span>
                        <span style="font-size: 1.1rem;">{dag_emoji}</span>
                    </div>
                </div>
                <div style="background-color: {bg_kleur}; padding: 0.5rem; border-radius: 0 0 0.5rem 0.5rem; margin-bottom: 1rem;">
                </div>
                """, unsafe_allow_html=True)
            
                # Container voor dag-inhoud
                with st.container():
                    for item in dag_items:
                        item_datum = item["wed_datum"]
                    
                        if item["type"] == "eigen_uit":
                            # Eigen uitwedstrijd - opvallend blok, tegenstander (thuis) eerst
                            st.warning(f"🚗 **{item_datum.strftime('%H:%M')} - {item['uitteam']}** vs {item['thuisteam']}  \n*Jouw uitwedstrijd • Terug ±{item['terug_tijd'].strftime('%H:%M')}*")
                            
                        elif item["type"] == "eigen_thuis":
                            # Eigen thuiswedstrijd - opvallend blok
                            st.warning(f"🏠 **{item_datum.strftime('%H:%M')} - {item['thuisteam']}** vs {item['uitteam']}  \n*Jouw thuiswedstrijd • Klaar ±{item['eind_tijd'].strftime('%H:%M')}*")
                            
                        else:
                            # Wedstrijd om te fluiten
                            wed = item
                            niveau_tekst = instellingen["niveaus"].get(str(wed["niveau"]), "")
                        
                            # Bepaal of dit een wedstrijd op eigen niveau is
                            eigen_niveau = scheids.get("niveau_1e_scheids", 1)
                            is_eigen_niveau = wed["niveau"] == eigen_niveau
                        
                            # Bepaal status voor 1e scheidsrechter
                            status_1e = bepaal_scheids_status(nbb_nummer, wed, scheids, wedstrijden, scheidsrechters, als_eerste=True)
                        
                            # Bepaal status voor 2e scheidsrechter  
                            status_2e = bepaal_scheids_status(nbb_nummer, wed, scheids, wedstrijden, scheidsrechters, als_eerste=False)
                        
                            # Bereken pool-indicator voor deze wedstrijd
                            pool_size = bereken_pool_voor_wedstrijd(wed["id"], wedstrijden, scheidsrechters)
                            pool_emoji, pool_kleur = get_pool_indicator(pool_size)
                            
                            # Bepaal achtergrondkleur voor pool-badge
                            if pool_size < 5:
                                pool_bg = "#ffebee"  # Licht rood
                                pool_text = "#c62828"
                            elif pool_size <= 8:
                                pool_bg = "#fff3e0"  # Licht oranje
                                pool_text = "#e65100"
                            else:
                                pool_bg = "#e8f5e9"  # Licht groen
                                pool_text = "#2e7d32"
                        
                            # Fluitwedstrijd - prominenter als op eigen niveau
                            if is_eigen_niveau:
                                # Eigen niveau: groene box met ster + pool indicator
                                st.markdown(f"""
                                <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 0.75rem; border-radius: 0 0.5rem 0.5rem 0; margin: 0.5rem 0; display: flex; justify-content: space-between; align-items: center;">
                                    <div>⭐ <strong>{item_datum.strftime('%H:%M')}</strong> · {wed['thuisteam']} - {wed['uitteam']} · <strong>Niveau {wed['niveau']}</strong> <em>(jouw niveau)</em></div>
                                    <div style="background: {pool_bg}; color: {pool_text}; padding: 4px 10px; border-radius: 6px; text-align: center; min-width: 50px;">
                                        <div style="font-size: 1.3rem; font-weight: bold;">{pool_size}</div>
                                        <div style="font-size: 0.65rem; text-transform: uppercase;">pool</div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                # Onder eigen niveau: grijze box (minder prominent) + pool indicator
                                st.markdown(f"""
                                <div style="background-color: #f0f2f6; border-left: 4px solid #6c757d; padding: 0.75rem; border-radius: 0 0.5rem 0.5rem 0; margin: 0.5rem 0; display: flex; justify-content: space-between; align-items: center;">
                                    <div>🏀 <strong>{item_datum.strftime('%H:%M')}</strong> · {wed['thuisteam']} - {wed['uitteam']} · <em>Niveau {wed['niveau']}</em></div>
                                    <div style="background: {pool_bg}; color: {pool_text}; padding: 4px 10px; border-radius: 6px; text-align: center; min-width: 50px;">
                                        <div style="font-size: 1.3rem; font-weight: bold;">{pool_size}</div>
                                        <div style="font-size: 0.65rem; text-transform: uppercase;">pool</div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                        
                            # Scheidsrechter opties
                            col_1e, col_2e = st.columns(2)
                        
                            with col_1e:
                                if status_1e["ingeschreven_zelf"]:
                                    st.markdown(f"🙋 **1e scheids:** Jij")
                                    # Alleen afmelden tonen voor toekomstige wedstrijden
                                    if item_datum > datetime.now() and st.button("❌ Afmelden", key=f"afmeld_1e_{wed['id']}"):
                                        # NIEUW: Registreer afmelding VOORDAT we de scheidsrechter verwijderen
                                        registreer_afmelding(wed["id"], nbb_nummer, "scheids_1", wedstrijden)
                                        
                                        wedstrijden[wed["id"]]["scheids_1"] = None
                                        wedstrijden[wed["id"]]["scheids_1_punten_berekend"] = None
                                        wedstrijden[wed["id"]]["scheids_1_punten_details"] = None
                                        sla_wedstrijd_op(wed["id"], wedstrijden[wed["id"]])
                                        st.rerun()
                                elif status_1e["bezet"]:
                                    # Toon begeleiding indicator voor MSE's
                                    begel_indicator = " 🎓" if is_mse and status_1e.get("wil_begeleiding", False) else ""
                                    st.markdown(f"👤 **1e scheids:** {status_1e['naam']}{begel_indicator}")
                                elif status_1e["beschikbaar"]:
                                    # Bereken potentiële punten als boven minimum
                                    punten_info = None
                                    if op_niveau >= min_wed:
                                        punten_info = bereken_punten_voor_wedstrijd(nbb_nummer, wed['id'], wedstrijden, scheidsrechters)
                                
                                    # Check of dit 2+ niveaus onder eigen niveau is
                                    niveau_verschil = eigen_niveau - wed["niveau"]
                                    is_laag_niveau = niveau_verschil >= 2
                                
                                    button_label = "📋 1e scheids"
                                    if punten_info:
                                        button_label = f"📋 1e scheids (+{punten_info['totaal']}🏆)"
                                
                                    # Check of er een pending bevestiging is voor deze wedstrijd
                                    bevestig_key = f"bevestig_1e_{wed['id']}"
                                
                                    if bevestig_key in st.session_state and st.session_state[bevestig_key]:
                                        # Toon bevestigingsdialoog met alle tussenliggende niveaus
                                        st.warning(f"⚠️ **Let op:** Dit is een niveau {wed['niveau']} wedstrijd, {niveau_verschil} niveaus onder jouw niveau ({eigen_niveau}).")
                                    
                                        # Toon open posities per niveau (van eigen niveau naar beneden tot wedstrijd niveau + 1)
                                        st.write("**Open posities op hogere niveaus:**")
                                        totaal_hoger = 0
                                        for check_niveau in range(eigen_niveau, wed["niveau"], -1):
                                            open_op_niveau = tel_open_posities_op_niveau(nbb_nummer, check_niveau)
                                            totaal_hoger += open_op_niveau['totaal_open']
                                            if open_op_niveau['totaal_open'] > 0:
                                                st.write(f"- Niveau {check_niveau}: **{open_op_niveau['totaal_open']}** open posities")
                                            else:
                                                st.write(f"- Niveau {check_niveau}: geen open posities")
                                    
                                        if totaal_hoger > 0:
                                            st.write(f"")
                                            st.write(f"Er zijn **{totaal_hoger} posities** op hogere niveaus waar jij hard nodig bent!")
                                    
                                        col_ja, col_nee = st.columns(2)
                                        with col_ja:
                                            if st.button("✅ Toch inschrijven", key=f"bevestig_ja_1e_{wed['id']}", type="secondary"):
                                                # Gebruik nieuwe functie: punten worden opgeslagen maar niet toegekend
                                                punten_definitief = schrijf_in_als_scheids(nbb_nummer, wed['id'], "scheids_1", wedstrijden, scheidsrechters)
                                                
                                                if punten_definitief is None or (isinstance(punten_definitief, dict) and punten_definitief.get("error")):
                                                    naam = punten_definitief.get("huidige_naam", "iemand anders") if isinstance(punten_definitief, dict) else "iemand anders"
                                                    toon_error_met_scroll(f"⚠️ Deze positie is zojuist door **{naam}** ingenomen. Ververs de pagina.")
                                                else:
                                                    del st.session_state[bevestig_key]
                                                    st.rerun()
                                        with col_nee:
                                            if st.button("❌ Annuleren", key=f"bevestig_nee_1e_{wed['id']}"):
                                                del st.session_state[bevestig_key]
                                                st.rerun()
                                        
                                        # Scroll naar deze waarschuwing
                                        scroll_naar_warning()
                                    else:
                                        # Normale knop, maar bij laag niveau eerst bevestiging vragen
                                    
                                        if st.button(button_label, key=f"1e_{wed['id']}", type="primary" if is_eigen_niveau else "secondary"):
                                            if is_laag_niveau:
                                                # Vraag bevestiging
                                                st.session_state[bevestig_key] = True
                                                st.rerun()
                                            else:
                                                # Direct inschrijven - punten worden opgeslagen maar niet toegekend
                                                punten_definitief = schrijf_in_als_scheids(nbb_nummer, wed['id'], "scheids_1", wedstrijden, scheidsrechters)
                                                
                                                if punten_definitief is None or (isinstance(punten_definitief, dict) and punten_definitief.get("error")):
                                                    naam = punten_definitief.get("huidige_naam", "iemand anders") if isinstance(punten_definitief, dict) else "iemand anders"
                                                    toon_error_met_scroll(f"⚠️ Deze positie is zojuist door **{naam}** ingenomen. Ververs de pagina.")
                                                else:
                                                    if punten_definitief.get('inval_bonus', 0) > 0:
                                                        st.success(f"""
                                                        ✅ **Ingeschreven!**  
                                                        🕐 Geregistreerd: **{punten_definitief['berekening']['inschrijf_moment_leesbaar']}**  
                                                        ⏱️ {punten_definitief['berekening']['uren_tot_wedstrijd']} uur tot wedstrijd  
                                                        🏆 **{punten_definitief['totaal']} punten** na bevestiging ({punten_definitief['details']})
                                                        """)
                                                    st.rerun()
                                else:
                                    st.caption(f"~~1e scheids~~ *({status_1e['reden']})*")
                        
                            with col_2e:
                                if status_2e["ingeschreven_zelf"]:
                                    st.markdown(f"🙋 **2e scheids:** Jij")
                                    # Alleen afmelden tonen voor toekomstige wedstrijden
                                    if item_datum > datetime.now() and st.button("❌ Afmelden", key=f"afmeld_2e_{wed['id']}"):
                                        # NIEUW: Registreer afmelding VOORDAT we de scheidsrechter verwijderen
                                        registreer_afmelding(wed["id"], nbb_nummer, "scheids_2", wedstrijden)
                                        
                                        wedstrijden[wed["id"]]["scheids_2"] = None
                                        wedstrijden[wed["id"]]["scheids_2_punten_berekend"] = None
                                        wedstrijden[wed["id"]]["scheids_2_punten_details"] = None
                                        sla_wedstrijd_op(wed["id"], wedstrijden[wed["id"]])
                                        st.rerun()
                                elif status_2e["bezet"]:
                                    # Toon begeleiding indicator voor MSE's
                                    begel_indicator = " 🎓" if is_mse and status_2e.get("wil_begeleiding", False) else ""
                                    st.markdown(f"👤 **2e scheids:** {status_2e['naam']}{begel_indicator}")
                                elif status_2e["beschikbaar"]:
                                    # Bereken potentiële punten als boven minimum
                                    punten_info = None
                                    if op_niveau >= min_wed:
                                        punten_info = bereken_punten_voor_wedstrijd(nbb_nummer, wed['id'], wedstrijden, scheidsrechters)
                                
                                    # Check of dit 2+ niveaus onder eigen niveau is
                                    niveau_verschil = eigen_niveau - wed["niveau"]
                                    is_laag_niveau = niveau_verschil >= 2
                                
                                    # Check of dit 1 niveau HOGER is (positieve nudge voor 2e scheids)
                                    is_niveau_hoger = wed["niveau"] == eigen_niveau + 1
                                    heeft_1e_scheids = wed.get("scheids_1") is not None
                                
                                    button_label = "📋 2e scheids"
                                    if punten_info:
                                        button_label = f"📋 2e scheids (+{punten_info['totaal']}🏆)"
                                
                                    # Positieve nudge voor niveau hoger met ervaren 1e scheids
                                    if is_niveau_hoger and heeft_1e_scheids:
                                        eerste_scheids_naam = scheidsrechters.get(wed.get("scheids_1"), {}).get("naam", "ervaren scheids")
                                        st.success(f"⭐ **Kans om hoger te fluiten!** Met {eerste_scheids_naam} als 1e scheids mag jij hier 2e zijn.")
                                
                                    # Check of er een pending bevestiging is voor deze wedstrijd
                                    bevestig_key = f"bevestig_2e_{wed['id']}"
                                
                                    if bevestig_key in st.session_state and st.session_state[bevestig_key]:
                                        # Toon bevestigingsdialoog met alle tussenliggende niveaus
                                        st.warning(f"⚠️ **Let op:** Dit is een niveau {wed['niveau']} wedstrijd, {niveau_verschil} niveaus onder jouw niveau ({eigen_niveau}).")
                                    
                                        # Toon open posities per niveau
                                        st.write("**Open posities op hogere niveaus:**")
                                        totaal_hoger = 0
                                        for check_niveau in range(eigen_niveau, wed["niveau"], -1):
                                            open_op_niveau = tel_open_posities_op_niveau(nbb_nummer, check_niveau)
                                            totaal_hoger += open_op_niveau['totaal_open']
                                            if open_op_niveau['totaal_open'] > 0:
                                                st.write(f"- Niveau {check_niveau}: **{open_op_niveau['totaal_open']}** open posities")
                                            else:
                                                st.write(f"- Niveau {check_niveau}: geen open posities")
                                    
                                        if totaal_hoger > 0:
                                            st.write(f"")
                                            st.write(f"Er zijn **{totaal_hoger} posities** op hogere niveaus waar jij hard nodig bent!")
                                    
                                        col_ja, col_nee = st.columns(2)
                                        with col_ja:
                                            if st.button("✅ Toch inschrijven", key=f"bevestig_ja_2e_{wed['id']}", type="secondary"):
                                                # Gebruik nieuwe functie: punten worden opgeslagen maar niet toegekend
                                                punten_definitief = schrijf_in_als_scheids(nbb_nummer, wed['id'], "scheids_2", wedstrijden, scheidsrechters)
                                                
                                                if punten_definitief is None or (isinstance(punten_definitief, dict) and punten_definitief.get("error")):
                                                    naam = punten_definitief.get("huidige_naam", "iemand anders") if isinstance(punten_definitief, dict) else "iemand anders"
                                                    toon_error_met_scroll(f"⚠️ Deze positie is zojuist door **{naam}** ingenomen. Ververs de pagina.")
                                                else:
                                                    del st.session_state[bevestig_key]
                                                    st.rerun()
                                        with col_nee:
                                            if st.button("❌ Annuleren", key=f"bevestig_nee_2e_{wed['id']}"):
                                                del st.session_state[bevestig_key]
                                                st.rerun()
                                        
                                        # Scroll naar deze waarschuwing
                                        scroll_naar_warning()
                                    else:
                                        # Normale knop, maar bij laag niveau eerst bevestiging vragen
                                    
                                        if st.button(button_label, key=f"2e_{wed['id']}", type="primary" if is_eigen_niveau or (is_niveau_hoger and heeft_1e_scheids) else "secondary"):
                                            if is_laag_niveau:
                                                st.session_state[bevestig_key] = True
                                                st.rerun()
                                            else:
                                                # Direct inschrijven - punten worden opgeslagen maar niet toegekend
                                                punten_definitief = schrijf_in_als_scheids(nbb_nummer, wed['id'], "scheids_2", wedstrijden, scheidsrechters)
                                                
                                                if punten_definitief is None or (isinstance(punten_definitief, dict) and punten_definitief.get("error")):
                                                    naam = punten_definitief.get("huidige_naam", "iemand anders") if isinstance(punten_definitief, dict) else "iemand anders"
                                                    toon_error_met_scroll(f"⚠️ Deze positie is zojuist door **{naam}** ingenomen. Ververs de pagina.")
                                                else:
                                                    if punten_definitief.get('inval_bonus', 0) > 0:
                                                        st.success(f"""
                                                        ✅ **Ingeschreven!**  
                                                        🕐 Geregistreerd: **{punten_definitief['berekening']['inschrijf_moment_leesbaar']}**  
                                                        ⏱️ {punten_definitief['berekening']['uren_tot_wedstrijd']} uur tot wedstrijd  
                                                        🏆 **{punten_definitief['totaal']} punten** na bevestiging ({punten_definitief['details']})
                                                        """)
                                                    st.rerun()
                                else:
                                    st.caption(f"~~2e scheids~~ *({status_2e['reden']})*")
                                
                                # Toon begeleider indien aanwezig
                                begeleider_nbb = wed.get("begeleider")
                                if begeleider_nbb:
                                    begeleider_naam = scheidsrechters.get(begeleider_nbb, {}).get("naam", "Onbekend")
                                    if begeleider_nbb == nbb_nummer:
                                        col_beg_info, col_beg_afmeld = st.columns([3, 1])
                                        with col_beg_info:
                                            st.markdown(f"🎓 **Begeleider:** Jij")
                                        with col_beg_afmeld:
                                            # Alleen afmelden tonen voor toekomstige wedstrijden
                                            if item_datum > datetime.now() and st.button("❌", key=f"afmeld_beg_{wed['id']}", help="Afmelden als begeleider"):
                                                wedstrijden[wed["id"]]["begeleider"] = None
                                                sla_wedstrijd_op(wed["id"], wedstrijden[wed["id"]])
                                                st.rerun()
                                    else:
                                        st.markdown(f"🎓 **Begeleider:** {begeleider_naam}")
                                elif is_mse:
                                    # MSE opties: begeleider aanmelden of speler uitnodigen
                                    al_scheids = (wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer)
                                    
                                    if status_1e["ingeschreven_zelf"] and not wed.get("scheids_2"):
                                        # MSE is 1e scheids, kan speler uitnodigen als 2e
                                        spelers_voor_begeleiding = [(s_nbb, s) for s_nbb, s in scheidsrechters.items() 
                                                                     if s_nbb != nbb_nummer and s.get("open_voor_begeleiding", False)]
                                        mse_uitnodigingen = laad_begeleidingsuitnodigingen()
                                        bestaande = next((u for u in mse_uitnodigingen.values() 
                                                         if u.get("wed_id") == wed["id"] and u.get("status") == "pending"), None)
                                        
                                        if bestaande:
                                            uitgenodigde = scheidsrechters.get(bestaande["speler_nbb"], {})
                                            st.caption(f"📨 Uitnodiging verstuurd naar {uitgenodigde.get('naam', '?')}")
                                        else:
                                            beschikbaar = [(s_nbb, s) for s_nbb, s in spelers_voor_begeleiding 
                                                           if is_beschikbaar_voor_begeleiding(s_nbb, wed["id"], wedstrijden, scheidsrechters)[0]]
                                            if beschikbaar:
                                                opties = {f"{s['naam']}": s_nbb for s_nbb, s in beschikbaar}
                                                col_sel, col_btn = st.columns([3, 1])
                                                with col_sel:
                                                    selectie = st.selectbox("Uitnodigen:", [""] + list(opties.keys()), 
                                                                          key=f"mse_sel_{wed['id']}", label_visibility="collapsed")
                                                with col_btn:
                                                    if st.button("📨", key=f"mse_btn_{wed['id']}", disabled=not selectie, help="Uitnodigen"):
                                                        if selectie:
                                                            uitn_id = f"beg_{wed['id']}_{opties[selectie]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                                                            mse_uitnodigingen[uitn_id] = {
                                                                "id": uitn_id, "wed_id": wed["id"], "mse_nbb": nbb_nummer,
                                                                "speler_nbb": opties[selectie], "status": "pending",
                                                                "aangemaakt": datetime.now().isoformat()
                                                            }
                                                            sla_begeleidingsuitnodigingen_op(mse_uitnodigingen)
                                                            st.rerun()
                                    elif not al_scheids:
                                        # MSE kan zich aanmelden als begeleider, maar niet bij eigen wedstrijd
                                        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                                        heeft_eigen = heeft_eigen_wedstrijd(nbb_nummer, wed_datum, wedstrijden, scheidsrechters)
                                        if not heeft_eigen:
                                            if st.button("🎓 Begeleider", key=f"beg_aanmeld_{wed['id']}", help="Aanmelden als begeleider (niet fluiten)"):
                                                wedstrijden[wed["id"]]["begeleider"] = nbb_nummer
                                                sla_wedstrijd_op(wed["id"], wedstrijden[wed["id"]])
                                                st.rerun()

# ============================================================
# BEHEERDER VIEW
# ============================================================

def toon_beheerder_view():
    """Toon het beheerderspaneel."""
    # IP info in sidebar
    with st.sidebar:
        st.markdown("### 🔧 Beheerder")
        ip_info = db.get_ip_info()
        with st.expander("🌍 Netwerk info"):
            st.write(f"**Publiek IP:** {ip_info['ip']}")
            st.write(f"**Land:** {ip_info['country']}")
            st.write(f"**Header:** {ip_info.get('used_header', '?')}")
            if ip_info['allowed']:
                st.success("✅ Toegang OK")
            else:
                st.error("❌ Geblokkeerd")
    
    # Header met logo en refresh knop
    logo_path = Path(__file__).parent / "logo.png"
    if logo_path.exists():
        col_logo, col_title, col_refresh = st.columns([1, 3, 1])
        with col_logo:
            st.image(str(logo_path), width=100)
        with col_title:
            st.title("Beheerder - Scheidsrechter Planning")
            st.caption(f"Ref Planner v{APP_VERSIE}")
        with col_refresh:
            st.write("")  # Spacing
            if st.button("🔄 Ververs data", help="Laad alle data opnieuw uit de database"):
                # Clear alle database caches
                cache_keys = [key for key in st.session_state.keys() if key.startswith("_db_cache_")]
                for key in cache_keys:
                    del st.session_state[key]
                st.rerun()
    else:
        col_title, col_refresh = st.columns([4, 1])
        with col_title:
            st.title("🔧 Beheerder - Scheidsrechter Planning")
            st.caption(f"Ref Planner v{APP_VERSIE}")
        with col_refresh:
            st.write("")  # Spacing
            if st.button("🔄 Ververs data", help="Laad alle data opnieuw uit de database"):
                # Clear alle database caches
                cache_keys = [key for key in st.session_state.keys() if key.startswith("_db_cache_")]
                for key in cache_keys:
                    del st.session_state[key]
                st.rerun()
    
    # Statistieken berekenen
    wedstrijden = laad_wedstrijden()
    nu = datetime.now()
    
    # Bepaal weekend grenzen (komende za-zo)
    dagen_tot_zaterdag = (5 - nu.weekday()) % 7
    if dagen_tot_zaterdag == 0 and nu.weekday() != 5:
        dagen_tot_zaterdag = 7
    weekend_start = (nu + timedelta(days=dagen_tot_zaterdag)).replace(hour=0, minute=0, second=0, microsecond=0)
    weekend_eind = weekend_start + timedelta(days=2)
    
    # Bepaal maand grenzen
    maand_start = nu.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if nu.month == 12:
        maand_eind = maand_start.replace(year=nu.year + 1, month=1)
    else:
        maand_eind = maand_start.replace(month=nu.month + 1)
    
    # Tellers initialiseren
    stats = {
        "totaal": {"te_spelen": 0, "niet_compleet": 0},
        "weekend": {"te_spelen": 0, "niet_compleet": 0},
        "maand": {"te_spelen": 0, "niet_compleet": 0}
    }
    
    for wed_id, wed in wedstrijden.items():
        # Alleen thuiswedstrijden
        if wed.get("type", "thuis") != "thuis":
            continue
        if wed.get("geannuleerd", False):
            continue
        
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        
        # Nog te spelen?
        if wed_datum > nu:
            is_compleet = wed.get("scheids_1") and wed.get("scheids_2")
            
            # Totaal
            stats["totaal"]["te_spelen"] += 1
            if not is_compleet:
                stats["totaal"]["niet_compleet"] += 1
            
            # Weekend check
            if weekend_start <= wed_datum < weekend_eind:
                stats["weekend"]["te_spelen"] += 1
                if not is_compleet:
                    stats["weekend"]["niet_compleet"] += 1
            
            # Maand check (rest van deze maand)
            if nu <= wed_datum < maand_eind:
                stats["maand"]["te_spelen"] += 1
                if not is_compleet:
                    stats["maand"]["niet_compleet"] += 1
    
    # Bereken percentages
    def calc_pct(te_spelen, niet_compleet):
        if te_spelen > 0:
            return round((te_spelen - niet_compleet) / te_spelen * 100)
        return 100
    
    # Toon statistieken in 3 blokken
    st.markdown("##### 📊 Bezetting")
    col_weekend, col_maand, col_totaal = st.columns(3)
    
    with col_weekend:
        weekend_pct = calc_pct(stats["weekend"]["te_spelen"], stats["weekend"]["niet_compleet"])
        weekend_label = f"🗓️ Weekend ({weekend_start.strftime('%d/%m')})"
        if stats["weekend"]["te_spelen"] == 0:
            st.metric(weekend_label, "Geen wedstrijden")
        elif stats["weekend"]["niet_compleet"] == 0:
            st.metric(weekend_label, f"✅ {stats['weekend']['te_spelen']} wedstrijden", "Compleet!")
        else:
            st.metric(weekend_label, f"{stats['weekend']['niet_compleet']} open", 
                     f"van {stats['weekend']['te_spelen']} ({weekend_pct}% compleet)")
    
    with col_maand:
        maand_pct = calc_pct(stats["maand"]["te_spelen"], stats["maand"]["niet_compleet"])
        maand_naam = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"][nu.month - 1]
        if stats["maand"]["te_spelen"] == 0:
            st.metric(f"📅 Rest {maand_naam}", "Geen wedstrijden")
        elif stats["maand"]["niet_compleet"] == 0:
            st.metric(f"📅 Rest {maand_naam}", f"✅ {stats['maand']['te_spelen']} wedstrijden", "Compleet!")
        else:
            st.metric(f"📅 Rest {maand_naam}", f"{stats['maand']['niet_compleet']} open",
                     f"van {stats['maand']['te_spelen']} ({maand_pct}% compleet)")
    
    with col_totaal:
        totaal_pct = calc_pct(stats["totaal"]["te_spelen"], stats["totaal"]["niet_compleet"])
        if stats["totaal"]["te_spelen"] == 0:
            st.metric("📆 Hele seizoen", "Geen wedstrijden")
        else:
            st.metric("📆 Hele seizoen", f"{totaal_pct}% compleet",
                     f"{stats['totaal']['niet_compleet']} open van {stats['totaal']['te_spelen']}")
    
    # Beheerder opties in sidebar
    with st.sidebar:
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔓 Uitloggen", use_container_width=True):
                st.session_state.beheerder_ingelogd = False
                st.rerun()
        with col2:
            if st.button("🔑 Wachtwoord", use_container_width=True, help="Wachtwoord wijzigen"):
                st.session_state.moet_wachtwoord_wijzigen = True
                st.rerun()
    
    st.divider()
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "📅 Wedstrijden", 
        "👥 Scheidsrechters", 
        "📈 Capaciteit",
        "🏆 Beloningen",
        "✅ Bevestigen",
        "📊 Analyse",
        "🖼️ Weekend Overzicht",
        "⚙️ Instellingen",
        "📊 Import/Export",
        "🔐 Apparaten"
    ])
    
    with tab1:
        toon_wedstrijden_beheer()
    
    with tab2:
        toon_scheidsrechters_beheer()
    
    with tab3:
        toon_capaciteit_monitor()
    
    with tab4:
        toon_beloningen_beheer()
    
    with tab5:
        toon_bevestigen_wedstrijden()
    
    with tab6:
        toon_analyse_dashboard()
    
    with tab7:
        toon_weekend_overzicht()
    
    with tab8:
        toon_instellingen_beheer()
    
    with tab9:
        toon_import_export()
    
    with tab10:
        toon_apparaten_beheer()

def toon_bevestigen_wedstrijden():
    """TC scherm voor het bevestigen van gespeelde wedstrijden."""
    st.subheader("✅ Wedstrijden Bevestigen")
    st.caption("Bevestig dat scheidsrechters hebben gefloten om punten toe te kennen")
    
    # Uitleg
    with st.expander("ℹ️ Hoe werkt dit?"):
        st.markdown("""
        **Proces na de wedstrijd:**
        1. Spelers schrijven zich in → punten worden **berekend** maar nog niet toegekend
        2. Na de wedstrijd bevestigt TC wie er was
        3. **Gefloten** → punten worden toegekend
        4. **No-show (zonder invaller)** → strikes worden toegekend
        5. **No-show met invaller** → strikes voor no-show + bonuspunten voor invaller
        
        **Scenario's:**
        - ✅ Scheids was aanwezig → "Gefloten"
        - ❌ Scheids niet verschenen, wedstrijd niet doorgegaan → "No-show"
        - 🔄 Scheids niet verschenen, iemand anders heeft ingevallen → "No-show met invaller"
        """)
    
    # Haal wedstrijden op die bevestigd moeten worden
    te_bevestigen = get_te_bevestigen_wedstrijden()
    
    if not te_bevestigen:
        st.success("🎉 Alle gespeelde wedstrijden zijn bevestigd!")
        st.info("Zodra er wedstrijden zijn gespeeld met scheidsrechters, verschijnen ze hier voor bevestiging.")
        return
    
    # Statistieken
    totaal_open = sum(1 for w in te_bevestigen for pos in ["scheids_1_open", "scheids_2_open"] if w.get(pos))
    st.metric("Te bevestigen posities", totaal_open)
    
    st.divider()
    
    # Bulk acties
    col_bulk1, col_bulk2 = st.columns(2)
    with col_bulk1:
        if st.button("✅ Alles als 'Gefloten' markeren", type="primary", help="Markeer alle openstaande posities als gefloten"):
            count = 0
            for wed in te_bevestigen:
                if wed["scheids_1_open"]:
                    bevestig_wedstrijd_gefloten(wed["wed_id"], "scheids_1", "TC (bulk)")
                    count += 1
                if wed["scheids_2_open"]:
                    bevestig_wedstrijd_gefloten(wed["wed_id"], "scheids_2", "TC (bulk)")
                    count += 1
            st.success(f"✅ {count} posities bevestigd als gefloten!")
            st.rerun()
    
    with col_bulk2:
        st.caption("Of bevestig individueel hieronder:")
    
    st.divider()
    
    # Toon wedstrijden per datum
    huidige_datum = None
    for wed in te_bevestigen:
        wed_datum = wed["wed_datum"]
        datum_str = wed_datum.strftime("%A %d %B %Y")
        
        # Nieuwe datum header
        if datum_str != huidige_datum:
            if huidige_datum is not None:
                st.divider()
            st.markdown(f"### 📅 {datum_str}")
            huidige_datum = datum_str
        
        # Wedstrijd info
        with st.container():
            st.markdown(f"**{wed_datum.strftime('%H:%M')}** - {wed['thuisteam']} vs {wed['uitteam']} (niveau {wed['niveau']})")
            
            col1, col2 = st.columns(2)
            
            # Haal alle scheidsrechters op voor invaller selectie
            scheidsrechters = laad_scheidsrechters()
            
            # 1e scheids
            with col1:
                if wed["scheids_1"]:
                    status_icon = "⏳" if wed["scheids_1_open"] else "✅" if wed["scheids_1_status"] == "gefloten" else "❌"
                    st.write(f"**1e scheids:** {wed['scheids_1_naam']} {status_icon}")
                    
                    if wed["scheids_1_open"]:
                        punten = wed.get("scheids_1_punten", 0)
                        st.caption(f"Berekende punten: {punten}")
                        
                        if st.button("✅ Gefloten", key=f"gefloten_1_{wed['wed_id']}", type="primary", use_container_width=True):
                            bevestig_wedstrijd_gefloten(wed["wed_id"], "scheids_1", "TC")
                            st.success(f"✅ {wed['scheids_1_naam']} bevestigd - {punten} punten toegekend")
                            st.rerun()
                        
                        if st.button("❌ No-show (zonder invaller)", key=f"noshow_1_{wed['wed_id']}", type="secondary", use_container_width=True):
                            markeer_no_show(wed["wed_id"], "scheids_1", "TC")
                            beloningsinst = laad_beloningsinstellingen()
                            strikes = beloningsinst.get("strikes_no_show", 5)
                            st.error(f"❌ {wed['scheids_1_naam']} no-show - {strikes} strikes toegekend")
                            st.rerun()
                        
                        # No-show met invaller
                        with st.expander("🔄 No-show met invaller"):
                            # Filter: alle scheidsrechters behalve de huidige
                            mogelijke_invallers = {
                                nbb: s.get("naam", "Onbekend") 
                                for nbb, s in scheidsrechters.items() 
                                if nbb != wed["scheids_1"] and nbb != wed.get("scheids_2")
                            }
                            
                            if mogelijke_invallers:
                                invaller_opties = {f"{naam} ({nbb})": nbb for nbb, naam in mogelijke_invallers.items()}
                                geselecteerde_invaller = st.selectbox(
                                    "Wie heeft ingevallen?",
                                    options=list(invaller_opties.keys()),
                                    key=f"invaller_1_{wed['wed_id']}"
                                )
                                
                                beloningsinst = laad_beloningsinstellingen()
                                inval_punten = beloningsinst.get("punten_per_wedstrijd", 1) + beloningsinst.get("punten_inval_24u", 5)
                                st.caption(f"Invaller krijgt: ~{inval_punten}+ punten")
                                
                                if st.button("⚡ Verwerk no-show + invaller", key=f"noshow_inv_1_{wed['wed_id']}", type="primary"):
                                    invaller_nbb = invaller_opties[geselecteerde_invaller]
                                    resultaat = markeer_no_show_met_invaller(wed["wed_id"], "scheids_1", invaller_nbb, "TC")
                                    if resultaat:
                                        st.success(f"✅ Verwerkt: {resultaat['oorspronkelijke_scheids']} → {resultaat['strikes']} strikes")
                                        st.success(f"✅ Invaller {resultaat['invaller']} → {resultaat['punten']} punten")
                                    st.rerun()
                            else:
                                st.caption("Geen andere scheidsrechters beschikbaar")
            
            # 2e scheids
            with col2:
                if wed["scheids_2"]:
                    status_icon = "⏳" if wed["scheids_2_open"] else "✅" if wed["scheids_2_status"] == "gefloten" else "❌"
                    st.write(f"**2e scheids:** {wed['scheids_2_naam']} {status_icon}")
                    
                    if wed["scheids_2_open"]:
                        punten = wed.get("scheids_2_punten", 0)
                        st.caption(f"Berekende punten: {punten}")
                        
                        if st.button("✅ Gefloten", key=f"gefloten_2_{wed['wed_id']}", type="primary", use_container_width=True):
                            bevestig_wedstrijd_gefloten(wed["wed_id"], "scheids_2", "TC")
                            st.success(f"✅ {wed['scheids_2_naam']} bevestigd - {punten} punten toegekend")
                            st.rerun()
                        
                        if st.button("❌ No-show (zonder invaller)", key=f"noshow_2_{wed['wed_id']}", type="secondary", use_container_width=True):
                            markeer_no_show(wed["wed_id"], "scheids_2", "TC")
                            beloningsinst = laad_beloningsinstellingen()
                            strikes = beloningsinst.get("strikes_no_show", 5)
                            st.error(f"❌ {wed['scheids_2_naam']} no-show - {strikes} strikes toegekend")
                            st.rerun()
                        
                        # No-show met invaller
                        with st.expander("🔄 No-show met invaller"):
                            # Filter: alle scheidsrechters behalve de huidige
                            mogelijke_invallers = {
                                nbb: s.get("naam", "Onbekend") 
                                for nbb, s in scheidsrechters.items() 
                                if nbb != wed["scheids_2"] and nbb != wed.get("scheids_1")
                            }
                            
                            if mogelijke_invallers:
                                invaller_opties = {f"{naam} ({nbb})": nbb for nbb, naam in mogelijke_invallers.items()}
                                geselecteerde_invaller = st.selectbox(
                                    "Wie heeft ingevallen?",
                                    options=list(invaller_opties.keys()),
                                    key=f"invaller_2_{wed['wed_id']}"
                                )
                                
                                beloningsinst = laad_beloningsinstellingen()
                                inval_punten = beloningsinst.get("punten_per_wedstrijd", 1) + beloningsinst.get("punten_inval_24u", 5)
                                st.caption(f"Invaller krijgt: ~{inval_punten}+ punten")
                                
                                if st.button("⚡ Verwerk no-show + invaller", key=f"noshow_inv_2_{wed['wed_id']}", type="primary"):
                                    invaller_nbb = invaller_opties[geselecteerde_invaller]
                                    resultaat = markeer_no_show_met_invaller(wed["wed_id"], "scheids_2", invaller_nbb, "TC")
                                    if resultaat:
                                        st.success(f"✅ Verwerkt: {resultaat['oorspronkelijke_scheids']} → {resultaat['strikes']} strikes")
                                        st.success(f"✅ Invaller {resultaat['invaller']} → {resultaat['punten']} punten")
                                    st.rerun()
                            else:
                                st.caption("Geen andere scheidsrechters beschikbaar")

def toon_analyse_dashboard():
    """Dashboard voor analyse van fluitgedrag en minimum bepaling."""
    st.subheader("📊 Analyse Dashboard")
    st.caption("Inzicht in fluitgedrag voor het bepalen van minimums")
    
    scheidsrechters = laad_scheidsrechters()
    wedstrijden = laad_wedstrijden()
    beloningen = laad_beloningen()
    nu = datetime.now()
    
    # Tel gefloten wedstrijden per scheidsrechter
    gefloten_data = {}
    for nbb in scheidsrechters.keys():
        gefloten_data[nbb] = {
            "totaal": 0,
            "als_1e": 0,
            "als_2e": 0,
            "op_niveau": 0,
            "onder_niveau": 0,
            "boven_niveau": 0
        }
    
    for wed_id, wed in wedstrijden.items():
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        if wed_datum > nu:
            continue  # Alleen gespeelde wedstrijden
        
        wed_niveau = wed.get("niveau", 1)
        
        scheids_1 = wed.get("scheids_1")
        scheids_2 = wed.get("scheids_2")
        
        if scheids_1 and scheids_1 in gefloten_data:
            gefloten_data[scheids_1]["totaal"] += 1
            gefloten_data[scheids_1]["als_1e"] += 1
            eigen_niveau = scheidsrechters.get(scheids_1, {}).get("niveau_1e_scheids", 1)
            if wed_niveau == eigen_niveau:
                gefloten_data[scheids_1]["op_niveau"] += 1
            elif wed_niveau < eigen_niveau:
                gefloten_data[scheids_1]["onder_niveau"] += 1
            else:
                gefloten_data[scheids_1]["boven_niveau"] += 1
        
        if scheids_2 and scheids_2 in gefloten_data:
            gefloten_data[scheids_2]["totaal"] += 1
            gefloten_data[scheids_2]["als_2e"] += 1
            eigen_niveau = scheidsrechters.get(scheids_2, {}).get("niveau_1e_scheids", 1)
            max_2e_niveau = min(eigen_niveau + 1, 5)
            if wed_niveau <= eigen_niveau:
                gefloten_data[scheids_2]["op_niveau"] += 1
            elif wed_niveau <= max_2e_niveau:
                gefloten_data[scheids_2]["onder_niveau"] += 1
            else:
                gefloten_data[scheids_2]["boven_niveau"] += 1
    
    # Maak analyse lijst
    analyse_lijst = []
    for nbb, scheids in scheidsrechters.items():
        min_wed = scheids.get("min_wedstrijden", 0)
        gefloten = gefloten_data.get(nbb, {}).get("totaal", 0)
        verschil = gefloten - min_wed
        
        bel_data = beloningen.get("spelers", {}).get(nbb, {})
        
        analyse_lijst.append({
            "nbb": nbb,
            "naam": scheids.get("naam", ""),
            "niveau": scheids.get("niveau_1e_scheids", 1),
            "min_wedstrijden": min_wed,
            "gefloten": gefloten,
            "verschil": verschil,
            "als_1e": gefloten_data.get(nbb, {}).get("als_1e", 0),
            "als_2e": gefloten_data.get(nbb, {}).get("als_2e", 0),
            "op_niveau": gefloten_data.get(nbb, {}).get("op_niveau", 0),
            "punten": bel_data.get("punten", 0),
            "strikes": bel_data.get("strikes", 0)
        })
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    veel_fluiten = [s for s in analyse_lijst if s["verschil"] >= 3]
    weinig_fluiten = [s for s in analyse_lijst if s["verschil"] < 0]
    precies_goed = [s for s in analyse_lijst if 0 <= s["verschil"] < 3]
    niet_gefloten = [s for s in analyse_lijst if s["gefloten"] == 0 and s["min_wedstrijden"] > 0]
    
    with col1:
        st.metric("🌟 Veel fluiten (+3)", len(veel_fluiten), help="Kandidaten voor lager minimum")
    with col2:
        st.metric("✅ Op schema", len(precies_goed))
    with col3:
        st.metric("⚠️ Achter op schema", len(weinig_fluiten), help="Nog niet aan minimum")
    with col4:
        st.metric("❌ Niet gefloten", len(niet_gefloten), help="Spelers die nog niet gefloten hebben")
    
    st.divider()
    
    # Tabs voor verschillende views
    tab_veel, tab_weinig, tab_allemaal, tab_gedrag = st.tabs(["🌟 Veel fluiten", "⚠️ Weinig fluiten", "📋 Alle scheidsrechters", "📈 Inschrijfgedrag"])
    
    with tab_veel:
        st.markdown("### Kandidaten voor lager minimum")
        st.caption("Spelers die minstens 3 wedstrijden boven hun minimum fluiten")
        
        if veel_fluiten:
            veel_sorted = sorted(veel_fluiten, key=lambda x: x["verschil"], reverse=True)
            
            for speler in veel_sorted[:20]:
                with st.expander(f"🌟 **{speler['naam']}** — Gefloten: {speler['gefloten']} | Min: {speler['min_wedstrijden']} | +{speler['verschil']}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**Niveau:** {speler['niveau']}")
                        st.write(f"**Als 1e scheids:** {speler['als_1e']}")
                        st.write(f"**Als 2e scheids:** {speler['als_2e']}")
                    with col_b:
                        st.write(f"**Punten:** {speler['punten']}")
                        st.write(f"**Strikes:** {speler['strikes']}")
                        st.write(f"**Op eigen niveau:** {speler['op_niveau']}")
                    
                    # Suggestie voor nieuw minimum
                    nieuw_min = max(0, speler["min_wedstrijden"] - 1)
                    if speler["verschil"] >= 5:
                        nieuw_min = max(0, speler["min_wedstrijden"] - 2)
                    
                    if nieuw_min < speler["min_wedstrijden"]:
                        st.info(f"💡 Suggestie: Verlaag minimum naar **{nieuw_min}**")
                        
                        if st.button(f"📝 Pas minimum aan naar {nieuw_min}", key=f"adj_min_{speler['nbb']}"):
                            scheids = scheidsrechters[speler["nbb"]]
                            scheids["min_wedstrijden"] = nieuw_min
                            sla_scheidsrechter_op(speler["nbb"], scheids)
                            st.success(f"Minimum aangepast naar {nieuw_min}")
                            st.rerun()
        else:
            st.info("Geen spelers met +3 boven minimum")
    
    with tab_weinig:
        st.markdown("### Spelers die weinig fluiten")
        st.caption("Spelers die hun minimum nog niet gehaald hebben")
        
        if weinig_fluiten:
            weinig_sorted = sorted(weinig_fluiten, key=lambda x: x["verschil"])
            
            for speler in weinig_sorted[:20]:
                status_icon = "❌" if speler["gefloten"] == 0 else "⚠️"
                with st.expander(f"{status_icon} **{speler['naam']}** — Gefloten: {speler['gefloten']} | Min: {speler['min_wedstrijden']} | {speler['verschil']}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**Niveau:** {speler['niveau']}")
                        st.write(f"**Nog nodig:** {abs(speler['verschil'])}")
                    with col_b:
                        st.write(f"**Punten:** {speler['punten']}")
                        st.write(f"**Strikes:** {speler['strikes']}")
                    
                    if speler["gefloten"] == 0:
                        st.warning("⚠️ Heeft dit seizoen nog niet gefloten!")
        else:
            st.success("Iedereen heeft het minimum gehaald! 🎉")
    
    with tab_allemaal:
        st.markdown("### Alle scheidsrechters")
        
        # Sorteer opties
        sorteer = st.selectbox(
            "Sorteer op",
            ["Naam", "Gefloten (hoog-laag)", "Gefloten (laag-hoog)", "Verschil (hoog-laag)", "Verschil (laag-hoog)", "Niveau"],
            key="sorteer_analyse"
        )
        
        if sorteer == "Naam":
            analyse_sorted = sorted(analyse_lijst, key=lambda x: x["naam"])
        elif sorteer == "Gefloten (hoog-laag)":
            analyse_sorted = sorted(analyse_lijst, key=lambda x: x["gefloten"], reverse=True)
        elif sorteer == "Gefloten (laag-hoog)":
            analyse_sorted = sorted(analyse_lijst, key=lambda x: x["gefloten"])
        elif sorteer == "Verschil (hoog-laag)":
            analyse_sorted = sorted(analyse_lijst, key=lambda x: x["verschil"], reverse=True)
        elif sorteer == "Verschil (laag-hoog)":
            analyse_sorted = sorted(analyse_lijst, key=lambda x: x["verschil"])
        else:  # Niveau
            analyse_sorted = sorted(analyse_lijst, key=lambda x: (x["niveau"], x["naam"]))
        
        # Tabel weergave
        st.markdown("| Naam | Niv | Min | Gefloten | Verschil | 1e | 2e | Punten |")
        st.markdown("|------|-----|-----|----------|----------|-----|-----|--------|")
        
        for speler in analyse_sorted:
            verschil_str = f"+{speler['verschil']}" if speler['verschil'] >= 0 else str(speler['verschil'])
            if speler['verschil'] >= 3:
                verschil_str = f"🌟 {verschil_str}"
            elif speler['verschil'] < 0:
                verschil_str = f"⚠️ {verschil_str}"
            
            st.markdown(f"| {speler['naam']} | {speler['niveau']} | {speler['min_wedstrijden']} | {speler['gefloten']} | {verschil_str} | {speler['als_1e']} | {speler['als_2e']} | {speler['punten']} |")
    
    with tab_gedrag:
        st.markdown("### 📈 Inschrijfgedrag Analyse")
        st.caption("Wanneer schrijven spelers zich in? Vergelijk top performers met probleemgevallen.")
        
        # Haal inschrijf statistieken op
        inschrijf_stats = db.get_inschrijf_statistieken()
        
        if not inschrijf_stats:
            st.info("""
            📊 **Nog geen data beschikbaar**
            
            Inschrijfgedrag wordt bijgehouden vanaf nu. Na enkele weken zie je hier:
            - Gemiddeld aantal dagen vooruit dat spelers zich inschrijven
            - Vergelijking tussen top 3 punten vs. spelers met strikes
            - Patronen: early birds vs. last-minute inschrijvers
            """)
        else:
            # Combineer met beloningen data
            gedrag_analyse = []
            for nbb, stats in inschrijf_stats.items():
                scheids = scheidsrechters.get(nbb, {})
                bel_data = beloningen.get("spelers", {}).get(nbb, {})
                
                gedrag_analyse.append({
                    "nbb": nbb,
                    "naam": scheids.get("naam", "Onbekend"),
                    "punten": bel_data.get("punten", 0),
                    "strikes": bel_data.get("strikes", 0),
                    **stats
                })
            
            # Sorteer op punten (top 3) en strikes (probleemgevallen)
            top_3 = sorted([g for g in gedrag_analyse if g["punten"] > 0], 
                          key=lambda x: x["punten"], reverse=True)[:3]
            probleemgevallen = sorted([g for g in gedrag_analyse if g["strikes"] >= 3], 
                                      key=lambda x: x["strikes"], reverse=True)[:5]
            
            # Vergelijking metrics
            col_top, col_probleem = st.columns(2)
            
            with col_top:
                st.markdown("#### 🏆 Top 3 (meeste punten)")
                if top_3:
                    gem_dagen_top = sum(g["gem_dagen_voor_wedstrijd"] for g in top_3) / len(top_3)
                    gem_early_top = sum(g["early_bird_pct"] for g in top_3) / len(top_3)
                    
                    st.metric("Gem. dagen vooruit", f"{gem_dagen_top:.1f} dagen")
                    st.metric("Early bird %", f"{gem_early_top:.0f}%", 
                             help="Inschrijvingen >7 dagen van tevoren")
                    
                    for speler in top_3:
                        st.markdown(f"**{speler['naam']}** ({speler['punten']} ptn)")
                        st.caption(f"↳ {speler['gem_dagen_voor_wedstrijd']} dagen vooruit | "
                                  f"{speler['early_bird_pct']}% early bird")
                else:
                    st.caption("*Nog geen punten uitgedeeld*")
            
            with col_probleem:
                st.markdown("#### ⚠️ Probleemgevallen (3+ strikes)")
                if probleemgevallen:
                    gem_dagen_prob = sum(g["gem_dagen_voor_wedstrijd"] for g in probleemgevallen) / len(probleemgevallen)
                    gem_lastmin_prob = sum(g["last_minute_pct"] for g in probleemgevallen) / len(probleemgevallen)
                    
                    st.metric("Gem. dagen vooruit", f"{gem_dagen_prob:.1f} dagen")
                    st.metric("Last-minute %", f"{gem_lastmin_prob:.0f}%",
                             help="Inschrijvingen <3 dagen van tevoren")
                    
                    for speler in probleemgevallen:
                        st.markdown(f"**{speler['naam']}** ({speler['strikes']} strikes)")
                        st.caption(f"↳ {speler['gem_dagen_voor_wedstrijd']} dagen vooruit | "
                                  f"{speler['last_minute_pct']}% last-minute")
                else:
                    st.success("*Geen spelers met 3+ strikes*")
            
            st.divider()
            
            # Alle spelers tabel
            st.markdown("#### 📋 Overzicht alle spelers")
            
            # Sorteer opties
            sorteer_gedrag = st.selectbox(
                "Sorteer op",
                ["Gem. dagen vooruit (hoog-laag)", "Gem. dagen vooruit (laag-hoog)", 
                 "Last-minute % (hoog-laag)", "Punten", "Strikes"],
                key="sorteer_gedrag"
            )
            
            if sorteer_gedrag == "Gem. dagen vooruit (hoog-laag)":
                gedrag_sorted = sorted(gedrag_analyse, key=lambda x: x["gem_dagen_voor_wedstrijd"], reverse=True)
            elif sorteer_gedrag == "Gem. dagen vooruit (laag-hoog)":
                gedrag_sorted = sorted(gedrag_analyse, key=lambda x: x["gem_dagen_voor_wedstrijd"])
            elif sorteer_gedrag == "Last-minute % (hoog-laag)":
                gedrag_sorted = sorted(gedrag_analyse, key=lambda x: x["last_minute_pct"], reverse=True)
            elif sorteer_gedrag == "Punten":
                gedrag_sorted = sorted(gedrag_analyse, key=lambda x: x["punten"], reverse=True)
            else:  # Strikes
                gedrag_sorted = sorted(gedrag_analyse, key=lambda x: x["strikes"], reverse=True)
            
            st.markdown("| Naam | Gem. dagen | Inschrijvingen | Early bird | Last-minute | Punten | Strikes |")
            st.markdown("|------|------------|----------------|------------|-------------|--------|---------|")
            
            for speler in gedrag_sorted:
                eb_indicator = "🐦" if speler["early_bird_pct"] >= 50 else ""
                lm_indicator = "⚠️" if speler["last_minute_pct"] >= 50 else ""
                
                st.markdown(f"| {speler['naam']} | {speler['gem_dagen_voor_wedstrijd']} | "
                           f"{speler['aantal_inschrijvingen']} | {speler['early_bird_pct']}% {eb_indicator} | "
                           f"{speler['last_minute_pct']}% {lm_indicator} | {speler['punten']} | {speler['strikes']} |")
    
    st.divider()
    
    # Bulk minimum aanpassen
    st.markdown("### 🔧 Bulk minimum aanpassen")
    st.caption("Pas minimums aan voor meerdere spelers tegelijk")
    
    with st.expander("Bulk aanpassingen"):
        col_bulk1, col_bulk2 = st.columns(2)
        
        with col_bulk1:
            st.markdown("**Verlaag minimum voor veel fluiters:**")
            st.caption(f"{len(veel_fluiten)} spelers met +3 boven minimum")
            
            if veel_fluiten and st.button("📉 Verlaag minimum (-1) voor alle veel fluiters", key="bulk_verlaag"):
                count = 0
                for speler in veel_fluiten:
                    if speler["min_wedstrijden"] > 0:
                        scheids = scheidsrechters[speler["nbb"]]
                        scheids["min_wedstrijden"] = max(0, scheids.get("min_wedstrijden", 0) - 1)
                        sla_scheidsrechter_op(speler["nbb"], scheids)
                        count += 1
                st.success(f"Minimum verlaagd voor {count} spelers")
                st.rerun()
        
        with col_bulk2:
            st.markdown("**Verhoog minimum voor weinig fluiters:**")
            actieve_weinig = [s for s in weinig_fluiten if s["gefloten"] > 0]
            st.caption(f"{len(actieve_weinig)} spelers die wel gefloten hebben maar onder minimum")
            
            if actieve_weinig and st.button("📈 Verhoog minimum (+1) voor weinig fluiters", key="bulk_verhoog"):
                count = 0
                for speler in actieve_weinig:
                    scheids = scheidsrechters[speler["nbb"]]
                    scheids["min_wedstrijden"] = scheids.get("min_wedstrijden", 0) + 1
                    sla_scheidsrechter_op(speler["nbb"], scheids)
                    count += 1
                st.success(f"Minimum verhoogd voor {count} spelers")
                st.rerun()

def toon_apparaten_beheer():
    """Beheer van gekoppelde apparaten per speler."""
    st.subheader("🔐 Apparaatbeheer")
    
    # Statistieken
    stats = db.get_device_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Totaal apparaten", stats["total_devices"])
    with col2:
        st.metric("Spelers met apparaat", stats["unique_spelers"])
    with col3:
        st.metric("Spelers met verificatie", stats["spelers_met_geboortedatum"], 
                  help="Spelers met geboortedatum in systeem")
    with col4:
        st.metric("Wachtend op goedkeuring", stats["pending_approvals"])
    
    st.divider()
    
    # Alle devices ophalen
    all_devices = db.get_all_devices()
    scheidsrechters = laad_scheidsrechters()
    
    if not all_devices:
        st.info("Nog geen apparaten gekoppeld.")
        return
    
    # Groepeer per speler
    devices_per_speler = {}
    for device in all_devices:
        speler_id = device["speler_id"]
        if speler_id not in devices_per_speler:
            devices_per_speler[speler_id] = []
        devices_per_speler[speler_id].append(device)
    
    # Zoekfunctie
    zoek = st.text_input("🔍 Zoek speler (naam of NBB-nummer)", key="zoek_apparaat")
    
    # Filter opties
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        toon_pending = st.checkbox("Alleen wachtend op goedkeuring", key="filter_pending")
    
    # Filter op zoekterm
    gefilterde_spelers = list(devices_per_speler.keys())
    if zoek:
        zoek_lower = zoek.lower()
        gefilterde_spelers = [
            speler_id for speler_id in devices_per_speler.keys()
            if zoek_lower in speler_id.lower() or 
               zoek_lower in scheidsrechters.get(speler_id, {}).get("naam", "").lower()
        ]
    
    # Filter op pending
    if toon_pending:
        gefilterde_spelers = [
            speler_id for speler_id in gefilterde_spelers
            if any(not d.get("approved", True) for d in devices_per_speler[speler_id])
        ]
    
    # Toon per speler
    for speler_id in sorted(gefilterde_spelers, key=lambda x: scheidsrechters.get(x, {}).get("naam", x)):
        devices = devices_per_speler[speler_id]
        speler_naam = scheidsrechters.get(speler_id, {}).get("naam", "Onbekend")
        pending_count = sum(1 for d in devices if not d.get("approved", True))
        
        label = f"**{speler_naam}** ({speler_id}) - {len(devices)} apparaat{'en' if len(devices) != 1 else ''}"
        if pending_count > 0:
            label += f" ⏳ {pending_count} wachtend"
        
        with st.expander(label):
            for device in devices:
                col_info, col_status, col_delete = st.columns([3, 1, 1])
                
                with col_info:
                    device_name = device.get("device_name", "Onbekend apparaat")
                    fingerprint = device.get("fingerprint", "")[:8] if device.get("fingerprint") else ""
                    created = db.format_datetime(device.get("created_at", ""))
                    last_used = db.format_datetime(device.get("last_used", ""))
                    
                    st.markdown(f"📱 **{device_name}**")
                    if fingerprint:
                        st.caption(f"ID: {fingerprint} · Gekoppeld: {created}")
                    else:
                        st.caption(f"Gekoppeld: {created}")
                    st.caption(f"Laatst gebruikt: {last_used}")
                
                with col_status:
                    if device.get("approved", True):
                        st.success("✅ Actief")
                    else:
                        st.warning("⏳ Wachtend")
                
                with col_delete:
                    if st.button("🗑️", key=f"admin_del_{device['id']}", help="Verwijder apparaat"):
                        if db.remove_device_admin(device["id"]):
                            st.success(f"Apparaat verwijderd!")
                            st.rerun()
                        else:
                            st.error("Fout bij verwijderen")
                
                st.divider()
    
    # Bulk acties
    st.divider()
    st.markdown("### ⚠️ Bulk acties")
    
    with st.expander("Alle apparaten van een speler verwijderen"):
        speler_opties = {
            f"{scheidsrechters.get(sid, {}).get('naam', 'Onbekend')} ({sid})": sid 
            for sid in devices_per_speler.keys()
        }
        
        if speler_opties:
            geselecteerde = st.selectbox("Selecteer speler", options=list(speler_opties.keys()))
            
            if geselecteerde:
                speler_id = speler_opties[geselecteerde]
                aantal = len(devices_per_speler[speler_id])
                
                st.warning(f"Dit verwijdert {aantal} apparaat{'en' if aantal != 1 else ''} van {geselecteerde}")
                
                if st.button(f"🗑️ Verwijder alle {aantal} apparaten", type="primary"):
                    for device in devices_per_speler[speler_id]:
                        db.remove_device_admin(device["id"])
                    st.success(f"Alle apparaten van {geselecteerde} verwijderd!")
                    st.rerun()

def genereer_overzicht_afbeelding(datum: datetime, wedstrijden_data: list, scheidsrechters: dict) -> bytes:
    """Genereer een PNG afbeelding van het scheidsrechteroverzicht."""
    
    # Configuratie
    breedte = 850
    header_hoogte = 100
    rij_hoogte = 55
    kolom_breedtes = [65, 65, 300, 340]  # Tijd, Veld, Wedstrijd, Scheidsrechters
    
    # Bereken hoogte
    aantal_rijen = len(wedstrijden_data)
    hoogte = header_hoogte + 40 + (aantal_rijen + 1) * rij_hoogte + 20  # +1 voor header rij
    
    # Kleuren
    header_kleur = (70, 130, 180)  # Steel blue
    header_tekst = (255, 255, 255)
    tabel_header_bg = (70, 130, 180)
    rij_even = (245, 245, 245)
    rij_oneven = (255, 255, 255)
    rand_kleur = (200, 200, 200)
    tekst_kleur = (50, 50, 50)
    label_kleur = (100, 100, 100)  # Grijs voor "1e:" en "2e:" labels
    
    # Maak afbeelding
    img = Image.new('RGB', (breedte, hoogte), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Probeer fonts te laden
    try:
        font_groot = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_normaal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        font_datum = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf", 16)
        font_klein = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except:
        font_groot = ImageFont.load_default()
        font_normaal = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_datum = ImageFont.load_default()
        font_klein = ImageFont.load_default()
    
    # Header achtergrond
    draw.rectangle([0, 0, breedte, header_hoogte], fill=header_kleur)
    
    # Titel
    titel = "SCHEIDSRECHTEROVERZICHT"
    bbox = draw.textbbox((0, 0), titel, font=font_groot)
    titel_breedte = bbox[2] - bbox[0]
    draw.text(((breedte - titel_breedte) / 2, 20), titel, fill=header_tekst, font=font_groot)
    
    # Datum
    dag_namen = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
    maand_namen = ["januari", "februari", "maart", "april", "mei", "juni", 
                   "juli", "augustus", "september", "oktober", "november", "december"]
    datum_tekst = f"{dag_namen[datum.weekday()]} {datum.day} {maand_namen[datum.month-1]} {datum.year}"
    bbox = draw.textbbox((0, 0), datum_tekst, font=font_datum)
    datum_breedte = bbox[2] - bbox[0]
    draw.text(((breedte - datum_breedte) / 2, 60), datum_tekst, fill=header_tekst, font=font_datum)
    
    # Tabel start positie
    tabel_start_y = header_hoogte + 20
    margin_left = 30
    
    # Tabel header
    x = margin_left
    y = tabel_start_y
    headers = ["Tijd", "Veld", "Wedstrijd", "Scheidsrechters"]
    
    # Header achtergrond
    draw.rectangle([margin_left, y, breedte - margin_left, y + rij_hoogte], fill=tabel_header_bg)
    
    for i, (header, width) in enumerate(zip(headers, kolom_breedtes)):
        # Tekst centreren in kolom
        bbox = draw.textbbox((0, 0), header, font=font_bold)
        tekst_breedte = bbox[2] - bbox[0]
        tekst_x = x + (width - tekst_breedte) / 2
        draw.text((tekst_x, y + 18), header, fill=header_tekst, font=font_bold)
        x += width
    
    # Data rijen
    y += rij_hoogte
    for idx, wed in enumerate(wedstrijden_data):
        geannuleerd = wed.get("geannuleerd", False)
        
        # Achtergrond kleur
        if geannuleerd:
            bg_kleur = (255, 204, 204)  # Licht rood voor geannuleerd
        else:
            bg_kleur = rij_even if idx % 2 == 0 else rij_oneven
        draw.rectangle([margin_left, y, breedte - margin_left, y + rij_hoogte], fill=bg_kleur)
        
        # Horizontale lijn
        draw.line([margin_left, y, breedte - margin_left, y], fill=rand_kleur, width=1)
        
        x = margin_left
        
        # Tijd
        tijd_tekst = wed["tijd"]
        bbox = draw.textbbox((0, 0), tijd_tekst, font=font_normaal)
        tekst_breedte = bbox[2] - bbox[0]
        draw.text((x + (kolom_breedtes[0] - tekst_breedte) / 2, y + 18), tijd_tekst, fill=tekst_kleur, font=font_normaal)
        x += kolom_breedtes[0]
        
        # Veld
        veld_tekst = wed.get("veld", "-")
        bbox = draw.textbbox((0, 0), veld_tekst, font=font_normaal)
        tekst_breedte = bbox[2] - bbox[0]
        draw.text((x + (kolom_breedtes[1] - tekst_breedte) / 2, y + 18), veld_tekst, fill=tekst_kleur, font=font_normaal)
        x += kolom_breedtes[1]
        
        # Wedstrijd (2 regels)
        wed_tekst1 = wed["thuisteam"]
        wed_tekst2 = wed["uitteam"]
        wed_tekst_kleur = (136, 136, 136) if geannuleerd else tekst_kleur  # Grijs als geannuleerd
        draw.text((x + 8, y + 8), wed_tekst1, fill=wed_tekst_kleur, font=font_normaal)
        draw.text((x + 8, y + 28), wed_tekst2, fill=wed_tekst_kleur, font=font_normaal)
        x += kolom_breedtes[2]
        
        # Scheidsrechters (2 regels: 1e en 2e) of GEANNULEERD
        if geannuleerd:
            annuleer_kleur = (204, 0, 0)  # Rood
            draw.text((x + 8, y + 18), "GEANNULEERD", fill=annuleer_kleur, font=font_bold)
        else:
            scheids_1 = wed.get("scheids_1", "-")
            scheids_2 = wed.get("scheids_2", "-")
            draw.text((x + 8, y + 8), f"1e: {scheids_1}", fill=tekst_kleur, font=font_klein)
            draw.text((x + 8, y + 28), f"2e: {scheids_2}", fill=tekst_kleur, font=font_klein)
        
        y += rij_hoogte
    
    # Laatste lijn
    draw.line([margin_left, y, breedte - margin_left, y], fill=rand_kleur, width=1)
    
    # Rand om hele tabel
    draw.rectangle([margin_left, tabel_start_y, breedte - margin_left, y], outline=rand_kleur, width=2)
    
    # Verticale lijnen
    x = margin_left
    for width in kolom_breedtes[:-1]:
        x += width
        draw.line([x, tabel_start_y, x, y], fill=rand_kleur, width=1)
    
    # Opslaan naar bytes
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.getvalue()

def genereer_open_posities_alert(weekend_dagen: list, wedstrijden: dict, scheidsrechters: dict) -> bytes:
    """
    Genereer een alert-stijl afbeelding met open scheidsrechtersposities.
    Teams met ** worden extra benadrukt als kritiek (no-show risico).
    """
    from PIL import Image, ImageDraw, ImageFont
    
    # Verzamel wedstrijden met open posities
    open_wedstrijden = []
    for dag in weekend_dagen:
        for wed_id, wed in wedstrijden.items():
            if wed.get("type") == "uit" or wed.get("geannuleerd"):
                continue
            try:
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
            except:
                continue
            
            if wed_datum.date() != dag:
                continue
            
            # Check open posities en zoekt vervanging status
            open_1e = not wed.get("scheids_1")
            open_2e = not wed.get("scheids_2")
            zoekt_1e = wed.get("scheids_1_zoekt_vervanging", False) and wed.get("scheids_1")
            zoekt_2e = wed.get("scheids_2_zoekt_vervanging", False) and wed.get("scheids_2")
            
            # Toon als er een open positie is OF iemand zoekt vervanging
            if open_1e or open_2e or zoekt_1e or zoekt_2e:
                # Check of dit een kritiek team is (met **)
                thuisteam = wed.get("thuisteam", "")
                is_kritiek = "**" in thuisteam
                
                # Niveau van de wedstrijd
                wed_niveau = wed.get("niveau", 1)
                # 2e scheids mag 1 niveau lager (maar minimaal 1)
                niveau_2e = max(1, wed_niveau - 1)
                
                open_wedstrijden.append({
                    "datum": wed_datum,
                    "dag": ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()],
                    "tijd": wed_datum.strftime("%H:%M"),
                    "thuisteam": thuisteam,
                    "uitteam": wed.get("uitteam", ""),
                    "open_1e": open_1e,
                    "open_2e": open_2e,
                    "zoekt_1e": zoekt_1e,
                    "zoekt_2e": zoekt_2e,
                    "is_kritiek": is_kritiek,
                    "niveau": wed_niveau,
                    "niveau_1e": wed_niveau,
                    "niveau_2e": niveau_2e
                })
    
    # Sorteer: kritiek eerst, dan op datum/tijd
    open_wedstrijden.sort(key=lambda x: (not x["is_kritiek"], x["datum"]))
    
    # Tel statistieken
    totaal_wedstrijden = len(open_wedstrijden)
    totaal_open = sum(1 for w in open_wedstrijden if w["open_1e"]) + sum(1 for w in open_wedstrijden if w["open_2e"])
    totaal_zoekt = sum(1 for w in open_wedstrijden if w["zoekt_1e"]) + sum(1 for w in open_wedstrijden if w["zoekt_2e"])
    totaal_posities = totaal_open + totaal_zoekt
    kritieke_wedstrijden = sum(1 for w in open_wedstrijden if w["is_kritiek"])
    
    # Afmetingen
    width = 450
    header_height = 100
    stats_height = 70
    row_height = 80
    warning_height = 60
    footer_height = 50
    
    content_height = len(open_wedstrijden) * row_height if open_wedstrijden else 60
    height = header_height + stats_height + content_height + warning_height + footer_height + 40
    
    # Kleuren
    bg_color = (26, 26, 26)
    header_orange = (255, 102, 0)
    critical_red = (255, 51, 51)
    text_white = (255, 255, 255)
    text_gray = (136, 136, 136)
    card_bg = (42, 42, 42)
    
    # Maak afbeelding
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Probeer fonts te laden
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_subtitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        font_number = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except:
        font_title = ImageFont.load_default()
        font_subtitle = font_title
        font_normal = font_title
        font_bold = font_title
        font_small = font_title
        font_number = font_title
    
    y = 0
    
    # Header met gradient
    draw.rectangle([0, 0, width, header_height], fill=header_orange)
    
    # Alert icoon
    draw.text((width//2, 20), "🚨", font=font_title, anchor="mt", fill=text_white)
    draw.text((width//2, 50), "SCHEIDSRECHTERS GEZOCHT!", font=font_title, anchor="mt", fill=text_white)
    
    # Weekend datum
    if weekend_dagen:
        start_dag = min(weekend_dagen)
        eind_dag = max(weekend_dagen)
        if start_dag == eind_dag:
            datum_str = f"{start_dag.strftime('%d %B')}"
        else:
            datum_str = f"Weekend {start_dag.strftime('%d')}-{eind_dag.strftime('%d %B')}"
        draw.text((width//2, 78), datum_str, font=font_subtitle, anchor="mt", fill=(255, 255, 255, 200))
    
    y = header_height + 15
    
    # Statistieken
    stat_width = width // 3
    stats = [
        (str(totaal_wedstrijden), "Wedstrijden", header_orange),
        (str(totaal_posities), "Open posities", header_orange),
        (str(kritieke_wedstrijden), "Kritiek ⚠️", critical_red if kritieke_wedstrijden > 0 else header_orange)
    ]
    
    for i, (number, label, color) in enumerate(stats):
        x = stat_width * i + stat_width // 2
        draw.text((x, y), number, font=font_number, anchor="mt", fill=color)
        draw.text((x, y + 32), label, font=font_small, anchor="mt", fill=text_gray)
    
    y += stats_height
    
    # Wedstrijden
    if not open_wedstrijden:
        draw.text((width//2, y + 20), "Geen open posities! 🎉", font=font_normal, anchor="mt", fill=text_white)
        y += 60
    else:
        for wed in open_wedstrijden:
            # Card achtergrond
            card_color = (60, 30, 30) if wed["is_kritiek"] else card_bg
            border_color = critical_red if wed["is_kritiek"] else header_orange
            
            draw.rectangle([15, y, width-15, y + row_height - 8], fill=card_color)
            draw.rectangle([15, y, 19, y + row_height - 8], fill=border_color)
            
            # Tijd
            tijd_color = critical_red if wed["is_kritiek"] else header_orange
            draw.text((30, y + 10), f"{wed['dag']} {wed['tijd']}", font=font_bold, fill=tijd_color)
            
            # Niveau badge (rechts naast tijd)
            niveau_tekst = f"Niv.{wed['niveau']}"
            draw.text((width - 70, y + 10), niveau_tekst, font=font_bold, fill=text_gray)
            
            # Kritiek badge
            if wed["is_kritiek"]:
                badge_x = width - 60
                draw.rectangle([badge_x, y + 28, width - 20, y + 44], fill=critical_red)
                draw.text((badge_x + 20, y + 36), "⚠️ **", font=font_small, anchor="mm", fill=text_white)
            
            # Teams
            thuisteam_display = wed["thuisteam"].replace("**", "").strip()
            draw.text((30, y + 30), thuisteam_display, font=font_normal, fill=text_white)
            draw.text((30, y + 46), f"vs {wed['uitteam']}", font=font_small, fill=text_gray)
            
            # Open posities en zoekt vervanging
            pos_y = y + 62
            pos_x = 30
            pos_color = (255, 150, 100) if not wed["is_kritiek"] else (255, 100, 100)
            zoekt_color = (255, 200, 100)  # Geel/oranje voor zoekt vervanging
            
            if wed["open_1e"]:
                draw.text((pos_x, pos_y), f"• 1e scheids nodig (niv.{wed['niveau_1e']})", font=font_small, fill=pos_color)
                pos_x += 165
            elif wed.get("zoekt_1e"):
                draw.text((pos_x, pos_y), f"• 1e zoekt vervanger (niv.{wed['niveau_1e']})", font=font_small, fill=zoekt_color)
                pos_x += 185
            
            if wed["open_2e"]:
                draw.text((pos_x, pos_y), f"• 2e scheids nodig (niv.{wed['niveau_2e']})", font=font_small, fill=pos_color)
            elif wed.get("zoekt_2e"):
                draw.text((pos_x, pos_y), f"• 2e zoekt vervanger (niv.{wed['niveau_2e']})", font=font_small, fill=zoekt_color)
            
            y += row_height
    
    # Waarschuwing box (alleen als er kritieke wedstrijden zijn)
    if kritieke_wedstrijden > 0:
        y += 5
        draw.rectangle([15, y, width-15, y + warning_height - 10], fill=(60, 30, 30), outline=(100, 50, 50))
        draw.text((25, y + 12), "⚠️ ** = Team heeft al no-show gehad", font=font_small, fill=(255, 100, 100))
        draw.text((25, y + 28), "Nog een no-show = uitsluiting competitie!", font=font_small, fill=(255, 150, 150))
        y += warning_height
    
    # Footer
    y += 10
    draw.rectangle([0, y, width, height], fill=(34, 34, 34))
    draw.text((width//2, y + 20), "Inschrijven via BOB App of TC", font=font_normal, anchor="mt", fill=text_gray)
    
    # Sla op als PNG
    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()

def toon_weekend_overzicht():
    """Genereer een weekend overzicht als afbeelding."""
    st.subheader("Weekend Overzicht Generator")
    
    if not PIL_AVAILABLE:
        st.error("PIL/Pillow is niet geïnstalleerd. Installeer met: pip install Pillow")
        return
    
    wedstrijden = laad_wedstrijden()
    scheidsrechters = laad_scheidsrechters()
    
    # Vind beschikbare datums en groepeer per weekend
    datums_met_wedstrijden = set()
    for wed_id, wed in wedstrijden.items():
        if wed.get("type") == "uit":
            continue
        try:
            wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
            if wed_datum > datetime.now() - timedelta(days=7):  # Afgelopen week + toekomst
                datums_met_wedstrijden.add(wed_datum.date())
        except:
            continue
    
    if not datums_met_wedstrijden:
        st.warning("Geen wedstrijden gevonden.")
        return
    
    # Groepeer in weekenden (zaterdag + zondag)
    weekenden = {}
    for d in sorted(datums_met_wedstrijden):
        # Vind de zaterdag van dit weekend
        if d.weekday() == 5:  # Zaterdag
            zaterdag = d
        elif d.weekday() == 6:  # Zondag
            zaterdag = d - timedelta(days=1)
        else:
            # Doordeweeks - toon als losse dag
            weekenden[d.strftime('%d-%m-%Y')] = {"label": f"{['Ma','Di','Wo','Do','Vr','Za','Zo'][d.weekday()]} {d.strftime('%d-%m-%Y')}", "dagen": [d]}
            continue
        
        zondag = zaterdag + timedelta(days=1)
        weekend_key = f"{zaterdag.strftime('%d-%m')}"
        
        if weekend_key not in weekenden:
            weekenden[weekend_key] = {
                "label": f"Weekend {zaterdag.strftime('%d')}/{zondag.strftime('%d-%m-%Y')}",
                "dagen": []
            }
        
        if d not in weekenden[weekend_key]["dagen"]:
            weekenden[weekend_key]["dagen"].append(d)
    
    # Sorteer weekenden
    weekend_lijst = sorted(weekenden.items(), key=lambda x: min(x[1]["dagen"]))
    weekend_labels = [v["label"] for k, v in weekend_lijst]
    weekend_dagen_lijst = [v["dagen"] for k, v in weekend_lijst]
    
    # Weekend selectie
    st.markdown("**Selecteer weekend**")
    
    # Gebruik index voor betere tracking
    gekozen_index = st.selectbox(
        "Kies een weekend", 
        range(len(weekend_labels)),
        format_func=lambda i: weekend_labels[i],
        key="weekend_selectie_idx"
    )
    
    gekozen_weekend = weekend_labels[gekozen_index]
    gekozen_dagen = sorted(weekend_dagen_lijst[gekozen_index])
    
    # Debug: toon welke dagen geselecteerd zijn
    st.caption(f"📅 Geselecteerd: {', '.join([d.strftime('%d-%m-%Y') for d in gekozen_dagen])}")
    
    # Toon info over geselecteerde dagen
    dag_namen_lang = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
    maand_namen = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
    
    if len(gekozen_dagen) > 1:
        st.info(f"📅 Dit weekend heeft wedstrijden op **{len(gekozen_dagen)} dagen**: {', '.join([dag_namen_lang[d.weekday()] for d in gekozen_dagen])}")
    
    st.markdown("---")
    
    # Helper functie om wedstrijden voor een dag op te halen
    def get_wedstrijden_voor_dag(datum):
        dag_wedstrijden = []
        for wed_id, wed in wedstrijden.items():
            if wed.get("type") == "uit":
                continue
            try:
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
            except:
                continue
                
            if wed_datum.date() == datum:
                geannuleerd = wed.get("geannuleerd", False)
                
                if geannuleerd:
                    scheids_1_naam = "GEANNULEERD"
                    scheids_2_naam = "GEANNULEERD"
                else:
                    scheids_1_naam = "-"
                    scheids_2_naam = "-"
                    
                    if wed.get("scheids_1"):
                        scheids_1 = scheidsrechters.get(wed["scheids_1"], {})
                        team_info = scheids_1.get("eigen_teams", [])
                        team_str = f"({team_info[0]})" if team_info else ""
                        scheids_1_naam = f"{scheids_1.get('naam', 'Onbekend')} {team_str}".strip()
                    
                    if wed.get("scheids_2"):
                        scheids_2 = scheidsrechters.get(wed["scheids_2"], {})
                        team_info = scheids_2.get("eigen_teams", [])
                        team_str = f"({team_info[0]})" if team_info else ""
                        scheids_2_naam = f"{scheids_2.get('naam', 'Onbekend')} {team_str}".strip()
                
                dag_wedstrijden.append({
                    "tijd": wed_datum.strftime("%H:%M"),
                    "veld": wed.get("veld") or "-",
                    "thuisteam": wed["thuisteam"],
                    "uitteam": wed["uitteam"],
                    "scheids_1": scheids_1_naam,
                    "scheids_2": scheids_2_naam,
                    "geannuleerd": geannuleerd,
                    "datum": wed_datum
                })
        
        dag_wedstrijden.sort(key=lambda x: x["datum"])
        return dag_wedstrijden
    
    # Helper functie om HTML preview te maken
    def maak_html_preview(datum, overzicht_data):
        html_rows = []
        for idx, wed in enumerate(overzicht_data):
            geannuleerd = wed.get("geannuleerd", False)
            if geannuleerd:
                bg = "#ffcccc"  # Licht rood voor geannuleerd
                scheids_cel = '<span style="color: #cc0000; font-weight: bold;">GEANNULEERD</span>'
                wed_cel = f'<span style="text-decoration: line-through; color: #888;">{wed["thuisteam"]}<br/>{wed["uitteam"]}</span>'
            else:
                bg = "#f5f5f5" if idx % 2 == 0 else "#ffffff"
                scheids_cel = f'1e: {wed["scheids_1"]}<br/>2e: {wed["scheids_2"]}'
                wed_cel = f'{wed["thuisteam"]}<br/>{wed["uitteam"]}'
            html_rows.append(f'<tr style="background-color: {bg};"><td style="padding: 8px; border: 1px solid #ccc; text-align: center; vertical-align: middle;">{wed["tijd"]}</td><td style="padding: 8px; border: 1px solid #ccc; text-align: center; vertical-align: middle;">{wed["veld"]}</td><td style="padding: 8px; border: 1px solid #ccc; vertical-align: middle;">{wed_cel}</td><td style="padding: 8px; border: 1px solid #ccc; vertical-align: middle;">{scheids_cel}</td></tr>')
        
        return f'''<div style="font-family: Arial, sans-serif; max-width: 750px; margin-bottom: 20px;"><div style="background-color: #4682B4; color: white; padding: 15px; text-align: center; border-radius: 5px 5px 0 0;"><h2 style="margin: 0;">SCHEIDSRECHTEROVERZICHT</h2><p style="margin: 5px 0 0 0; font-style: italic;">{dag_namen_lang[datum.weekday()]} {datum.day} {maand_namen[datum.month-1]} {datum.year}</p></div><table style="width: 100%; border-collapse: collapse; border: 1px solid #ccc;"><tr style="background-color: #4682B4; color: white;"><th style="padding: 10px; border: 1px solid #ccc; width: 60px;">Tijd</th><th style="padding: 10px; border: 1px solid #ccc; width: 60px;">Veld</th><th style="padding: 10px; border: 1px solid #ccc;">Wedstrijd</th><th style="padding: 10px; border: 1px solid #ccc;">Scheidsrechters</th></tr>{''.join(html_rows)}</table></div>'''
    
    # Toon overzicht voor elke dag in het weekend
    for dag_idx, gekozen_datum in enumerate(gekozen_dagen):
        dag_wedstrijden = get_wedstrijden_voor_dag(gekozen_datum)
        
        if not dag_wedstrijden:
            st.warning(f"Geen thuiswedstrijden op {dag_namen_lang[gekozen_datum.weekday()]} {gekozen_datum.strftime('%d-%m-%Y')}")
            continue
        
        # Preview tabel
        st.markdown(f"### {dag_namen_lang[gekozen_datum.weekday()]} {gekozen_datum.day} {maand_namen[gekozen_datum.month-1]}")
        
        html_preview = maak_html_preview(gekozen_datum, dag_wedstrijden)
        st.markdown(html_preview, unsafe_allow_html=True)
        
        # Download knoppen per dag
        col1, col2 = st.columns(2)
        
        dag_key = gekozen_datum.strftime("%Y%m%d")
        
        with col1:
            if st.button(f"🖼️ Genereer PNG", key=f"gen_{dag_key}", type="primary"):
                try:
                    img_bytes = genereer_overzicht_afbeelding(
                        datetime.combine(gekozen_datum, datetime.min.time()),
                        dag_wedstrijden,
                        scheidsrechters
                    )
                    st.session_state[f"overzicht_png_{dag_key}"] = img_bytes
                    st.success("Afbeelding gegenereerd!")
                except Exception as e:
                    st.error(f"Fout bij genereren: {e}")
        
        with col2:
            if f"overzicht_png_{dag_key}" in st.session_state:
                datum_str = gekozen_datum.strftime("%Y-%m-%d")
                dag_naam = dag_namen_lang[gekozen_datum.weekday()].lower()
                st.download_button(
                    f"⬇️ Download PNG",
                    data=st.session_state[f"overzicht_png_{dag_key}"],
                    file_name=f"scheidsrechter_overzicht_{dag_naam}_{datum_str}.png",
                    mime="image/png",
                    key=f"download_{dag_key}"
                )
        
        # Toon gegenereerde afbeelding
        if f"overzicht_png_{dag_key}" in st.session_state:
            with st.expander("Bekijk gegenereerde afbeelding", expanded=False):
                st.image(st.session_state[f"overzicht_png_{dag_key}"])
        
        if dag_idx < len(gekozen_dagen) - 1:
            st.markdown("---")
    
    # === OPEN POSITIES ALERT SECTIE ===
    st.markdown("---")
    st.subheader("🚨 Open Posities Alert")
    st.caption("Genereer een alert-afbeelding met open posities voor WhatsApp. Teams met ** (no-show risico) worden extra benadrukt.")
    
    # Tel open posities en zoekt vervanging voor geselecteerd weekend
    open_count = 0
    zoekt_count = 0
    kritiek_count = 0
    for dag in gekozen_dagen:
        for wed_id, wed in wedstrijden.items():
            if wed.get("type") == "uit" or wed.get("geannuleerd"):
                continue
            try:
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
            except:
                continue
            if wed_datum.date() == dag:
                if not wed.get("scheids_1"):
                    open_count += 1
                elif wed.get("scheids_1_zoekt_vervanging"):
                    zoekt_count += 1
                if not wed.get("scheids_2"):
                    open_count += 1
                elif wed.get("scheids_2_zoekt_vervanging"):
                    zoekt_count += 1
                if "**" in wed.get("thuisteam", "") and (not wed.get("scheids_1") or not wed.get("scheids_2")):
                    kritiek_count += 1
    
    totaal_aandacht = open_count + zoekt_count
    
    if totaal_aandacht == 0:
        st.success("🎉 Geen open posities of vervangers gezocht voor dit weekend!")
    else:
        status_parts = []
        if open_count > 0:
            status_parts.append(f"{open_count} open")
        if zoekt_count > 0:
            status_parts.append(f"{zoekt_count} zoekt vervanger")
        if kritiek_count > 0:
            status_parts.append(f"{kritiek_count} kritiek (**)")
        st.warning(f"⚠️ {', '.join(status_parts)}")
        
        col_gen, col_download = st.columns(2)
        
        alert_key = f"alert_{'_'.join([d.strftime('%Y%m%d') for d in gekozen_dagen])}"
        
        with col_gen:
            if st.button("🚨 Genereer Alert PNG", key=f"gen_alert_{alert_key}", type="primary"):
                try:
                    alert_bytes = genereer_open_posities_alert(gekozen_dagen, wedstrijden, scheidsrechters)
                    st.session_state[f"alert_png_{alert_key}"] = alert_bytes
                    st.success("Alert afbeelding gegenereerd!")
                except Exception as e:
                    st.error(f"Fout bij genereren: {e}")
        
        with col_download:
            if f"alert_png_{alert_key}" in st.session_state:
                start_dag = min(gekozen_dagen)
                st.download_button(
                    "⬇️ Download Alert PNG",
                    data=st.session_state[f"alert_png_{alert_key}"],
                    file_name=f"open_posities_alert_{start_dag.strftime('%Y-%m-%d')}.png",
                    mime="image/png",
                    key=f"download_alert_{alert_key}"
                )
        
        # Toon gegenereerde alert
        if f"alert_png_{alert_key}" in st.session_state:
            with st.expander("Bekijk gegenereerde alert", expanded=True):
                st.image(st.session_state[f"alert_png_{alert_key}"])

def toon_wedstrijden_beheer():
    """Beheer wedstrijden en toewijzingen."""
    wedstrijden = laad_wedstrijden()
    scheidsrechters = laad_scheidsrechters()
    instellingen = laad_instellingen()
    
    st.subheader("Wedstrijdoverzicht")
    
    # Bulk acties
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        if st.button("🗑️ Alle wedstrijden verwijderen", type="secondary"):
            st.session_state.bevestig_delete_all = True
    with col2:
        if st.button("🚫 Wedstrijden annuleren per dag", type="secondary"):
            st.session_state.toon_annuleer_dag = True
    
    if st.session_state.get("bevestig_delete_all"):
        st.warning("⚠️ Weet je zeker dat je ALLE wedstrijden wilt verwijderen?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Ja, verwijderen"):
                sla_wedstrijden_op({})
                st.session_state.bevestig_delete_all = False
                st.success("Alle wedstrijden verwijderd!")
                st.rerun()
        with col2:
            if st.button("❌ Annuleren"):
                st.session_state.bevestig_delete_all = False
                st.rerun()
    
    # Bulk annulering per dag
    if st.session_state.get("toon_annuleer_dag"):
        st.markdown("---")
        st.markdown("### 🚫 Wedstrijden annuleren per dag")
        st.caption("Annuleer alle wedstrijden op een specifieke dag. Scheidsrechters worden automatisch afgemeld met reden 'wedstrijd geannuleerd'.")
        
        # Verzamel unieke dagen met wedstrijden
        dagen_met_wedstrijden = set()
        for wed_id, wed in wedstrijden.items():
            if wed.get("geannuleerd"):
                continue
            try:
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                dagen_met_wedstrijden.add(wed_datum.date())
            except:
                pass
        
        if not dagen_met_wedstrijden:
            st.info("Geen actieve wedstrijden gevonden.")
        else:
            gesorteerde_dagen = sorted(dagen_met_wedstrijden)
            dag_namen_nl = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
            maand_namen_nl = ["", "januari", "februari", "maart", "april", "mei", "juni", 
                             "juli", "augustus", "september", "oktober", "november", "december"]
            dag_opties = {
                f"{dag_namen_nl[d.weekday()]} {d.day} {maand_namen_nl[d.month]} {d.year}": d 
                for d in gesorteerde_dagen
            }
            
            gekozen_dag_str = st.selectbox(
                "Selecteer dag om te annuleren",
                options=list(dag_opties.keys()),
                key="annuleer_dag_select"
            )
            gekozen_dag = dag_opties[gekozen_dag_str]
            
            # Toon wedstrijden op die dag
            wedstrijden_op_dag = []
            for wed_id, wed in wedstrijden.items():
                if wed.get("geannuleerd"):
                    continue
                try:
                    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                    if wed_datum.date() == gekozen_dag:
                        wedstrijden_op_dag.append((wed_id, wed, wed_datum))
                except:
                    pass
            
            wedstrijden_op_dag.sort(key=lambda x: x[2])
            
            st.write(f"**{len(wedstrijden_op_dag)} wedstrijden** op {gekozen_dag_str}:")
            
            scheids_affected = []
            for wed_id, wed, wed_datum in wedstrijden_op_dag:
                scheids_1_naam = scheidsrechters.get(wed.get("scheids_1"), {}).get("naam", "-")
                scheids_2_naam = scheidsrechters.get(wed.get("scheids_2"), {}).get("naam", "-")
                st.write(f"• {wed_datum.strftime('%H:%M')} - {wed.get('thuisteam', '?')} vs {wed.get('uitteam', '?')} ({scheids_1_naam} / {scheids_2_naam})")
                if wed.get("scheids_1"):
                    scheids_affected.append((wed.get("scheids_1"), scheids_1_naam))
                if wed.get("scheids_2"):
                    scheids_affected.append((wed.get("scheids_2"), scheids_2_naam))
            
            unieke_scheids = list(set(scheids_affected))
            if unieke_scheids:
                st.write(f"**{len(unieke_scheids)} scheidsrechters** worden afgemeld: {', '.join([s[1] for s in unieke_scheids])}")
            
            col_ja, col_nee = st.columns(2)
            with col_ja:
                if st.button("🚫 Annuleer deze dag", type="primary", key="bevestig_annuleer_dag"):
                    # Annuleer alle wedstrijden op deze dag - per wedstrijd opslaan (voorkomt race conditions)
                    aantal_geannuleerd = 0
                    for wed_id, wed, wed_datum in wedstrijden_op_dag:
                        # Log afmelding voor scheidsrechters
                        for positie in ["scheids_1", "scheids_2"]:
                            scheids_nbb = wed.get(positie)
                            if scheids_nbb:
                                try:
                                    db.log_registratie(scheids_nbb, wed_id, positie, "annulering_wedstrijd", wed_datum)
                                except:
                                    pass
                        
                        # Markeer wedstrijd als geannuleerd en verwijder scheidsrechters
                        wed_data = {
                            **wed,
                            "geannuleerd": True,
                            "geannuleerd_op": datetime.now().isoformat(),
                            "scheids_1": None,
                            "scheids_2": None,
                            "scheids_1_punten_berekend": None,
                            "scheids_2_punten_berekend": None,
                            "scheids_1_punten_details": None,
                            "scheids_2_punten_details": None,
                            "begeleider": None
                        }
                        sla_wedstrijd_op(wed_id, wed_data)
                        aantal_geannuleerd += 1
                    
                    # Clear alle bewerk session states voor deze wedstrijden
                    for wed_id, wed, wed_datum in wedstrijden_op_dag:
                        if f"bewerk_{wed_id}" in st.session_state:
                            del st.session_state[f"bewerk_{wed_id}"]
                    
                    st.session_state.toon_annuleer_dag = False
                    st.success(f"✅ {aantal_geannuleerd} wedstrijden geannuleerd, {len(unieke_scheids)} scheidsrechters afgemeld!")
                    st.rerun()
            
            with col_nee:
                if st.button("❌ Terug", key="annuleer_terug"):
                    st.session_state.toon_annuleer_dag = False
                    st.rerun()
        
        st.markdown("---")
    
    # Tabs voor thuis en uit
    tab_thuis, tab_uit = st.tabs(["🏠 Thuiswedstrijden (scheids nodig)", "🚗 Uitwedstrijden (blokkades)"])
    
    with tab_thuis:
        toon_wedstrijden_lijst(wedstrijden, scheidsrechters, instellingen, type_filter="thuis")
    
    with tab_uit:
        toon_wedstrijden_lijst(wedstrijden, scheidsrechters, instellingen, type_filter="uit")
    
    st.divider()
    
    # Nieuwe wedstrijd toevoegen
    st.subheader("➕ Nieuwe wedstrijd toevoegen")
    
    with st.form("nieuwe_wedstrijd"):
        col1, col2 = st.columns(2)
        with col1:
            wed_type = st.selectbox("Type", ["thuis", "uit"], format_func=lambda x: "🏠 Thuiswedstrijd" if x == "thuis" else "🚗 Uitwedstrijd")
            datum = st.date_input("Datum")
            tijd = st.time_input("Tijd")
            thuisteam = st.text_input("Thuisteam" if wed_type == "thuis" else "Eigen team")
        with col2:
            uitteam = st.text_input("Uitteam" if wed_type == "thuis" else "Tegenstander")
            niveau = st.selectbox("Niveau", [1, 2, 3, 4, 5])
            vereist_bs2 = st.checkbox("BS2 vereist")
            reistijd = st.number_input("Reistijd (minuten, voor uitwedstrijden)", min_value=0, value=60)
        
        if st.form_submit_button("Toevoegen"):
            wed_id = f"wed_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            nieuwe_wed = {
                "datum": f"{datum} {tijd.strftime('%H:%M')}",
                "thuisteam": thuisteam,
                "uitteam": uitteam,
                "niveau": niveau,
                "vereist_bs2": vereist_bs2,
                "type": wed_type,
                "scheids_1": None,
                "scheids_2": None
            }
            if wed_type == "uit":
                nieuwe_wed["reistijd_minuten"] = reistijd
            
            wedstrijden[wed_id] = nieuwe_wed
            sla_wedstrijden_op(wedstrijden)
            st.success("Wedstrijd toegevoegd!")
            st.rerun()


def toon_bewerk_formulier(wed: dict, wedstrijden: dict, scheidsrechters: dict, form_context: str = "default"):
    """Toon het bewerk formulier voor een wedstrijd."""
    st.markdown("---")
    st.markdown("**📝 Wedstrijd bewerken**")
    
    wed_data = wedstrijden[wed["id"]]
    huidige_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    
    # Unieke form key met context om duplicates te voorkomen
    with st.form(f"bewerk_form_{wed['id']}_{form_context}"):
        col_d, col_t, col_v = st.columns(3)
        
        with col_d:
            nieuwe_datum = st.date_input(
                "Datum", 
                value=huidige_datum.date(),
                key=f"edit_datum_{wed['id']}_{form_context}"
            )
        
        with col_t:
            nieuwe_tijd = st.time_input(
                "Tijd",
                value=huidige_datum.time(),
                key=f"edit_tijd_{wed['id']}_{form_context}"
            )
        
        with col_v:
            huidig_veld = wed_data.get("veld", "")
            nieuw_veld = st.text_input(
                "Veld",
                value=huidig_veld,
                key=f"edit_veld_{wed['id']}_{form_context}",
                placeholder="bijv. 1, 2, 3..."
            )
        
        col_niveau, col_bs2 = st.columns(2)
        with col_niveau:
            nieuw_niveau = st.selectbox(
                "Niveau",
                options=[1, 2, 3, 4, 5],
                index=wed_data.get("niveau", 1) - 1,
                key=f"edit_niveau_{wed['id']}_{form_context}"
            )
        with col_bs2:
            nieuw_bs2 = st.checkbox(
                "Vereist BS2",
                value=wed_data.get("vereist_bs2", False),
                key=f"edit_bs2_{wed['id']}_{form_context}"
            )
        
        submitted = st.form_submit_button("💾 Opslaan", type="primary")
        
        if submitted:
            nieuwe_datum_tijd = datetime.combine(nieuwe_datum, nieuwe_tijd)
            datum_gewijzigd = nieuwe_datum_tijd != huidige_datum
            
            # Check conflicten als datum/tijd is gewijzigd
            alle_conflicten = []
            if datum_gewijzigd:
                # Check 1e scheidsrechter
                if wed_data.get("scheids_1"):
                    conflicten_1 = analyseer_scheids_conflicten(
                        wed_data["scheids_1"], wed["id"], nieuwe_datum_tijd,
                        wedstrijden, scheidsrechters
                    )
                    alle_conflicten.extend(conflicten_1)
                
                # Check 2e scheidsrechter
                if wed_data.get("scheids_2"):
                    conflicten_2 = analyseer_scheids_conflicten(
                        wed_data["scheids_2"], wed["id"], nieuwe_datum_tijd,
                        wedstrijden, scheidsrechters
                    )
                    alle_conflicten.extend(conflicten_2)
            
            # Sla de wijzigingen op
            wedstrijden[wed["id"]]["datum"] = nieuwe_datum_tijd.strftime("%Y-%m-%d %H:%M")
            wedstrijden[wed["id"]]["veld"] = nieuw_veld
            wedstrijden[wed["id"]]["niveau"] = nieuw_niveau
            wedstrijden[wed["id"]]["vereist_bs2"] = nieuw_bs2
            sla_wedstrijden_op(wedstrijden)
            
            # Toon resultaat
            if alle_conflicten:
                st.session_state[f"conflicten_{wed['id']}"] = alle_conflicten
            
            st.session_state[f"bewerk_{wed['id']}"] = False
            st.success("✅ Wedstrijd bijgewerkt!")
            st.rerun()
    
    # Toon eventuele conflicten van vorige save
    if f"conflicten_{wed['id']}" in st.session_state:
        conflicten = st.session_state[f"conflicten_{wed['id']}"]
        if conflicten:
            st.error("⚠️ **Let op! Conflicten gedetecteerd:**")
            for conflict in conflicten:
                st.warning(f"• {conflict['beschrijving']}")
            st.info("💡 Overweeg de scheidsrechter(s) te verwijderen of een andere tijd te kiezen.")
            if st.button("Conflicten sluiten", key=f"close_conflict_{wed['id']}"):
                del st.session_state[f"conflicten_{wed['id']}"]
                st.rerun()


def toon_wedstrijden_lijst(wedstrijden: dict, scheidsrechters: dict, instellingen: dict, type_filter: str):
    """Toon lijst van wedstrijden gefilterd op type."""
    
    # Filter opties
    col1, col2 = st.columns(2)
    with col1:
        if type_filter == "thuis":
            filter_status = st.selectbox("Filter", ["Alle", "Nog in te vullen", "Compleet"], key=f"filter_{type_filter}")
        else:
            filter_status = "Alle"
    with col2:
        sorteer = st.selectbox("Sorteer op", ["Datum", "Niveau"], key=f"sort_{type_filter}")
    
    # Wedstrijden lijst
    wed_lijst = []
    for wed_id, wed in wedstrijden.items():
        # Filter op type (default is thuis voor oude data)
        wed_type = wed.get("type", "thuis")
        if wed_type != type_filter:
            continue
        
        scheids_1_naam = scheidsrechters.get(wed.get("scheids_1", ""), {}).get("naam", "")
        scheids_2_naam = scheidsrechters.get(wed.get("scheids_2", ""), {}).get("naam", "")
        
        compleet = bool(wed.get("scheids_1") and wed.get("scheids_2"))
        geannuleerd = wed.get("geannuleerd", False)
        
        # Filter op status
        if filter_status == "Nog in te vullen" and (compleet or geannuleerd):
            continue
        if filter_status == "Compleet" and (not compleet or geannuleerd):
            continue
        
        wed_lijst.append({
            "id": wed_id,
            "datum": wed["datum"],
            "thuisteam": wed["thuisteam"],
            "uitteam": wed["uitteam"],
            "niveau": wed["niveau"],
            "scheids_1": wed.get("scheids_1"),
            "scheids_1_naam": scheids_1_naam,
            "scheids_2": wed.get("scheids_2"),
            "scheids_2_naam": scheids_2_naam,
            "compleet": compleet,
            "geannuleerd": geannuleerd,
            "reistijd": wed.get("reistijd_minuten", 0),
            "veld": wed.get("veld", "")
        })
    
    if sorteer == "Datum":
        wed_lijst.sort(key=lambda x: x["datum"])
    else:
        wed_lijst.sort(key=lambda x: (x["niveau"], x["datum"]))
    
    if not wed_lijst:
        st.info("Geen wedstrijden gevonden.")
        return
    
    st.write(f"**{len(wed_lijst)} wedstrijden**")
    
    # Toon wedstrijden
    for wed in wed_lijst:
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
        niveau_tekst = instellingen["niveaus"].get(str(wed["niveau"]), "")
        
        if type_filter == "thuis":
            if wed["geannuleerd"]:
                status_icon = "❌"
                label = f"{status_icon} ~~{dag} {wed_datum.strftime('%d-%m %H:%M')} | {wed['thuisteam']} - {wed['uitteam']}~~ **GEANNULEERD**"
            else:
                status_icon = "✅" if wed["compleet"] else "⚠️"
                label = f"{status_icon} {dag} {wed_datum.strftime('%d-%m %H:%M')} | {wed['thuisteam']} - {wed['uitteam']} (Niv. {wed['niveau']})"
        else:
            label = f"🚗 {dag} {wed_datum.strftime('%d-%m %H:%M')} | {wed['thuisteam']} @ {wed['uitteam']} ({wed['reistijd']} min reistijd)"
        
        with st.expander(label):
            if type_filter == "thuis":
                # Annuleer toggle bovenaan
                col_annuleer, col_veld = st.columns([1, 1])
                with col_annuleer:
                    is_geannuleerd = st.checkbox(
                        "❌ Wedstrijd geannuleerd", 
                        value=wed["geannuleerd"],
                        key=f"annuleer_{wed['id']}"
                    )
                    if is_geannuleerd != wed["geannuleerd"]:
                        wedstrijden[wed["id"]]["geannuleerd"] = is_geannuleerd
                        sla_wedstrijden_op(wedstrijden)
                        st.rerun()
                
                with col_veld:
                    if wed["veld"]:
                        st.write(f"📍 Veld: **{wed['veld']}**")
                
                if wed["geannuleerd"]:
                    st.warning("Deze wedstrijd is geannuleerd. Scheidsrechters worden niet meegerekend.")
                    
                    # Acties voor geannuleerde wedstrijd
                    col_acties = st.columns([4, 1])[1]
                    with col_acties:
                        bewerk_key = f"bewerk_{wed['id']}"
                        if bewerk_key not in st.session_state:
                            st.session_state[bewerk_key] = False
                        
                        col_edit, col_del = st.columns(2)
                        with col_edit:
                            if st.button("✏️", key=f"toggle_edit_{wed['id']}", help="Bewerk wedstrijd"):
                                st.session_state[bewerk_key] = not st.session_state[bewerk_key]
                                st.rerun()
                        with col_del:
                            confirm_key = f"confirm_del_{wed['id']}"
                            if confirm_key not in st.session_state:
                                st.session_state[confirm_key] = False
                            
                            if not st.session_state[confirm_key]:
                                if st.button("🗑️", key=f"delwed_{wed['id']}", help="Verwijder wedstrijd"):
                                    st.session_state[confirm_key] = True
                                    st.rerun()
                            else:
                                st.warning("Verwijderen?")
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button("✅ Ja", key=f"confirm_yes_{wed['id']}"):
                                        db.verwijder_wedstrijd(wed["id"])
                                        st.session_state[confirm_key] = False
                                        st.rerun()
                                with col_no:
                                    if st.button("❌ Nee", key=f"confirm_no_{wed['id']}"):
                                        st.session_state[confirm_key] = False
                                        st.rerun()
                    
                    # Bewerk formulier voor geannuleerde wedstrijd
                    if st.session_state.get(f"bewerk_{wed['id']}", False):
                        toon_bewerk_formulier(wed, wedstrijden, scheidsrechters, form_context="geannuleerd")
                else:
                    col1, col2, col_beg, col3 = st.columns([2, 2, 2, 1])
                    
                    # Haal afmeldingen op voor deze wedstrijd
                    afmeldingen = get_afmeldingen_voor_wedstrijd(wed["id"], wedstrijden, scheidsrechters)
                    afmeldingen_1e = [a for a in afmeldingen if a.get("positie") == "scheids_1"]
                    afmeldingen_2e = [a for a in afmeldingen if a.get("positie") == "scheids_2"]
                    
                    with col1:
                        st.write("**1e Scheidsrechter:**")
                        if wed["scheids_1_naam"]:
                            zoekt_1 = wed.get("scheids_1_zoekt_vervanging", False)
                            status_1 = f"✓ {wed['scheids_1_naam']}" + (" 🔄" if zoekt_1 else "")
                            st.write(status_1)
                            col_del1, col_zoekt1 = st.columns(2)
                            with col_del1:
                                if st.button("Verwijderen", key=f"del1_{wed['id']}"):
                                    wedstrijden[wed["id"]]["scheids_1"] = None
                                    wedstrijden[wed["id"]]["scheids_1_zoekt_vervanging"] = False
                                    sla_wedstrijden_op(wedstrijden)
                                    st.rerun()
                            with col_zoekt1:
                                nieuwe_zoekt_1 = st.checkbox("Zoekt", value=zoekt_1, key=f"zoekt1_{wed['id']}", help="Zoekt vervanging")
                                if nieuwe_zoekt_1 != zoekt_1:
                                    wedstrijden[wed["id"]]["scheids_1_zoekt_vervanging"] = nieuwe_zoekt_1
                                    sla_wedstrijd_op(wed["id"], wedstrijden[wed["id"]])
                        else:
                            # NIEUW: Toon afmeldingen voor deze positie
                            if afmeldingen_1e:
                                afm_namen = ", ".join([a["naam"] for a in afmeldingen_1e])
                                st.caption(f"⚠️ Afgemeld: {afm_namen}")
                            
                            kandidaten = get_kandidaten_voor_wedstrijd(wed["id"], als_eerste=True)
                            if kandidaten:
                                keuzes = ["-- Selecteer --"] + [
                                    ("🔙 " if k.get('is_eerder_afgemeld') else "") +  # NIEUW: indicator voor eerder afgemeld
                                    ("😴 " if k.get('is_passief') else "") +
                                    f"{k['naam']} ({k['huidig_aantal']} wed)" + 
                                    (f" ⚠️ nog {k['tekort']} nodig" if k['tekort'] > 0 else "")
                                    for k in kandidaten
                                ]
                                selectie = st.selectbox("Kies 1e scheids", keuzes, key=f"sel1_{wed['id']}")
                                if selectie != "-- Selecteer --":
                                    idx = keuzes.index(selectie) - 1
                                    if st.button("Toewijzen", key=f"assign1_{wed['id']}"):
                                        gekozen_nbb = kandidaten[idx]["nbb_nummer"]
                                        # TC-toewijzing: bereken punten met bonus
                                        resultaat = schrijf_in_als_scheids(gekozen_nbb, wed["id"], "scheids_1", wedstrijden, scheidsrechters, bron="tc")
                                        if resultaat is None:
                                            st.error("⚠️ Wedstrijd niet gevonden. Ververs de pagina.")
                                        elif isinstance(resultaat, dict) and resultaat.get("error") == "bezet":
                                            toon_error_met_scroll(f"⚠️ Positie al bezet door **{resultaat['huidige_naam']}**. Ververs de pagina.")
                                        else:
                                            st.rerun()
                            else:
                                st.warning("Geen geschikte kandidaten")
                    
                    with col2:
                        st.write("**2e Scheidsrechter:**")
                        if wed["scheids_2_naam"]:
                            zoekt_2 = wed.get("scheids_2_zoekt_vervanging", False)
                            status_2 = f"✓ {wed['scheids_2_naam']}" + (" 🔄" if zoekt_2 else "")
                            st.write(status_2)
                            col_del2, col_zoekt2 = st.columns(2)
                            with col_del2:
                                if st.button("Verwijderen", key=f"del2_{wed['id']}"):
                                    wedstrijden[wed["id"]]["scheids_2"] = None
                                    wedstrijden[wed["id"]]["scheids_2_zoekt_vervanging"] = False
                                    sla_wedstrijden_op(wedstrijden)
                                    st.rerun()
                            with col_zoekt2:
                                nieuwe_zoekt_2 = st.checkbox("Zoekt", value=zoekt_2, key=f"zoekt2_{wed['id']}", help="Zoekt vervanging")
                                if nieuwe_zoekt_2 != zoekt_2:
                                    wedstrijden[wed["id"]]["scheids_2_zoekt_vervanging"] = nieuwe_zoekt_2
                                    sla_wedstrijd_op(wed["id"], wedstrijden[wed["id"]])
                        else:
                            # NIEUW: Toon afmeldingen voor deze positie
                            if afmeldingen_2e:
                                afm_namen = ", ".join([a["naam"] for a in afmeldingen_2e])
                                st.caption(f"⚠️ Afgemeld: {afm_namen}")
                            
                            kandidaten = get_kandidaten_voor_wedstrijd(wed["id"], als_eerste=False)
                            if kandidaten:
                                keuzes = ["-- Selecteer --"] + [
                                    ("🔙 " if k.get('is_eerder_afgemeld') else "") +  # NIEUW: indicator voor eerder afgemeld
                                    ("😴 " if k.get('is_passief') else "") +
                                    f"{k['naam']} ({k['huidig_aantal']} wed)" +
                                    (f" ⚠️ nog {k['tekort']} nodig" if k['tekort'] > 0 else "")
                                    for k in kandidaten
                                ]
                                selectie = st.selectbox("Kies 2e scheids", keuzes, key=f"sel2_{wed['id']}")
                                if selectie != "-- Selecteer --":
                                    idx = keuzes.index(selectie) - 1
                                    if st.button("Toewijzen", key=f"assign2_{wed['id']}"):
                                        gekozen_nbb = kandidaten[idx]["nbb_nummer"]
                                        # TC-toewijzing: bereken punten met bonus
                                        resultaat = schrijf_in_als_scheids(gekozen_nbb, wed["id"], "scheids_2", wedstrijden, scheidsrechters, bron="tc")
                                        if resultaat is None:
                                            st.error("⚠️ Wedstrijd niet gevonden. Ververs de pagina.")
                                        elif isinstance(resultaat, dict) and resultaat.get("error") == "bezet":
                                            toon_error_met_scroll(f"⚠️ Positie al bezet door **{resultaat['huidige_naam']}**. Ververs de pagina.")
                                        else:
                                            st.rerun()
                            else:
                                st.warning("Geen geschikte kandidaten")
                    
                    with col_beg:
                        st.write("**Begeleider:**")
                        begeleider_nbb = wedstrijden[wed["id"]].get("begeleider")
                        if begeleider_nbb:
                            begeleider_naam = scheidsrechters.get(begeleider_nbb, {}).get("naam", "Onbekend")
                            st.write(f"🎓 {begeleider_naam}")
                            if st.button("Verwijderen", key=f"del_beg_{wed['id']}"):
                                wedstrijden[wed["id"]]["begeleider"] = None
                                sla_wedstrijd_op(wed["id"], wedstrijden[wed["id"]])
                                st.rerun()
                        else:
                            # Toon alleen MSE's als opties
                            mse_kandidaten = [
                                (nbb, s) for nbb, s in scheidsrechters.items()
                                if (s.get("niveau_1e_scheids", 1) == 5 or any("MSE" in t.upper() for t in s.get("eigen_teams", [])))
                                and nbb != wed.get("scheids_1") and nbb != wed.get("scheids_2")
                            ]
                            if mse_kandidaten:
                                keuzes = ["-- Selecteer --"] + [s["naam"] for nbb, s in mse_kandidaten]
                                selectie = st.selectbox("Kies begeleider", keuzes, key=f"sel_beg_{wed['id']}")
                                if selectie != "-- Selecteer --":
                                    idx = keuzes.index(selectie) - 1
                                    if st.button("Toewijzen", key=f"assign_beg_{wed['id']}"):
                                        wedstrijden[wed["id"]]["begeleider"] = mse_kandidaten[idx][0]
                                        sla_wedstrijd_op(wed["id"], wedstrijden[wed["id"]])
                                        st.rerun()
                            else:
                                st.caption("Geen MSE beschikbaar")
                    
                    with col3:
                        st.write("**Acties:**")
                        
                        # Bewerk toggle
                        bewerk_key = f"bewerk_{wed['id']}"
                        if bewerk_key not in st.session_state:
                            st.session_state[bewerk_key] = False
                        
                        col_edit, col_del = st.columns(2)
                        with col_edit:
                            if st.button("✏️", key=f"toggle_edit_{wed['id']}", help="Bewerk wedstrijd"):
                                st.session_state[bewerk_key] = not st.session_state[bewerk_key]
                                st.rerun()
                        with col_del:
                            confirm_key = f"confirm_del_{wed['id']}"
                            if confirm_key not in st.session_state:
                                st.session_state[confirm_key] = False
                            
                            if not st.session_state[confirm_key]:
                                if st.button("🗑️", key=f"delwed_{wed['id']}", help="Verwijder wedstrijd"):
                                    st.session_state[confirm_key] = True
                                    st.rerun()
                            else:
                                st.warning("Verwijderen?")
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button("✅ Ja", key=f"confirm_yes_{wed['id']}"):
                                        db.verwijder_wedstrijd(wed["id"])
                                        st.session_state[confirm_key] = False
                                        st.rerun()
                                with col_no:
                                    if st.button("❌ Nee", key=f"confirm_no_{wed['id']}"):
                                        st.session_state[confirm_key] = False
                                        st.rerun()
                
                # Bewerk formulier (buiten de columns, volledige breedte)
                if st.session_state.get(f"bewerk_{wed['id']}", False):
                    toon_bewerk_formulier(wed, wedstrijden, scheidsrechters, form_context="actief")
            else:
                # Uitwedstrijd - info, bewerk en delete
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Team:** {wed['thuisteam']}")
                    st.write(f"**Reistijd:** {wed['reistijd']} minuten")
                with col2:
                    bewerk_key = f"bewerk_{wed['id']}"
                    if bewerk_key not in st.session_state:
                        st.session_state[bewerk_key] = False
                    
                    col_edit, col_del = st.columns(2)
                    with col_edit:
                        if st.button("✏️", key=f"toggle_edit_{wed['id']}", help="Bewerk wedstrijd"):
                            st.session_state[bewerk_key] = not st.session_state[bewerk_key]
                            st.rerun()
                    with col_del:
                        confirm_key = f"confirm_del_{wed['id']}"
                        if confirm_key not in st.session_state:
                            st.session_state[confirm_key] = False
                        
                        if not st.session_state[confirm_key]:
                            if st.button("🗑️", key=f"delwed_{wed['id']}", help="Verwijder wedstrijd"):
                                st.session_state[confirm_key] = True
                                st.rerun()
                        else:
                            st.warning("Verwijderen?")
                            col_yes, col_no = st.columns(2)
                            with col_yes:
                                if st.button("✅ Ja", key=f"confirm_yes_{wed['id']}"):
                                    db.verwijder_wedstrijd(wed["id"])
                                    st.session_state[confirm_key] = False
                                    st.rerun()
                            with col_no:
                                if st.button("❌ Nee", key=f"confirm_no_{wed['id']}"):
                                    st.session_state[confirm_key] = False
                                    st.rerun()
                
                # Bewerk formulier voor uitwedstrijd
                if st.session_state.get(f"bewerk_{wed['id']}", False):
                    st.markdown("---")
                    st.markdown("**📝 Uitwedstrijd bewerken**")
                    
                    wed_data = wedstrijden[wed["id"]]
                    huidige_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                    
                    with st.form(f"bewerk_uit_form_{wed['id']}"):
                        col_d, col_t, col_r = st.columns(3)
                        
                        with col_d:
                            nieuwe_datum = st.date_input(
                                "Datum", 
                                value=huidige_datum.date(),
                                key=f"edit_uit_datum_{wed['id']}"
                            )
                        
                        with col_t:
                            nieuwe_tijd = st.time_input(
                                "Tijd",
                                value=huidige_datum.time(),
                                key=f"edit_uit_tijd_{wed['id']}"
                            )
                        
                        with col_r:
                            nieuwe_reistijd = st.number_input(
                                "Reistijd (min)",
                                min_value=0,
                                max_value=180,
                                value=wed_data.get("reistijd_minuten", 60),
                                key=f"edit_uit_reistijd_{wed['id']}"
                            )
                        
                        submitted = st.form_submit_button("💾 Opslaan", type="primary")
                        
                        if submitted:
                            nieuwe_datum_tijd = datetime.combine(nieuwe_datum, nieuwe_tijd)
                            
                            wedstrijden[wed["id"]]["datum"] = nieuwe_datum_tijd.strftime("%Y-%m-%d %H:%M")
                            wedstrijden[wed["id"]]["reistijd_minuten"] = nieuwe_reistijd
                            sla_wedstrijden_op(wedstrijden)
                            
                            st.session_state[f"bewerk_{wed['id']}"] = False
                            st.success("✅ Uitwedstrijd bijgewerkt!")
                            st.rerun()

def toon_scheidsrechters_beheer():
    """Beheer scheidsrechters."""
    scheidsrechters = laad_scheidsrechters()
    instellingen = laad_instellingen()
    
    # Check of deadline verstreken is
    deadline = datetime.strptime(instellingen["inschrijf_deadline"], "%Y-%m-%d")
    deadline_verstreken = datetime.now() > deadline
    
    st.subheader("Scheidsrechtersoverzicht")
    
    # Overzicht per niveau
    if scheidsrechters:
        scheids_per_niveau = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        totaal_min = 0
        for nbb, scheids in scheidsrechters.items():
            niveau = scheids.get("niveau_1e_scheids", 1)
            scheids_per_niveau[niveau] = scheids_per_niveau.get(niveau, 0) + 1
            totaal_min += scheids.get("min_wedstrijden", 0)
        
        st.write("**Scheidsrechters per niveau (1e scheids):**")
        cols = st.columns(6)
        for i, niveau in enumerate([1, 2, 3, 4, 5]):
            count = scheids_per_niveau.get(niveau, 0)
            cols[i].metric(f"Niveau {niveau}", count)
        cols[5].metric("Totaal", len(scheidsrechters))
        
        st.caption(f"Minimale capaciteit: {totaal_min} wedstrijden | {len(scheidsrechters)} scheidsrechters")
        st.divider()
    
    # Legenda
    if deadline_verstreken:
        st.caption("✅ Voldoet aan minimum op eigen niveau | ⚠️ Nog niet genoeg wedstrijden op eigen niveau")
    else:
        st.caption("✅ Voldoet aan minimum op eigen niveau | ⏳ Inschrijving loopt nog")
    
    st.info("ℹ️ Het minimum aantal wedstrijden moet op het **eigen niveau** gefluiten worden. Wedstrijden op een lager niveau tellen niet mee voor het minimum.")
    
    # Filters
    st.write("**Filters:**")
    col_filter1, col_filter2, col_filter3, col_filter4, col_filter5 = st.columns(5)
    
    with col_filter1:
        niveau_filter = st.selectbox(
            "Filter op niveau (1e scheids)", 
            options=["Alle niveaus", "Niveau 5", "Niveau 4", "Niveau 3", "Niveau 2", "Niveau 1"],
            key="scheids_niveau_filter"
        )
    
    with col_filter2:
        status_filter = st.selectbox(
            "Filter op wedstrijden",
            options=["Alle", "Voldoet niet aan minimum", "Voldoet aan minimum"],
            key="scheids_status_filter"
        )
    
    with col_filter3:
        scheids_status_filter = st.selectbox(
            "Filter op status",
            options=["Alle", "🎯 Op te leiden", "✅ Actief", "⏸️ Inactief"],
            key="scheids_scheids_status_filter"
        )
    
    with col_filter4:
        bs2_filter = st.selectbox(
            "Filter op BS2",
            options=["Alle", "Met BS2 diploma", "Zonder BS2 diploma"],
            key="scheids_bs2_filter"
        )
    
    with col_filter5:
        begeleiding_filter = st.selectbox(
            "Filter op begeleiding",
            options=["Alle", "🎓 Open voor begeleiding", "Niet open"],
            key="scheids_begeleiding_filter"
        )
    
    # Filter scheidsrechters
    gefilterde_scheidsrechters = {}
    for nbb, scheids in scheidsrechters.items():
        # Niveau filter
        if niveau_filter != "Alle niveaus":
            filter_niveau = int(niveau_filter.replace("Niveau ", ""))
            if scheids.get("niveau_1e_scheids", 1) != filter_niveau:
                continue
        
        # BS2 filter
        if bs2_filter == "Met BS2 diploma" and not scheids.get("bs2_diploma", False):
            continue
        if bs2_filter == "Zonder BS2 diploma" and scheids.get("bs2_diploma", False):
            continue
        
        # Begeleiding filter
        if begeleiding_filter == "🎓 Open voor begeleiding" and not scheids.get("open_voor_begeleiding", False):
            continue
        if begeleiding_filter == "Niet open" and scheids.get("open_voor_begeleiding", False):
            continue
        
        # Scheidsrechter status filter
        if scheids_status_filter != "Alle":
            scheids_status = scheids.get("scheids_status", "Actief")
            if scheids_status_filter == "🎯 Op te leiden" and scheids_status != "Op te leiden":
                continue
            if scheids_status_filter == "✅ Actief" and scheids_status != "Actief":
                continue
            if scheids_status_filter == "⏸️ Inactief" and scheids_status != "Inactief":
                continue
        
        # Status filter (moet na niveau check want we gebruiken niveau_stats)
        if status_filter != "Alle":
            niveau_stats = tel_wedstrijden_op_eigen_niveau(nbb)
            op_niveau = niveau_stats["op_niveau"]
            min_wed = scheids.get("min_wedstrijden", 0)
            
            if status_filter == "Voldoet aan minimum" and op_niveau < min_wed:
                continue
            if status_filter == "Voldoet niet aan minimum" and op_niveau >= min_wed:
                continue
        
        gefilterde_scheidsrechters[nbb] = scheids
    
    # Toon aantal resultaten
    st.caption(f"*{len(gefilterde_scheidsrechters)} van {len(scheidsrechters)} scheidsrechters*")
    
    # Overzicht tabel met wedstrijden, punten en strikes
    st.divider()
    st.write("### 📊 Overzicht")
    
    # Verzamel data voor tabel
    overzicht_data = []
    for nbb, scheids in sorted(gefilterde_scheidsrechters.items(), key=lambda x: x[1]["naam"]):
        niveau_stats = tel_wedstrijden_op_eigen_niveau(nbb)
        speler_stats = get_speler_stats(nbb)
        
        # Status icoon bepalen
        status = scheids.get("scheids_status", "Actief")
        status_icon = {"Actief": "", "Op te leiden": "🎯", "Inactief": "⏸️"}.get(status, "")
        
        overzicht_data.append({
            "Naam": scheids.get("naam", "?"),
            "Niveau": scheids.get("niveau_1e_scheids", 1),
            "Wedstrijden": niveau_stats["totaal"],
            "Op niveau": f"{niveau_stats['op_niveau']}/{scheids.get('min_wedstrijden', 0)}",
            "🏆 Punten": speler_stats["punten"],
            "⚠️ Strikes": speler_stats["strikes"],
            "BS2": "✓" if scheids.get("bs2_diploma", False) else "",
            "🎓": "✓" if scheids.get("open_voor_begeleiding", False) else "",
            "🤕": "✓" if scheids.get("geblesseerd_tm") else "",
            "🧪": "✓" if scheids.get("uitgesloten_van_pool", False) else "",
            "🎯": status_icon,
        })
    
    if overzicht_data:
        # Toon als tabel
        import pandas as pd
        df = pd.DataFrame(overzicht_data)
        
        # Sorteer opties
        sorteer_optie = st.selectbox(
            "Sorteer op",
            ["Naam", "Niveau (hoog→laag)", "Wedstrijden (veel→weinig)", "Punten (hoog→laag)", "Strikes (hoog→laag)"],
            key="sorteer_overzicht"
        )
        
        if sorteer_optie == "Niveau (hoog→laag)":
            df = df.sort_values("Niveau", ascending=False)
        elif sorteer_optie == "Wedstrijden (veel→weinig)":
            df = df.sort_values("Wedstrijden", ascending=False)
        elif sorteer_optie == "Punten (hoog→laag)":
            df = df.sort_values("🏆 Punten", ascending=False)
        elif sorteer_optie == "Strikes (hoog→laag)":
            df = df.sort_values("⚠️ Strikes", ascending=False)
        
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Tel spelers per categorie
        open_voor_begeleiding_count = sum(1 for d in overzicht_data if d["🎓"] == "✓")
        geblesseerd_count = sum(1 for d in overzicht_data if d["🤕"] == "✓")
        uitgesloten_count = sum(1 for d in overzicht_data if d["🧪"] == "✓")
        op_te_leiden_count = sum(1 for d in overzicht_data if d["🎯"] == "🎯")
        inactief_count = sum(1 for d in overzicht_data if d["🎯"] == "⏸️")
        legenda_items = []
        if op_te_leiden_count > 0:
            legenda_items.append(f"🎯 = Op te leiden ({op_te_leiden_count})")
        if inactief_count > 0:
            legenda_items.append(f"⏸️ = Inactief ({inactief_count})")
        if open_voor_begeleiding_count > 0:
            legenda_items.append(f"🎓 = Open voor begeleiding ({open_voor_begeleiding_count})")
        if geblesseerd_count > 0:
            legenda_items.append(f"🤕 = Geblesseerd ({geblesseerd_count})")
        if uitgesloten_count > 0:
            legenda_items.append(f"🧪 = Uitgesloten van pool ({uitgesloten_count})")
        if legenda_items:
            st.caption(" | ".join(legenda_items))
    
    st.divider()
    st.write("### 📝 Details per scheidsrechter")
    
    # Statistieken (expanders)
    for nbb, scheids in sorted(gefilterde_scheidsrechters.items(), key=lambda x: x[1]["naam"]):
        niveau_stats = tel_wedstrijden_op_eigen_niveau(nbb)
        huidig = niveau_stats["totaal"]
        op_niveau = niveau_stats["op_niveau"]
        eigen_niveau = niveau_stats["niveau"]
        min_wed = scheids.get("min_wedstrijden", 0)
        
        # Status bepalen op basis van wedstrijden op eigen niveau
        if op_niveau >= min_wed:
            status = "✅"  # Voldoet aan minimum
        elif deadline_verstreken:
            status = "⚠️"  # Deadline verstreken en nog niet genoeg
        else:
            status = "⏳"  # Nog niet genoeg, maar deadline nog niet verstreken
        
        # Blessure indicator
        blessure_indicator = " 🤕" if scheids.get("geblesseerd_tm") else ""
        
        label = f"{status} {scheids['naam']}{blessure_indicator} - {op_niveau}/{min_wed} op niv.{eigen_niveau} (totaal: {huidig})"
        with st.expander(label):
            # Bewerk modus toggle
            edit_key = f"edit_{nbb}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False
            
            col_info, col_btn = st.columns([4, 1])
            with col_btn:
                if st.button("✏️ Bewerk" if not st.session_state[edit_key] else "❌ Annuleer", key=f"toggle_{nbb}"):
                    st.session_state[edit_key] = not st.session_state[edit_key]
                    st.rerun()
            
            if st.session_state[edit_key]:
                # Bewerk formulier
                with st.form(f"edit_form_{nbb}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nieuwe_naam = st.text_input("Naam", value=str(scheids.get("naam", "") or ""), key=f"naam_{nbb}")
                        
                        # Status van scheidsrechter
                        huidige_status = scheids.get("scheids_status", "Actief")
                        if huidige_status not in SCHEIDSRECHTER_STATUS_OPTIES:
                            huidige_status = "Actief"
                        status_idx = SCHEIDSRECHTER_STATUS_OPTIES.index(huidige_status)
                        scheids_status = st.selectbox(
                            "Status",
                            options=SCHEIDSRECHTER_STATUS_OPTIES,
                            index=status_idx,
                            key=f"status_{nbb}",
                            help="Op te leiden = moet nog getraind worden door TC-support"
                        )
                        
                        bs2_diploma = st.checkbox("BS2 diploma", value=bool(scheids.get("bs2_diploma", False)), key=f"bs2_{nbb}")
                        niet_op_zondag = st.checkbox("Niet op zondag", value=bool(scheids.get("niet_op_zondag", False)), key=f"zondag_{nbb}")
                        uitgesloten_van_pool = st.checkbox(
                            "Uitsluiten van pool", 
                            value=bool(scheids.get("uitgesloten_van_pool", False)), 
                            key=f"pool_{nbb}",
                            help="Test/reserve spelers - telt niet mee in pool-berekening"
                        )
                        
                        # Blessure status
                        st.markdown("**🤕 Blessure**")
                        huidige_blessure = scheids.get("geblesseerd_tm", "")
                        # Maak maand opties (huidige maand + 6 maanden vooruit)
                        maand_namen = ["januari", "februari", "maart", "april", "mei", "juni", 
                                      "juli", "augustus", "september", "oktober", "november", "december"]
                        nu = datetime.now()
                        blessure_opties = ["Niet geblesseerd"]
                        for i in range(7):  # Huidige maand + 6 maanden
                            maand_idx = (nu.month - 1 + i) % 12
                            jaar = nu.year + ((nu.month + i - 1) // 12)
                            blessure_opties.append(f"{maand_namen[maand_idx]} {jaar}")
                        
                        # Bepaal huidige index
                        blessure_idx = 0
                        if huidige_blessure and huidige_blessure in blessure_opties:
                            blessure_idx = blessure_opties.index(huidige_blessure)
                        
                        geblesseerd_tm = st.selectbox(
                            "Geblesseerd t/m",
                            options=blessure_opties,
                            index=blessure_idx,
                            key=f"blessure_{nbb}",
                            help="Speler wordt niet getoond bij handmatige toewijzing voor wedstrijden in deze maand"
                        )
                    with col2:
                        # Zorg voor geldige index (0-4)
                        idx_1e = max(0, min(4, scheids.get("niveau_1e_scheids", 1) - 1))
                        
                        niveau_1e = st.selectbox("1e scheids t/m niveau", [1, 2, 3, 4, 5], 
                                                  index=idx_1e, key=f"niv1_{nbb}")
                        # 2e scheids niveau wordt automatisch berekend als niveau_1e + 1
                        max_niveau_2e = min(niveau_1e + 1, 5)
                        st.info(f"2e scheids t/m niveau: **{max_niveau_2e}** (automatisch)")
                        min_w = st.number_input("Minimum wedstrijden", min_value=0, 
                                                value=int(scheids.get("min_wedstrijden", 2) or 2), key=f"min_{nbb}")
                    
                    eigen_teams = st.multiselect(
                        "Eigen teams", 
                        options=SCHEIDSRECHTER_TEAMS,
                        default=[t for t in scheids.get("eigen_teams", []) if t in SCHEIDSRECHTER_TEAMS],
                        key=f"teams_{nbb}"
                    )
                    
                    # Begeleiding velden (TC kan dit ook aanpassen)
                    st.divider()
                    st.write("**🎓 Begeleiding**")
                    open_voor_begeleiding = st.checkbox(
                        "Open voor begeleiding", 
                        value=bool(scheids.get("open_voor_begeleiding", False)), 
                        key=f"begeleiding_{nbb}"
                    )
                    
                    begeleiding_reden_idx = 0
                    if scheids.get("begeleiding_reden") in BEGELEIDING_REDENEN:
                        begeleiding_reden_idx = BEGELEIDING_REDENEN.index(scheids.get("begeleiding_reden")) + 1
                    begeleiding_reden = st.selectbox(
                        "Reden",
                        options=[""] + BEGELEIDING_REDENEN,
                        index=begeleiding_reden_idx,
                        key=f"reden_{nbb}"
                    )
                    telefoon_begeleiding = st.text_input(
                        "Telefoon voor begeleiding",
                        value=scheids.get("telefoon_begeleiding", ""),
                        key=f"telefoon_{nbb}"
                    )
                    
                    col_save, col_delete = st.columns(2)
                    with col_save:
                        if st.form_submit_button("💾 Opslaan"):
                            # niveau_2e wordt automatisch berekend
                            niveau_2e = min(niveau_1e + 1, 5)
                            # Blessure waarde: leeg als "Niet geblesseerd"
                            blessure_waarde = "" if geblesseerd_tm == "Niet geblesseerd" else geblesseerd_tm
                            scheidsrechters[nbb] = {
                                "naam": nieuwe_naam,
                                "scheids_status": scheids_status,
                                "bs2_diploma": bs2_diploma,
                                "niet_op_zondag": niet_op_zondag,
                                "uitgesloten_van_pool": uitgesloten_van_pool,
                                "niveau_1e_scheids": niveau_1e,
                                "niveau_2e_scheids": niveau_2e,
                                "min_wedstrijden": min_w,
                                "eigen_teams": eigen_teams,
                                "geblesseerd_tm": blessure_waarde,
                                "geblokkeerde_dagen": scheids.get("geblokkeerde_dagen", []),
                                "open_voor_begeleiding": open_voor_begeleiding,
                                "begeleiding_reden": begeleiding_reden if open_voor_begeleiding else "",
                                "telefoon_begeleiding": telefoon_begeleiding if open_voor_begeleiding else ""
                            }
                            sla_scheidsrechter_op(nbb, scheidsrechters[nbb])
                            st.session_state[edit_key] = False
                            st.success("Scheidsrechter bijgewerkt!")
                            st.rerun()
                    with col_delete:
                        if st.form_submit_button("🗑️ Verwijderen", type="secondary"):
                            del scheidsrechters[nbb]
                            db.verwijder_scheidsrechter(nbb)
                            st.session_state[edit_key] = False
                            st.success("Scheidsrechter verwijderd!")
                            st.rerun()
            else:
                # Weergave modus
                col1, col2 = st.columns(2)
                
                niveau_1e = scheids.get('niveau_1e_scheids', 1)
                max_niveau_2e = min(niveau_1e + 1, 5)
                
                with col1:
                    st.write(f"**NBB-nummer:** {nbb}")
                    # Status tonen met icoon
                    status = scheids.get("scheids_status", "Actief")
                    status_icon = {"Actief": "✅", "Op te leiden": "🎯", "Inactief": "⏸️"}.get(status, "")
                    if status != "Actief":
                        st.write(f"**Status:** {status_icon} {status}")
                    st.write(f"**BS2 diploma:** {'Ja' if scheids.get('bs2_diploma') else 'Nee'}")
                    st.write(f"**Niet op zondag:** {'Ja' if scheids.get('niet_op_zondag') else 'Nee'}")
                    if scheids.get("uitgesloten_van_pool"):
                        st.write("**🧪 Uitgesloten van pool:** Ja")
                    # Blessure indicator
                    if scheids.get("geblesseerd_tm"):
                        st.write(f"**🤕 Geblesseerd t/m:** {scheids.get('geblesseerd_tm')}")
                
                with col2:
                    st.write(f"**1e scheids t/m niveau:** {niveau_1e}")
                    st.write(f"**2e scheids t/m niveau:** {max_niveau_2e}")
                    st.write(f"**Eigen teams:** {', '.join(scheids.get('eigen_teams', [])) or '-'}")
                
                # Geblokkeerde dagen tonen
                geblokkeerde_dagen = scheids.get("geblokkeerde_dagen", [])
                if geblokkeerde_dagen:
                    # Sorteer en filter op toekomstige dagen
                    toekomstige_blokkades = sorted([d for d in geblokkeerde_dagen if d >= datetime.now().strftime("%Y-%m-%d")])
                    if toekomstige_blokkades:
                        st.write(f"**🚫 Geblokkeerde dagen:** {', '.join(toekomstige_blokkades)}")
                
                # Begeleidingsinfo tonen indien aanwezig
                if scheids.get("open_voor_begeleiding", False):
                    st.divider()
                    st.write("**🎓 Open voor begeleiding**")
                    if scheids.get("begeleiding_reden"):
                        st.write(f"*{scheids.get('begeleiding_reden')}*")
                    if scheids.get("telefoon_begeleiding"):
                        st.write(f"📱 {scheids.get('telefoon_begeleiding')}")
                
                # Link voor inschrijving
                st.code(f"?nbb={nbb}")
    
    st.divider()
    
    # Scheidsrechters per team overzicht
    st.subheader("👥 Scheidsrechters per team")
    st.caption("Overzicht welke scheidsrechters per team in BOB staan - handig om te delen met coaches/captains")
    
    # Groepeer scheidsrechters per team
    scheids_per_team = {}
    for team in SCHEIDSRECHTER_TEAMS:
        scheids_per_team[team] = []
    
    for nbb, scheids in scheidsrechters.items():
        eigen_teams = scheids.get("eigen_teams", [])
        for team in eigen_teams:
            if team in scheids_per_team:
                scheids_per_team[team].append({
                    "nbb": nbb,
                    "naam": scheids.get("naam", "?"),
                    "niveau": scheids.get("niveau_1e_scheids", 1),
                    "bs2": scheids.get("bs2_diploma", False),
                    "status": scheids.get("scheids_status", "Actief")
                })
    
    # Filter: alleen teams met scheidsrechters
    teams_met_scheids = {team: spelers for team, spelers in scheids_per_team.items() if spelers}
    
    if teams_met_scheids:
        # Team selectie
        geselecteerd_team = st.selectbox(
            "Selecteer team",
            options=["Alle teams"] + list(teams_met_scheids.keys()),
            key="team_overzicht_selectie"
        )
        
        # Toon tabel per team
        if geselecteerd_team == "Alle teams":
            teams_to_show = teams_met_scheids
        else:
            teams_to_show = {geselecteerd_team: teams_met_scheids[geselecteerd_team]}
        
        for team, spelers in teams_to_show.items():
            with st.expander(f"**{team}** ({len(spelers)} scheidsrechter{'s' if len(spelers) != 1 else ''})", expanded=(geselecteerd_team != "Alle teams")):
                # Sorteer op naam
                spelers_sorted = sorted(spelers, key=lambda x: x["naam"])
                
                # Maak tabel data
                team_data = []
                for sp in spelers_sorted:
                    status_icon = {"Actief": "", "Op te leiden": "🎯", "Inactief": "⏸️"}.get(sp["status"], "")
                    team_data.append({
                        "Naam": sp["naam"],
                        "Niveau": sp["niveau"],
                        "BS2": "✓" if sp["bs2"] else "",
                        "Status": status_icon
                    })
                
                if team_data:
                    import pandas as pd
                    df_team = pd.DataFrame(team_data)
                    st.dataframe(df_team, use_container_width=True, hide_index=True)
                    
                    # Kopieerbare tekst voor WhatsApp
                    namen_lijst = ", ".join([sp["naam"] for sp in spelers_sorted])
                    st.text_area(
                        "📋 Kopieer voor WhatsApp:",
                        f"Scheidsrechters {team} in BOB: {namen_lijst}",
                        height=68,
                        key=f"copy_team_{team}"
                    )
    else:
        st.info("Nog geen scheidsrechters gekoppeld aan teams.")
    
    st.divider()
    
    # Nieuwe scheidsrechter toevoegen
    st.subheader("➕ Nieuwe scheidsrechter toevoegen")
    
    with st.form("nieuwe_scheidsrechter"):
        col1, col2 = st.columns(2)
        with col1:
            nbb_nummer = st.text_input("NBB-nummer")
            naam = st.text_input("Naam")
            bs2_diploma = st.checkbox("BS2 diploma")
            niet_op_zondag = st.checkbox("Niet op zondag")
        with col2:
            niveau_1e = st.selectbox("1e scheids t/m niveau", [1, 2, 3, 4, 5], index=1)
            # 2e scheids niveau wordt automatisch berekend
            st.info(f"2e scheids niveau wordt automatisch berekend (niveau + 1)")
            min_wed = st.number_input("Minimum wedstrijden", min_value=0, value=2)
        
        eigen_teams = st.multiselect("Eigen teams", options=SCHEIDSRECHTER_TEAMS)
        
        if st.form_submit_button("Toevoegen"):
            if nbb_nummer and naam:
                # niveau_2e wordt automatisch berekend
                niveau_2e = min(niveau_1e + 1, 5)
                scheidsrechters[nbb_nummer] = {
                    "naam": naam,
                    "bs2_diploma": bs2_diploma,
                    "niet_op_zondag": niet_op_zondag,
                    "niveau_1e_scheids": niveau_1e,
                    "niveau_2e_scheids": niveau_2e,
                    "min_wedstrijden": min_wed,
                    "eigen_teams": eigen_teams
                }
                sla_scheidsrechter_op(nbb_nummer, scheidsrechters[nbb_nummer])
                st.success("Scheidsrechter toegevoegd!")
                st.rerun()
            else:
                st.error("NBB-nummer en naam zijn verplicht")

def toon_capaciteit_monitor():
    """Toon capaciteitsanalyse: vraag vs aanbod per niveau, met speciale BS2/MSE analyse."""
    scheidsrechters = laad_scheidsrechters()
    wedstrijden = laad_wedstrijden()
    nu = datetime.now()
    
    st.subheader("📈 Capaciteitsmonitor")
    st.caption("Analyse van scheidsrechtercapaciteit vs wedstrijdbehoefte per niveau")
    
    # Filter alleen toekomstige thuiswedstrijden
    toekomstige_wedstrijden = {}
    for wed_id, wed in wedstrijden.items():
        if wed.get("type", "thuis") != "thuis":
            continue
        if wed.get("geannuleerd", False):
            continue
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        if wed_datum > nu:
            toekomstige_wedstrijden[wed_id] = wed
    
    # ============================================================
    # BS2/MSE ANALYSE (PRIORITEIT)
    # ============================================================
    st.write("### 🏀 BS2/MSE Analyse (Prioriteit)")
    st.caption("MSE wedstrijden vereisen BS2 diploma en hebben voorrang")
    
    # Tel MSE wedstrijden (bs2_vereist of team bevat MSE)
    mse_wedstrijden = []
    mse_posities_nodig = 0
    mse_posities_ingevuld = 0
    
    andere_niveau5_wedstrijden = []
    andere_niveau5_posities_nodig = 0
    andere_niveau5_posities_ingevuld = 0
    
    for wed_id, wed in toekomstige_wedstrijden.items():
        is_bs2_vereist = wed.get("bs2_vereist", False)
        thuisteam = wed.get("thuisteam", "")
        uitteam = wed.get("uitteam", "")
        is_mse = is_bs2_vereist or "MSE" in thuisteam.upper() or "MSE" in uitteam.upper()
        niveau = wed.get("niveau", 1)
        
        if is_mse:
            mse_wedstrijden.append(wed)
            mse_posities_nodig += 2
            if wed.get("scheids_1"):
                mse_posities_ingevuld += 1
            if wed.get("scheids_2"):
                mse_posities_ingevuld += 1
        elif niveau == 5:
            andere_niveau5_wedstrijden.append(wed)
            andere_niveau5_posities_nodig += 2
            if wed.get("scheids_1"):
                andere_niveau5_posities_ingevuld += 1
            if wed.get("scheids_2"):
                andere_niveau5_posities_ingevuld += 1
    
    # Tel BS2 scheidsrechters en hun capaciteit
    bs2_scheidsrechters = []
    bs2_min_capaciteit = 0
    
    for nbb, scheids in scheidsrechters.items():
        if scheids.get("bs2_diploma", False):
            min_wed = scheids.get("min_wedstrijden", 0)
            eigen_teams = scheids.get("eigen_teams", [])
            
            # Check of deze scheids MSE speelt (kan eigen wedstrijden niet fluiten)
            speelt_mse = any("MSE" in t.upper() for t in eigen_teams) if eigen_teams else False
            
            bs2_scheidsrechters.append({
                "nbb": nbb,
                "naam": scheids.get("naam", "?"),
                "min": min_wed,
                "niveau": scheids.get("niveau_1e_scheids", 5),
                "speelt_mse": speelt_mse
            })
            bs2_min_capaciteit += min_wed
    
    # Toon BS2 metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("MSE wedstrijden", len(mse_wedstrijden))
    with col2:
        st.metric("MSE posities nodig", mse_posities_nodig)
    with col3:
        st.metric("BS2 scheidsrechters", len(bs2_scheidsrechters))
    with col4:
        st.metric("BS2 min. capaciteit", bs2_min_capaciteit)
    
    # Analyse BS2 capaciteit
    mse_nog_open = mse_posities_nodig - mse_posities_ingevuld
    totaal_niveau5_nodig = mse_posities_nodig + andere_niveau5_posities_nodig
    
    # MSE spelers kunnen eigen wedstrijden niet fluiten - schat impact
    mse_spelers = [s for s in bs2_scheidsrechters if s["speelt_mse"]]
    niet_mse_bs2 = [s for s in bs2_scheidsrechters if not s["speelt_mse"]]
    
    # Effectieve capaciteit voor MSE = niet-MSE BS2 scheidsrechters + deel van MSE spelers
    # MSE spelers kunnen andere MSE wedstrijden fluiten, maar niet hun eigen
    effectieve_mse_capaciteit = sum(s["min"] for s in niet_mse_bs2)
    # MSE spelers kunnen ~helft van hun capaciteit voor andere MSE wedstrijden gebruiken (grove schatting)
    effectieve_mse_capaciteit += sum(s["min"] for s in mse_spelers) // 2 if mse_spelers else 0
    
    # Status bepalen
    if mse_posities_nodig == 0:
        st.success("✅ Geen MSE wedstrijden gepland")
    elif effectieve_mse_capaciteit >= mse_posities_nodig:
        st.success(f"✅ **MSE capaciteit voldoende** — {effectieve_mse_capaciteit} beschikbaar voor {mse_posities_nodig} posities")
    elif bs2_min_capaciteit >= mse_posities_nodig:
        st.warning(f"⚠️ **MSE capaciteit krap** — Let op: sommige BS2 scheidsrechters spelen zelf MSE en kunnen eigen wedstrijden niet fluiten")
    else:
        tekort = mse_posities_nodig - bs2_min_capaciteit
        st.error(f"❌ **MSE capaciteit tekort** — {tekort} posities tekort (zelfs bij minimum inzet)")
    
    # Detail expander
    with st.expander("📋 BS2/MSE Details"):
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.write("**MSE Wedstrijden:**")
            st.write(f"- Aantal wedstrijden: {len(mse_wedstrijden)}")
            st.write(f"- Posities nodig: {mse_posities_nodig}")
            st.write(f"- Al ingevuld: {mse_posities_ingevuld}")
            st.write(f"- Nog open: {mse_nog_open}")
            
            st.write("")
            st.write("**Andere niveau 5 wedstrijden:**")
            st.write(f"- Aantal wedstrijden: {len(andere_niveau5_wedstrijden)}")
            st.write(f"- Posities nodig: {andere_niveau5_posities_nodig}")
            st.write(f"- Al ingevuld: {andere_niveau5_posities_ingevuld}")
        
        with col_b:
            st.write("**BS2 Scheidsrechters:**")
            if bs2_scheidsrechters:
                for s in sorted(bs2_scheidsrechters, key=lambda x: x["naam"]):
                    mse_tag = " 🏀" if s["speelt_mse"] else ""
                    st.write(f"- {s['naam']} (min {s['min']}, niv {s['niveau']}){mse_tag}")
                
                if mse_spelers:
                    st.caption("🏀 = speelt zelf MSE (kan eigen wedstrijden niet fluiten)")
            else:
                st.warning("Geen BS2 scheidsrechters geregistreerd!")
        
        # Prioriteitsadvies
        st.write("")
        st.write("**⚡ Prioriteitsvolgorde:**")
        st.write("1. **MSE wedstrijden** eerst bezetten (BS2 vereist)")
        st.write("2. **Andere niveau 5** wedstrijden daarna")
        st.write("3. BS2 scheidsrechters die MSE spelen kunnen hun eigen wedstrijden niet fluiten")
    
    st.divider()
    
    # ============================================================
    # REGULIERE NIVEAU ANALYSE
    # ============================================================
    
    # Bereken behoefte per niveau (elke wedstrijd heeft 2 scheidsrechters nodig)
    # Let op: MSE wedstrijden tellen NIET mee bij niveau 5 (apart behandeld)
    behoefte_per_niveau = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    ingevuld_per_niveau = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    for wed_id, wed in toekomstige_wedstrijden.items():
        niveau = wed.get("niveau", 1)
        is_bs2_vereist = wed.get("bs2_vereist", False)
        thuisteam = wed.get("thuisteam", "")
        uitteam = wed.get("uitteam", "")
        is_mse = is_bs2_vereist or "MSE" in thuisteam.upper() or "MSE" in uitteam.upper()
        
        # MSE apart behandeld, sla over
        if is_mse:
            continue
            
        behoefte_per_niveau[niveau] += 2
        
        if wed.get("scheids_1"):
            ingevuld_per_niveau[niveau] += 1
        if wed.get("scheids_2"):
            ingevuld_per_niveau[niveau] += 1
    
    # Bereken minimumcapaciteit per niveau
    capaciteit_min_per_niveau = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    scheids_per_niveau = {1: [], 2: [], 3: [], 4: [], 5: []}
    
    for nbb, scheids in scheidsrechters.items():
        niveau_1e = scheids.get("niveau_1e_scheids", 1)
        min_wed = scheids.get("min_wedstrijden", 0)
        has_bs2 = scheids.get("bs2_diploma", False)
        
        # Scheidsrechter kan alle niveaus t/m hun niveau fluiten
        for niveau in range(1, niveau_1e + 1):
            scheids_per_niveau[niveau].append({
                "nbb": nbb,
                "naam": scheids.get("naam", "?"),
                "min": min_wed,
                "eigen_niveau": niveau_1e,
                "bs2": has_bs2
            })
        
        # Tel capaciteit alleen bij eigen niveau (voorkomt dubbeltelling)
        capaciteit_min_per_niveau[niveau_1e] += min_wed
    
    # Bereken cumulatieve capaciteit (niveau 5 scheids kan ook niveau 1-4)
    cumulatief_min = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    running_min = 0
    for niveau in range(5, 0, -1):
        running_min += capaciteit_min_per_niveau[niveau]
        cumulatief_min[niveau] = running_min
    
    # Bereken cumulatieve behoefte
    cumulatief_behoefte = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    running_behoefte = 0
    for niveau in range(5, 0, -1):
        running_behoefte += behoefte_per_niveau[niveau]
        cumulatief_behoefte[niveau] = running_behoefte
    
    # Overzichtstabel
    st.write("### 📊 Overzicht per niveau (excl. MSE)")
    
    # Header metrics
    totaal_behoefte = sum(behoefte_per_niveau.values())
    totaal_ingevuld = sum(ingevuld_per_niveau.values())
    totaal_min = sum(capaciteit_min_per_niveau.values())
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Totaal nodig", totaal_behoefte, help="Aantal scheidsrechterposities (excl. MSE)")
    with col2:
        st.metric("Al ingevuld", totaal_ingevuld)
    with col3:
        st.metric("Min. capaciteit", totaal_min, help="Som van alle minimum wedstrijden")
    
    # Realisatiekans
    if totaal_behoefte > 0:
        if totaal_min >= totaal_behoefte:
            realisatie_tekst = "✅ Voldoende capaciteit"
        else:
            tekort = totaal_behoefte - totaal_min
            realisatie_tekst = f"⚠️ Tekort van {tekort} posities (afhankelijk van extra inzet)"
        
        st.markdown(f"### Realisatiekans: **{realisatie_tekst}**")
        st.caption("*Scheidsrechters kunnen meer fluiten dan hun minimum, dus een klein tekort is vaak geen probleem.*")
    
    st.divider()
    
    # Detail per niveau
    st.write("### 📋 Detail per niveau")
    
    # Uitleg
    with st.expander("ℹ️ **Uitleg: Waarom cumulatief?**"):
        st.write("""
**Het principe:** Een scheidsrechter kan "omlaag" fluiten, maar niet "omhoog".
- Niveau 5 scheidsrechter → kan niveau 5, 4, 3, 2, 1 fluiten ✓
- Niveau 4 scheidsrechter → kan niveau 4, 3, 2, 1 fluiten, maar **niet** niveau 5 ✗

**Daarom kijken we cumulatief van hoog naar laag:**
- Eerst moeten niveau 5 wedstrijden gevuld worden (alleen door niveau 5 scheidsrechters)
- Wat overblijft van niveau 5 capaciteit kan helpen bij niveau 4
- Enzovoort...

**Voorbeeld:**  
Als je 20 niveau 5 posities hebt en 20 niveau 5 scheidsrechters (exact genoeg), 
dan kunnen die scheidsrechters **niet** meer helpen bij niveau 4 wedstrijden.
        """)
    
    problemen = []
    
    for niveau in range(5, 0, -1):
        behoefte = behoefte_per_niveau[niveau]
        ingevuld = ingevuld_per_niveau[niveau]
        cap_min = capaciteit_min_per_niveau[niveau]
        cum_behoefte = cumulatief_behoefte[niveau]
        cum_min = cumulatief_min[niveau]
        
        # Bepaal status
        nog_nodig = behoefte - ingevuld
        
        if cum_min >= cum_behoefte:
            status = "✅"
            status_tekst = "OK"
        else:
            tekort = cum_behoefte - cum_min
            status = "⚠️"
            status_tekst = f"Tekort: {tekort} (extra inzet nodig)"
            problemen.append(f"Niveau {niveau}: {tekort} posities boven minimum nodig")
        
        niveau_label = f"Niveau {niveau}"
        if niveau == 5:
            niveau_label = "Niveau 5 (excl. MSE)"
        
        with st.expander(f"{status} **{niveau_label}** — Nodig: {behoefte} | Ingevuld: {ingevuld} | Scheids: {len(scheids_per_niveau[niveau])}"):
            # Sectie 1: Dit niveau alleen
            st.write("#### 📍 Dit niveau alleen")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.write(f"**Wedstrijden niveau {niveau}:** {behoefte // 2}")
                st.write(f"**Posities nodig:** {behoefte}")
                st.write(f"**Al ingevuld:** {ingevuld}")
                st.write(f"**Nog open:** {nog_nodig}")
            with col_a2:
                # Tel scheidsrechters met dit als EIGEN niveau
                eigen_niveau_scheids = [s for s in scheids_per_niveau[niveau] if s["eigen_niveau"] == niveau]
                st.write(f"**Scheidsrechters niveau {niveau}:** {len(eigen_niveau_scheids)}")
                st.write(f"**Hun min. capaciteit:** {cap_min}")
            
            st.write("---")
            
            # Sectie 2: Cumulatief met uitleg
            st.write(f"#### 📊 Cumulatief: niveau {niveau} t/m 5")
            st.caption(f"*Wie kan niveau {niveau} fluiten? Alle scheidsrechters van niveau {niveau} en hoger.*")
            
            # Bouw breakdown tabel
            st.write("**Opbouw behoefte:**")
            breakdown_behoefte = []
            breakdown_capaciteit = []
            for n in range(5, niveau - 1, -1):
                niv_label = f"Niveau {n}"
                if n == 5:
                    niv_label = "Niveau 5 (excl. MSE)"
                breakdown_behoefte.append(f"- {niv_label}: {behoefte_per_niveau[n]} posities")
                
                # Capaciteit van scheidsrechters met dit als EIGEN niveau
                eigen_cap = capaciteit_min_per_niveau[n]
                eigen_count = len([s for s in scheids_per_niveau[n] if s["eigen_niveau"] == n])
                breakdown_capaciteit.append(f"- Niveau {n} scheidsrechters: {eigen_count} personen, min {eigen_cap} wedstrijden")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                for line in breakdown_behoefte:
                    st.write(line)
                st.write(f"**Totaal nodig: {cum_behoefte}**")
            
            with col_b2:
                st.write("**Opbouw capaciteit:**")
                for line in breakdown_capaciteit:
                    st.write(line)
                st.write(f"**Totaal capaciteit: {cum_min}**")
            
            # Conclusie
            st.write("")
            if cum_min >= cum_behoefte:
                overschot = cum_min - cum_behoefte
                st.success(f"✅ **Voldoende** — {overschot} posities over (bij minimum inzet)")
            else:
                tekort = cum_behoefte - cum_min
                st.warning(f"⚠️ **{tekort} extra inzet nodig** boven het minimum")
            
            # Toon scheidsrechters voor dit niveau
            st.write("---")
            st.write(f"#### 👥 Alle scheidsrechters die niveau {niveau} kunnen fluiten")
            if scheids_per_niveau[niveau]:
                scheids_tekst = []
                for s in sorted(scheids_per_niveau[niveau], key=lambda x: (-x["eigen_niveau"], x["naam"])):
                    eigen = f" ★niv{s['eigen_niveau']}" if s["eigen_niveau"] != niveau else " ★"
                    bs2_tag = " 🎓" if s.get("bs2") else ""
                    scheids_tekst.append(f"{s['naam']} (min {s['min']}){eigen}{bs2_tag}")
                st.write(", ".join(scheids_tekst))
                st.caption("★ = eigen niveau | 🎓 = BS2 diploma")
    
    # Advies sectie
    st.divider()
    st.write("### 💡 Advies")
    
    alle_problemen = []
    
    # BS2/MSE problemen eerst
    if mse_posities_nodig > 0 and bs2_min_capaciteit < mse_posities_nodig:
        tekort = mse_posities_nodig - bs2_min_capaciteit
        alle_problemen.append(f"**BS2/MSE**: Tekort van {tekort} posities — werf meer BS2 scheidsrechters of verhoog hun minimum")
    elif mse_posities_nodig > 0 and effectieve_mse_capaciteit < mse_posities_nodig:
        alle_problemen.append(f"**BS2/MSE**: Capaciteit krap — sommige MSE spelers moeten buiten eigen wedstrijden fluiten")
    
    # Reguliere problemen
    alle_problemen.extend(problemen)
    
    if not alle_problemen:
        st.success("**Geen capaciteitsproblemen.** De minimum inzet van alle scheidsrechters is voldoende om alle wedstrijden te bezetten.")
    else:
        st.info("**Aandachtspunten:**")
        for probleem in alle_problemen:
            st.write(f"- {probleem}")
        
        st.write("")
        st.write("**Mogelijke oplossingen:**")
        st.write("- Scheidsrechters motiveren om boven hun minimum te fluiten (punten/ranking)")
        st.write("- Minimums verhogen voor scheidsrechters met ruimte in hun schema")
        st.write("- Nieuwe scheidsrechters werven op de niveaus met tekort")

def toon_beloningen_beheer():
    """Beheer beloningen: ranglijst, strikes, klusjes."""
    scheidsrechters = laad_scheidsrechters()
    beloningen = laad_beloningen()
    klusjes = laad_klusjes()
    verzoeken = laad_vervangingsverzoeken()
    
    st.subheader("🏆 Beloningen & Strikes Beheer")
    
    subtab1, subtab2, subtab3, subtab4, subtab5, subtab6 = st.tabs([
        "📊 Ranglijst", 
        "✏️ Punten & Strikes", 
        "🔧 Klusjes Toewijzen",
        "📋 Klusjes Instellingen",
        "🔄 Vervangingsverzoeken",
        "🎓 Begeleiding Feedback"
    ])
    
    with subtab1:
        st.write("**Ranglijst (gesorteerd op punten)**")
        
        ranglijst = get_ranglijst()
        
        if not ranglijst:
            st.info("Nog geen punten geregistreerd.")
        else:
            for idx, speler in enumerate(ranglijst, 1):
                # Bepaal medaille
                if idx == 1:
                    medaille = "🥇"
                elif idx == 2:
                    medaille = "🥈"
                elif idx == 3:
                    medaille = "🥉"
                else:
                    medaille = f"#{idx}"
                
                # Toon strikes indicator
                strikes_indicator = ""
                if speler["strikes"] >= 5:
                    strikes_indicator = " ⚠️ (gesprek TC)"
                elif speler["strikes"] >= 3:
                    strikes_indicator = " ⚠️"
                
                with st.expander(f"{medaille} {speler['naam']} — 🏆 {speler['punten']} punten | ⚠️ {speler['strikes']} strikes{strikes_indicator}"):
                    # Haal gedetailleerde stats op
                    speler_details = get_speler_stats(speler["nbb_nummer"])
                    
                    col_wed, col_handmatig = st.columns(2)
                    
                    with col_wed:
                        if speler_details["gefloten_wedstrijden"]:
                            st.write("**Wedstrijd punten:**")
                            wedstrijden_data = laad_wedstrijden()
                            for wed_reg in reversed(speler_details["gefloten_wedstrijden"][-10:]):  # Laatste 10
                                wed = wedstrijden_data.get(wed_reg.get("wed_id", ""), {})
                                wed_naam = f"{wed.get('thuisteam', '?')} vs {wed.get('uitteam', '?')}" if wed else "Onbekende wedstrijd"
                                
                                berekening = wed_reg.get("berekening", {})
                                if berekening:
                                    st.markdown(f"""
                                    - **+{wed_reg['punten']}** - {wed_naam}  
                                      *{berekening.get('inschrijf_moment_leesbaar', '?')} | {berekening.get('uren_tot_wedstrijd', '?')}u tot wed*
                                    """)
                                else:
                                    st.markdown(f"- **+{wed_reg['punten']}** - {wed_naam}")
                        else:
                            st.caption("Geen wedstrijd punten.")
                        
                        # Handmatige aanpassingen
                        if speler_details.get("punten_log"):
                            st.write("**Handmatige aanpassingen:**")
                            for entry in reversed(speler_details["punten_log"][-5:]):
                                datum = datetime.fromisoformat(entry["datum"]).strftime("%d-%m %H:%M")
                                teken = "+" if entry["punten"] > 0 else ""
                                st.markdown(f"- **{teken}{entry['punten']}** ({entry['oude_stand']}→{entry['nieuwe_stand']}) *{datum}*  \n  {entry['reden']}")
                    
                    with col_handmatig:
                        if speler_details["strike_log"]:
                            st.write("**Strike historie:**")
                            for strike in reversed(speler_details["strike_log"][-8:]):  # Laatste 8
                                datum = datetime.fromisoformat(strike["datum"]).strftime("%d-%m %H:%M")
                                teken = "+" if strike["strikes"] > 0 else ""
                                st.markdown(f"- **{teken}{strike['strikes']}** *{datum}*  \n  {strike['reden']}")
                        else:
                            st.caption("Geen strikes.")
            
            # Clinic drempel info
            st.divider()
            clinic_kandidaten = [s for s in ranglijst if s["punten"] >= 10]
            if clinic_kandidaten:
                st.success(f"**{len(clinic_kandidaten)} speler(s)** hebben 10+ punten en kunnen een voucher Clinic claimen!")
                for k in clinic_kandidaten:
                    st.write(f"  • {k['naam']} ({k['punten']} punten)")
    
    with subtab2:
        st.write("**Punten & Strikes aanpassen**")
        st.caption("Handmatig bijboeken of afboeken met verplichte omschrijving voor audit trail.")
        
        # Selecteer speler
        speler_opties = {f"{s['naam']} (NBB: {nbb})": nbb for nbb, s in scheidsrechters.items()}
        
        if speler_opties:
            geselecteerde_speler = st.selectbox("Selecteer speler", options=list(speler_opties.keys()))
            geselecteerde_nbb = speler_opties[geselecteerde_speler]
            
            # Toon huidige status
            stats = get_speler_stats(geselecteerde_nbb)
            
            col_status1, col_status2 = st.columns(2)
            with col_status1:
                st.metric("🏆 Punten", stats['punten'])
            with col_status2:
                st.metric("⚠️ Strikes", stats['strikes'])
            
            st.divider()
            
            # Punten sectie
            st.subheader("🏆 Punten aanpassen")
            
            col_punten_plus, col_punten_min = st.columns(2)
            
            with col_punten_plus:
                st.write("**Punten bijboeken**")
                punten_bij = st.number_input("Aantal punten", min_value=1, max_value=50, value=1, key="punten_bij")
                punten_bij_reden = st.text_input("Reden (verplicht)", key="punten_bij_reden", placeholder="bijv. Correctie, extra beloning, etc.")
                
                if st.button("➕ Punten bijboeken", type="primary", key="btn_punten_bij"):
                    if punten_bij_reden.strip():
                        pas_punten_aan(geselecteerde_nbb, punten_bij, f"Bijgeboekt: {punten_bij_reden}")
                        st.success(f"+{punten_bij} punten toegevoegd!")
                        st.rerun()
                    else:
                        st.error("Vul een reden in")
            
            with col_punten_min:
                st.write("**Punten afboeken**")
                punten_af = st.number_input("Aantal punten", min_value=1, max_value=50, value=1, key="punten_af")
                punten_af_reden = st.text_input("Reden (verplicht)", key="punten_af_reden", placeholder="bijv. Voucher verzilverd, correctie, etc.")
                
                if st.button("➖ Punten afboeken", key="btn_punten_af"):
                    if punten_af_reden.strip():
                        pas_punten_aan(geselecteerde_nbb, -punten_af, f"Afgeboekt: {punten_af_reden}")
                        st.success(f"-{punten_af} punten verwijderd!")
                        st.rerun()
                    else:
                        st.error("Vul een reden in")
            
            st.divider()
            
            # Strikes sectie
            st.subheader("⚠️ Strikes aanpassen")
            
            col_strikes_plus, col_strikes_min = st.columns(2)
            
            with col_strikes_plus:
                st.write("**Strike toevoegen**")
                strike_reden = st.selectbox("Reden", [
                    "No-show (5 strikes)",
                    "Afmelding <24 uur (2 strikes)",
                    "Afmelding <48 uur (1 strike)",
                    "Overig"
                ])
                
                if strike_reden == "No-show (5 strikes)":
                    strike_aantal = 5
                elif strike_reden == "Afmelding <24 uur (2 strikes)":
                    strike_aantal = 2
                elif strike_reden == "Afmelding <48 uur (1 strike)":
                    strike_aantal = 1
                else:
                    strike_aantal = st.number_input("Aantal strikes", min_value=1, max_value=10, value=1)
                
                strike_opmerking = st.text_input("Opmerking (optioneel)", key="strike_opmerking")
                
                if st.button("⚠️ Strike toekennen", type="primary"):
                    reden_tekst = f"{strike_reden}"
                    if strike_opmerking:
                        reden_tekst += f" - {strike_opmerking}"
                    voeg_strike_toe(geselecteerde_nbb, strike_aantal, reden_tekst)
                    st.success(f"+{strike_aantal} strike(s) toegekend!")
                    st.rerun()
            
            with col_strikes_min:
                st.write("**Strike verwijderen**")
                verwijder_aantal = st.number_input("Aantal strikes", min_value=1, max_value=10, value=1, key="strike_verwijder")
                verwijder_reden = st.text_input("Reden (verplicht)", key="strike_verwijder_reden", placeholder="bijv. Klusje afgerond, correctie, etc.")
                
                if st.button("✅ Strike verwijderen"):
                    if verwijder_reden.strip():
                        verwijder_strike(geselecteerde_nbb, verwijder_aantal, verwijder_reden)
                        st.success(f"-{verwijder_aantal} strike(s) verwijderd!")
                        st.rerun()
                    else:
                        st.error("Vul een reden in")
            
            st.divider()
            
            # Historie tonen
            st.subheader("📜 Aanpassingshistorie")
            
            # Haal punten_log op indien aanwezig
            beloningen = laad_beloningen()
            speler_data = beloningen.get("spelers", {}).get(geselecteerde_nbb, {})
            punten_log = speler_data.get("punten_log", [])
            strike_log = speler_data.get("strike_log", [])
            
            col_hist1, col_hist2 = st.columns(2)
            
            with col_hist1:
                st.write("**Punten historie:**")
                if punten_log:
                    for entry in reversed(punten_log[-10:]):
                        datum = datetime.fromisoformat(entry["datum"]).strftime("%d-%m-%Y %H:%M")
                        teken = "+" if entry["punten"] > 0 else ""
                        st.markdown(f"- **{teken}{entry['punten']}** ({entry['oude_stand']}→{entry['nieuwe_stand']})  \n  *{datum}*: {entry['reden']}")
                else:
                    st.caption("Geen handmatige aanpassingen.")
            
            with col_hist2:
                st.write("**Strikes historie:**")
                if strike_log:
                    for entry in reversed(strike_log[-10:]):
                        datum = datetime.fromisoformat(entry["datum"]).strftime("%d-%m-%Y %H:%M")
                        teken = "+" if entry["strikes"] > 0 else ""
                        st.markdown(f"- **{teken}{entry['strikes']}** - *{datum}*  \n  {entry['reden']}")
                else:
                    st.caption("Geen strikes geregistreerd.")
    
    with subtab3:
        st.write("**Klusjes beheer**")
        
        # Openstaande klusjes
        open_klusjes = {k_id: k for k_id, k in klusjes.items() if not k.get("afgerond", False)}
        
        if open_klusjes:
            st.write("**Openstaande klusjes:**")
            for k_id, klusje in open_klusjes.items():
                speler = scheidsrechters.get(klusje["nbb_nummer"], {})
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"**{speler.get('naam', 'Onbekend')}**: {klusje['naam']}")
                    with col2:
                        st.write(f"*{klusje['omschrijving'][:50]}...*" if len(klusje.get('omschrijving', '')) > 50 else klusje.get('omschrijving', ''))
                    with col3:
                        if st.button("✅ Afronden", key=f"afrond_{k_id}"):
                            klusjes[k_id]["afgerond"] = True
                            klusjes[k_id]["afgerond_op"] = datetime.now().isoformat()
                            sla_klusjes_op(klusjes)
                            
                            # Strike verwijderen
                            verwijder_strike(klusje["nbb_nummer"], klusje["strikes_waarde"], f"Klusje afgerond: {klusje['naam']}")
                            st.success(f"Klusje afgerond, {klusje['strikes_waarde']} strike(s) verwijderd!")
                            st.rerun()
        else:
            st.info("Geen openstaande klusjes.")
        
        st.divider()
        
        # Nieuw klusje toewijzen
        st.write("**Nieuw klusje toewijzen**")
        
        # Filter spelers met strikes
        spelers_met_strikes = []
        for nbb, s in scheidsrechters.items():
            stats = get_speler_stats(nbb)
            if stats["strikes"] > 0:
                spelers_met_strikes.append({
                    "nbb": nbb,
                    "naam": s["naam"],
                    "strikes": stats["strikes"]
                })
        
        if spelers_met_strikes:
            speler_opties = {f"{s['naam']} ({s['strikes']} strikes)": s['nbb'] for s in spelers_met_strikes}
            geselecteerde_speler = st.selectbox("Selecteer speler met strikes", options=list(speler_opties.keys()), key="klusje_speler")
            geselecteerde_nbb = speler_opties[geselecteerde_speler]
            
            klusje_opties = {k["naam"]: k for k in laad_beschikbare_klusjes()}
            geselecteerde_klusje = st.selectbox("Selecteer klusje", options=list(klusje_opties.keys()))
            klusje_data = klusje_opties[geselecteerde_klusje]
            
            st.info(f"**{klusje_data['naam']}**: {klusje_data['omschrijving']} (levert {klusje_data['strikes_waarde']} strike kwijtschelding op)")
            
            if st.button("📋 Klusje toewijzen", type="primary"):
                klusje_id = f"klusje_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                klusjes[klusje_id] = {
                    "id": klusje_id,
                    "nbb_nummer": geselecteerde_nbb,
                    "naam": klusje_data["naam"],
                    "omschrijving": klusje_data["omschrijving"],
                    "strikes_waarde": klusje_data["strikes_waarde"],
                    "afgerond": False,
                    "toegewezen_op": datetime.now().isoformat()
                }
                sla_klusjes_op(klusjes)
                st.success("Klusje toegewezen!")
                st.rerun()
        else:
            st.info("Geen spelers met strikes.")
    
    with subtab4:
        st.write("**Beschikbare klusjes beheren**")
        st.caption("Hier kun je de klusjes instellen die aan spelers met strikes kunnen worden toegewezen.")
        
        beschikbare_klusjes = laad_beschikbare_klusjes()
        
        # Toon huidige klusjes
        if beschikbare_klusjes:
            st.write("**Huidige klusjes:**")
            for idx, klusje in enumerate(beschikbare_klusjes):
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**{klusje['naam']}**")
                        st.caption(klusje['omschrijving'])
                    with col2:
                        st.write(f"*{klusje['strikes_waarde']} strike(s)*")
                    with col3:
                        if st.button("🗑️ Verwijderen", key=f"del_klusje_{idx}"):
                            beschikbare_klusjes.pop(idx)
                            sla_beschikbare_klusjes_op(beschikbare_klusjes)
                            st.rerun()
        else:
            st.info("Nog geen klusjes gedefinieerd.")
        
        st.divider()
        
        # Nieuw klusje toevoegen
        st.write("**Nieuw klusje toevoegen**")
        
        with st.form("nieuw_klusje_form"):
            nieuwe_naam = st.text_input("Naam", placeholder="bijv. Ballen oppompen")
            nieuwe_omschrijving = st.text_area("Omschrijving", placeholder="Beschrijf wat de speler moet doen...")
            nieuwe_strikes_waarde = st.number_input("Strikes kwijtschelding", min_value=1, max_value=5, value=1, help="Hoeveel strikes worden kwijtgescholden na afronding")
            
            if st.form_submit_button("➕ Klusje toevoegen", type="primary"):
                if nieuwe_naam and nieuwe_omschrijving:
                    nieuw_klusje = {
                        "id": f"klusje_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "naam": nieuwe_naam,
                        "omschrijving": nieuwe_omschrijving,
                        "strikes_waarde": nieuwe_strikes_waarde
                    }
                    beschikbare_klusjes.append(nieuw_klusje)
                    sla_beschikbare_klusjes_op(beschikbare_klusjes)
                    st.success(f"Klusje '{nieuwe_naam}' toegevoegd!")
                    st.rerun()
                else:
                    st.error("Vul naam en omschrijving in")
    
    with subtab5:
        st.write("**Openstaande vervangingsverzoeken**")
        
        open_verzoeken = {v_id: v for v_id, v in verzoeken.items() if v.get("status") == "pending"}
        
        if open_verzoeken:
            wedstrijden = laad_wedstrijden()
            
            for v_id, verzoek in open_verzoeken.items():
                wed = wedstrijden.get(verzoek["wed_id"], {})
                if not wed:
                    continue
                
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                aanvrager = scheidsrechters.get(verzoek["aanvrager_nbb"], {}).get("naam", "Onbekend")
                vervanger = scheidsrechters.get(verzoek["vervanger_nbb"], {}).get("naam", "Onbekend")
                
                # Check of wedstrijd al voorbij is
                is_verlopen = wed_datum < datetime.now()
                
                with st.container():
                    st.write(f"**{wed['thuisteam']} vs {wed['uitteam']}** ({wed_datum.strftime('%d-%m %H:%M')})")
                    st.write(f"Aanvrager: {aanvrager} → Vervanger: {vervanger}")
                    
                    if is_verlopen:
                        st.error("⚠️ Wedstrijd is voorbij zonder bevestiging!")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"Strike toekennen aan {aanvrager}", key=f"strike_{v_id}"):
                                # Bereken strikes dynamisch
                                beloningsinst = laad_beloningsinstellingen()
                                uren_tot_wed = (wed_datum - datetime.fromisoformat(verzoek["aangemaakt_op"])).total_seconds() / 3600
                                if uren_tot_wed < 24:
                                    strikes = beloningsinst["strikes_afmelding_24u"]
                                elif uren_tot_wed < 48:
                                    strikes = beloningsinst["strikes_afmelding_48u"]
                                else:
                                    strikes = 0
                                
                                if strikes > 0:
                                    voeg_strike_toe(verzoek["aanvrager_nbb"], strikes, f"Vervangingsverzoek niet bevestigd: {wed['thuisteam']} vs {wed['uitteam']}")
                                
                                verzoeken[v_id]["status"] = "expired"
                                sla_vervangingsverzoeken_op(verzoeken)
                                st.rerun()
                        with col2:
                            if st.button("Verzoek verwijderen", key=f"verwijder_{v_id}"):
                                verzoeken[v_id]["status"] = "cancelled"
                                sla_vervangingsverzoeken_op(verzoeken)
                                st.rerun()
                    else:
                        st.caption(f"Wacht op bevestiging van {vervanger}")
        else:
            st.info("Geen openstaande vervangingsverzoeken.")
    
    with subtab6:
        st.write("**Begeleiding Feedback Monitoring**")
        
        wedstrijden = laad_wedstrijden()
        feedback_data = laad_begeleiding_feedback()
        nu = datetime.now()
        
        # Debug: toon feedback records
        with st.expander("🔍 Debug: Feedback records in database", expanded=False):
            if feedback_data:
                for fb_id, fb in feedback_data.items():
                    st.caption(f"`{fb_id}` → status: {fb.get('status')}, speler: {fb.get('speler_nbb')}")
            else:
                st.caption("Geen feedback records gevonden")
        
        # Vind wedstrijden met begeleider die al gespeeld zijn
        wedstrijden_met_begeleiding = []
        for wed_id, wed in wedstrijden.items():
            if wed.get("geannuleerd", False):
                continue
            begeleider_nbb = wed.get("begeleider")
            if not begeleider_nbb:
                continue
            
            wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
            wed_eind = wed_datum + timedelta(hours=1, minutes=30)
            if wed_eind > nu:
                continue  # Nog niet gespeeld
            
            # Verzamel feedback van scheidsrechters
            scheids_1 = wed.get("scheids_1")
            scheids_2 = wed.get("scheids_2")
            
            fb_scheids_1 = feedback_data.get(f"fb_{wed_id}_{scheids_1}") if scheids_1 else None
            fb_scheids_2 = feedback_data.get(f"fb_{wed_id}_{scheids_2}") if scheids_2 else None
            
            wedstrijden_met_begeleiding.append({
                "wed_id": wed_id,
                "wed": wed,
                "wed_datum": wed_datum,
                "begeleider_nbb": begeleider_nbb,
                "scheids_1": scheids_1,
                "scheids_2": scheids_2,
                "fb_scheids_1": fb_scheids_1,
                "fb_scheids_2": fb_scheids_2
            })
        
        # Statistieken
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        totaal = len(wedstrijden_met_begeleiding)
        
        # Wacht op feedback = geen enkele echte feedback ontvangen
        # (als 1 scheidsrechter echte feedback gaf, is het klaar)
        def heeft_echte_feedback(fb):
            """Check of feedback echt is (niet alleen bevestigd)"""
            if not fb:
                return False
            status = fb.get("status", "")
            return status in ["aanwezig_geholpen", "aanwezig_niet_geholpen", "niet_aanwezig"]
        
        wacht_op_feedback = sum(1 for w in wedstrijden_met_begeleiding 
                                if not heeft_echte_feedback(w["fb_scheids_1"]) and 
                                   not heeft_echte_feedback(w["fb_scheids_2"]))
        
        with col_stat1:
            st.metric("Totaal met begeleiding", totaal)
        with col_stat2:
            st.metric("Wacht op feedback", wacht_op_feedback)
        with col_stat3:
            feedback_rate = f"{((totaal - wacht_op_feedback) / totaal * 100):.0f}%" if totaal > 0 else "-"
            st.metric("Response rate", feedback_rate)
        
        st.divider()
        
        # Filter
        filter_status = st.selectbox("Filter", [
            "Wacht op feedback",
            "Feedback ontvangen",
            "Alles"
        ])
        
        # Toon wedstrijden
        for item in sorted(wedstrijden_met_begeleiding, key=lambda x: x["wed_datum"], reverse=True):
            wed = item["wed"]
            begeleider_naam = scheidsrechters.get(item["begeleider_nbb"], {}).get("naam", "Onbekend")
            
            # Bepaal status - heeft minimaal 1 scheidsrechter echte feedback gegeven?
            fb_1 = item["fb_scheids_1"]
            fb_2 = item["fb_scheids_2"]
            scheids_1_naam = scheidsrechters.get(item["scheids_1"], {}).get("naam", "-") if item["scheids_1"] else "-"
            scheids_2_naam = scheidsrechters.get(item["scheids_2"], {}).get("naam", "-") if item["scheids_2"] else "-"
            
            heeft_feedback = heeft_echte_feedback(fb_1) or heeft_echte_feedback(fb_2)
            
            # Filter toepassen
            if filter_status == "Wacht op feedback" and heeft_feedback:
                continue
            if filter_status == "Feedback ontvangen" and not heeft_feedback:
                continue
            
            status_icons = {
                "aanwezig_geholpen": "✅",
                "aanwezig_niet_geholpen": "⚠️",
                "niet_aanwezig": "❌",
                "bevestigd": "👁️"
            }
            
            with st.expander(f"{item['wed_datum'].strftime('%d-%m %H:%M')} - {wed['thuisteam']} vs {wed['uitteam']} | Begeleider: **{begeleider_naam}**"):
                # Debug info
                st.caption(f"🔍 wed_id: `{item['wed_id']}` | Zoek: `fb_{item['wed_id']}_{item['scheids_1']}` en `fb_{item['wed_id']}_{item['scheids_2']}`")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**1e scheids:** {scheids_1_naam}")
                    if fb_1:
                        status = fb_1.get('status', '?')
                        icon = status_icons.get(status, '?')
                        label = "gezien" if status == "bevestigd" else status.replace('_', ' ')
                        st.write(f"{icon} {label}")
                        if st.button("🗑️ Reset", key=f"reset_fb1_{item['wed_id']}"):
                            verwijder_begeleiding_feedback(f"fb_{item['wed_id']}_{item['scheids_1']}")
                            st.rerun()
                    elif item["scheids_1"]:
                        st.warning("⏳ Wacht op feedback")
                
                with col2:
                    st.write(f"**2e scheids:** {scheids_2_naam}")
                    if fb_2:
                        status = fb_2.get('status', '?')
                        icon = status_icons.get(status, '?')
                        label = "gezien" if status == "bevestigd" else status.replace('_', ' ')
                        st.write(f"{icon} {label}")
                        if st.button("🗑️ Reset", key=f"reset_fb2_{item['wed_id']}"):
                            verwijder_begeleiding_feedback(f"fb_{item['wed_id']}_{item['scheids_2']}")
                            st.rerun()
                    elif item["scheids_2"]:
                        st.warning("⏳ Wacht op feedback")

def toon_instellingen_beheer():
    """Beheer instellingen."""
    instellingen = laad_instellingen()
    beloningsinst = laad_beloningsinstellingen()
    
    # Tabs voor verschillende instellingen categorieën
    tab_alg, tab_bel, tab_seizoen, tab_reset, tab_versie = st.tabs(["⚙️ Algemeen", "🏆 Beloningssysteem", "📅 Seizoen", "🗑️ Data Reset", "ℹ️ Over"])
    
    with tab_alg:
        st.subheader("Algemene Instellingen")
        
        # Deadline
        huidige_deadline = datetime.strptime(instellingen["inschrijf_deadline"], "%Y-%m-%d")
        nieuwe_deadline = st.date_input("Inschrijf deadline", value=huidige_deadline)
        
        if st.button("Deadline opslaan"):
            instellingen["inschrijf_deadline"] = nieuwe_deadline.strftime("%Y-%m-%d")
            sla_instellingen_op(instellingen)
            st.success("Deadline opgeslagen!")
        
        st.divider()
        
        # Niveaus
        st.subheader("Niveau-omschrijvingen")
        
        for niveau in ["1", "2", "3", "4", "5"]:
            instellingen["niveaus"][niveau] = st.text_input(
                f"Niveau {niveau}",
                value=instellingen["niveaus"].get(niveau, ""),
                key=f"niveau_{niveau}"
            )
        
        if st.button("Niveaus opslaan"):
            sla_instellingen_op(instellingen)
            st.success("Niveaus opgeslagen!")
    
    with tab_bel:
        st.subheader("🏆 Beloningssysteem Instellingen")
        st.caption("Pas hier de punten- en strike-waarden aan")
        
        # Huidige waarden tonen
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.metric("Punten voor voucher", beloningsinst["punten_voor_voucher"])
        with col_info2:
            st.metric("Waarschuwing bij strikes", beloningsinst["strikes_waarschuwing_bij"])
        with col_info3:
            st.metric("Gesprek TC bij strikes", beloningsinst["strikes_gesprek_bij"])
        
        st.divider()
        
        # Punten instellingen
        st.subheader("💰 Punten Verdienen")
        st.caption("Punten worden toegekend voor wedstrijden boven het minimum")
        
        with st.form("punten_instellingen"):
            col1, col2 = st.columns(2)
            
            with col1:
                punten_per_wedstrijd = st.number_input(
                    "Basispunten per wedstrijd",
                    min_value=1, max_value=10,
                    value=beloningsinst["punten_per_wedstrijd"],
                    help="Punten voor elke wedstrijd boven minimum"
                )
                
                punten_lastig = st.number_input(
                    "Bonus: lastig tijdstip",
                    min_value=0, max_value=10,
                    value=beloningsinst["punten_lastig_tijdstip"],
                    help="Extra punten als je apart moet terugkomen"
                )
                
                punten_inval_48 = st.number_input(
                    "Bonus: invallen <48 uur",
                    min_value=0, max_value=10,
                    value=beloningsinst["punten_inval_48u"],
                    help="Extra punten voor last-minute invallen"
                )
            
            with col2:
                punten_inval_24 = st.number_input(
                    "Bonus: invallen <24 uur",
                    min_value=0, max_value=10,
                    value=beloningsinst["punten_inval_24u"],
                    help="Extra punten voor zeer last-minute invallen"
                )
                
                punten_voucher = st.number_input(
                    "Punten voor voucher",
                    min_value=5, max_value=50,
                    value=beloningsinst["punten_voor_voucher"],
                    help="Hoeveel punten nodig voor een clinic voucher"
                )
            
            if st.form_submit_button("💾 Punten instellingen opslaan", type="primary"):
                beloningsinst["punten_per_wedstrijd"] = punten_per_wedstrijd
                beloningsinst["punten_lastig_tijdstip"] = punten_lastig
                beloningsinst["punten_inval_48u"] = punten_inval_48
                beloningsinst["punten_inval_24u"] = punten_inval_24
                beloningsinst["punten_voor_voucher"] = punten_voucher
                sla_beloningsinstellingen_op(beloningsinst)
                st.success("Punten instellingen opgeslagen!")
                st.rerun()
        
        st.divider()
        
        # Strikes instellingen
        st.subheader("⚠️ Strikes")
        st.caption("Strikes voor ongewenst gedrag")
        
        with st.form("strikes_instellingen"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Strikes toekennen:**")
                strikes_48 = st.number_input(
                    "Afmelding <48 uur",
                    min_value=0, max_value=5,
                    value=beloningsinst["strikes_afmelding_48u"],
                    help="Strikes bij late afmelding (zonder vervanging)"
                )
                
                strikes_24 = st.number_input(
                    "Afmelding <24 uur",
                    min_value=0, max_value=5,
                    value=beloningsinst["strikes_afmelding_24u"],
                    help="Strikes bij zeer late afmelding"
                )
                
                strikes_noshow = st.number_input(
                    "No-show",
                    min_value=0, max_value=10,
                    value=beloningsinst["strikes_no_show"],
                    help="Strikes bij niet komen opdagen"
                )
            
            with col2:
                st.write("**Strike drempels:**")
                strikes_waarschuwing = st.number_input(
                    "Waarschuwing bij",
                    min_value=1, max_value=10,
                    value=beloningsinst["strikes_waarschuwing_bij"],
                    help="Bij dit aantal strikes krijgt speler een waarschuwing"
                )
                
                strikes_gesprek = st.number_input(
                    "Gesprek TC bij",
                    min_value=1, max_value=10,
                    value=beloningsinst["strikes_gesprek_bij"],
                    help="Bij dit aantal strikes volgt een gesprek met TC"
                )
                
                strikes_vervallen = st.checkbox(
                    "Strikes vervallen einde seizoen",
                    value=beloningsinst["strikes_vervallen_einde_seizoen"],
                    help="Als aan: strikes worden gereset aan einde seizoen"
                )
            
            if st.form_submit_button("💾 Strike instellingen opslaan", type="primary"):
                beloningsinst["strikes_afmelding_48u"] = strikes_48
                beloningsinst["strikes_afmelding_24u"] = strikes_24
                beloningsinst["strikes_no_show"] = strikes_noshow
                beloningsinst["strikes_waarschuwing_bij"] = strikes_waarschuwing
                beloningsinst["strikes_gesprek_bij"] = strikes_gesprek
                beloningsinst["strikes_vervallen_einde_seizoen"] = strikes_vervallen
                sla_beloningsinstellingen_op(beloningsinst)
                st.success("Strike instellingen opgeslagen!")
                st.rerun()
        
        st.divider()
        
        # Strike reductie
        st.subheader("🔧 Strike Reductie")
        st.caption("Hoe spelers strikes kunnen wegwerken")
        
        with st.form("reductie_instellingen"):
            col1, col2 = st.columns(2)
            
            with col1:
                reductie_wedstrijd = st.number_input(
                    "Per extra wedstrijd",
                    min_value=0, max_value=5,
                    value=beloningsinst["strike_reductie_extra_wedstrijd"],
                    help="Strike reductie per extra gefloten wedstrijd"
                )
            
            with col2:
                reductie_invallen = st.number_input(
                    "Bij invallen <48u",
                    min_value=0, max_value=5,
                    value=beloningsinst["strike_reductie_invallen"],
                    help="Strike reductie bij last-minute invallen"
                )
            
            st.caption("*Klusjes hebben hun eigen strike-waarde (zie Klusjes Instellingen)*")
            
            if st.form_submit_button("💾 Reductie instellingen opslaan", type="primary"):
                beloningsinst["strike_reductie_extra_wedstrijd"] = reductie_wedstrijd
                beloningsinst["strike_reductie_invallen"] = reductie_invallen
                sla_beloningsinstellingen_op(beloningsinst)
                st.success("Reductie instellingen opgeslagen!")
                st.rerun()
        
        st.divider()
        
        # Reset naar defaults
        st.subheader("🔄 Reset")
        with st.expander("⚠️ Reset naar standaardwaarden"):
            st.warning("Dit zet alle beloningsinstellingen terug naar de standaardwaarden.")
            if st.button("Reset naar defaults", type="secondary"):
                sla_beloningsinstellingen_op(DEFAULT_BELONINGSINSTELLINGEN.copy())
                st.success("Instellingen gereset naar defaults!")
                st.rerun()
    
    with tab_seizoen:
        st.subheader("📅 Seizoen Beheer")
        
        # Huidig seizoen
        huidig_seizoen = db.get_huidig_seizoen()
        st.info(f"**Huidig seizoen:** {huidig_seizoen}")
        
        st.divider()
        
        # Seizoen afsluiten
        st.markdown("### 🔒 Seizoen afsluiten")
        st.caption("Archiveer statistieken en start een nieuw seizoen")
        
        with st.expander("⚠️ Seizoen afsluiten", expanded=False):
            st.warning("""
            **Dit doet het volgende:**
            1. Archiveert alle statistieken van dit seizoen (punten, strikes, gefloten wedstrijden, minimums)
            2. Reset alle beloningen (punten, strikes, logs) naar 0
            3. Wedstrijden en scheidsrechter gegevens blijven behouden
            
            **Let op:** Dit kan niet ongedaan worden gemaakt!
            """)
            
            # Voorvertoning statistieken
            scheidsrechters = laad_scheidsrechters()
            beloningen = laad_beloningen()
            wedstrijden = laad_wedstrijden()
            
            preview_stats = db.verzamel_seizoen_statistieken(scheidsrechters, beloningen, wedstrijden)
            totalen = preview_stats.get("totalen", {})
            
            col_prev1, col_prev2, col_prev3, col_prev4 = st.columns(4)
            with col_prev1:
                st.metric("Scheidsrechters", totalen.get("aantal_scheidsrechters", 0))
            with col_prev2:
                st.metric("Gespeelde wedstrijden", totalen.get("totaal_wedstrijden", 0))
            with col_prev3:
                st.metric("Totaal punten", totalen.get("totaal_punten_uitgedeeld", 0))
            with col_prev4:
                st.metric("Totaal strikes", totalen.get("totaal_strikes_uitgedeeld", 0))
            
            st.divider()
            
            # Bevestiging
            bevestig_seizoen = st.text_input(
                f"Type '{huidig_seizoen}' om te bevestigen",
                key="bevestig_seizoen_afsluiten"
            )
            
            if st.button("🔒 Sluit seizoen af en archiveer", type="primary", key="btn_sluit_seizoen"):
                if bevestig_seizoen == huidig_seizoen:
                    # Archiveer
                    if db.archiveer_seizoen(huidig_seizoen, preview_stats):
                        # Reset beloningen
                        success, aantal = db.reset_alle_beloningen()
                        if success:
                            st.success(f"✅ Seizoen {huidig_seizoen} gearchiveerd!")
                            st.success(f"✅ Beloningen gereset voor {aantal} spelers")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("Fout bij resetten beloningen")
                    else:
                        st.error("Fout bij archiveren seizoen")
                else:
                    st.warning(f"Type '{huidig_seizoen}' om te bevestigen")
        
        st.divider()
        
        # Archief bekijken
        st.markdown("### 📚 Seizoen Archief")
        
        archieven = db.laad_seizoen_archieven()
        
        if archieven:
            # Selecteer seizoen
            seizoen_opties = [a["seizoen"] for a in archieven]
            geselecteerd_seizoen = st.selectbox(
                "Selecteer seizoen",
                options=seizoen_opties,
                key="select_archief_seizoen"
            )
            
            if geselecteerd_seizoen:
                archief = db.laad_seizoen_archief(geselecteerd_seizoen)
                
                if archief:
                    afgesloten = archief.get("afgesloten_op", "")
                    if afgesloten:
                        try:
                            afgesloten_dt = datetime.fromisoformat(afgesloten.replace("Z", "+00:00"))
                            st.caption(f"Afgesloten op: {afgesloten_dt.strftime('%d-%m-%Y %H:%M')}")
                        except:
                            st.caption(f"Afgesloten op: {afgesloten}")
                    
                    stats = archief.get("statistieken", {})
                    totalen = stats.get("totalen", {})
                    spelers = stats.get("spelers", {})
                    
                    # Totalen
                    col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                    with col_t1:
                        st.metric("Scheidsrechters", totalen.get("aantal_scheidsrechters", 0))
                    with col_t2:
                        st.metric("Wedstrijden", totalen.get("totaal_wedstrijden", 0))
                    with col_t3:
                        st.metric("Punten uitgedeeld", totalen.get("totaal_punten_uitgedeeld", 0))
                    with col_t4:
                        st.metric("Strikes uitgedeeld", totalen.get("totaal_strikes_uitgedeeld", 0))
                    
                    st.divider()
                    
                    # Detail per speler
                    st.markdown("**Statistieken per speler:**")
                    
                    # Sorteer opties
                    sorteer_archief = st.selectbox(
                        "Sorteer op",
                        ["Naam", "Gefloten (hoog-laag)", "Punten (hoog-laag)", "Minimum"],
                        key="sorteer_archief"
                    )
                    
                    speler_lijst = [{"nbb": nbb, **data} for nbb, data in spelers.items()]
                    
                    if sorteer_archief == "Naam":
                        speler_lijst.sort(key=lambda x: x.get("naam", ""))
                    elif sorteer_archief == "Gefloten (hoog-laag)":
                        speler_lijst.sort(key=lambda x: x.get("gefloten_totaal", 0), reverse=True)
                    elif sorteer_archief == "Punten (hoog-laag)":
                        speler_lijst.sort(key=lambda x: x.get("punten", 0), reverse=True)
                    else:
                        speler_lijst.sort(key=lambda x: (x.get("min_wedstrijden", 0), x.get("naam", "")))
                    
                    # Tabel header
                    st.markdown("| Naam | Niv | Min | Gefloten | 1e | 2e | Punten | Strikes |")
                    st.markdown("|------|-----|-----|----------|-----|-----|--------|---------|")
                    
                    for speler in speler_lijst:
                        st.markdown(
                            f"| {speler.get('naam', '?')} | "
                            f"{speler.get('niveau', '?')} | "
                            f"{speler.get('min_wedstrijden', 0)} | "
                            f"{speler.get('gefloten_totaal', 0)} | "
                            f"{speler.get('gefloten_als_1e', 0)} | "
                            f"{speler.get('gefloten_als_2e', 0)} | "
                            f"{speler.get('punten', 0)} | "
                            f"{speler.get('strikes', 0)} |"
                        )
                    
                    # Export archief
                    st.divider()
                    if st.button(f"📥 Export {geselecteerd_seizoen} naar CSV", key="export_archief"):
                        output = "nbb_nummer,naam,niveau,min_wedstrijden,gefloten_totaal,gefloten_als_1e,gefloten_als_2e,punten,strikes\n"
                        for speler in speler_lijst:
                            output += f"{speler.get('nbb', '')},\"{speler.get('naam', '')}\","
                            output += f"{speler.get('niveau', 1)},{speler.get('min_wedstrijden', 0)},"
                            output += f"{speler.get('gefloten_totaal', 0)},{speler.get('gefloten_als_1e', 0)},"
                            output += f"{speler.get('gefloten_als_2e', 0)},{speler.get('punten', 0)},"
                            output += f"{speler.get('strikes', 0)}\n"
                        
                        st.download_button(
                            "📥 Download CSV",
                            output,
                            file_name=f"seizoen_{geselecteerd_seizoen}_archief.csv",
                            mime="text/csv",
                            key="dl_archief"
                        )
        else:
            st.info("Nog geen gearchiveerde seizoenen")
    
    with tab_reset:
        st.subheader("🗑️ Data Reset")
        st.warning("**Let op:** Deze acties zijn onomkeerbaar! Gebruik dit alleen om testdata te wissen.")
        
        # Statistieken ophalen
        reset_stats = db.get_reset_statistics()
        
        # Overzicht metrics
        st.markdown("### 📊 Overzicht")
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            bel = reset_stats.get("beloningen", {})
            st.metric("Spelers met punten/strikes", bel.get("spelers", 0), 
                     help=f"Totaal: {bel.get('punten', 0)} punten, {bel.get('strikes', 0)} strikes")
        with col_s2:
            st.metric("MSE data", 
                     reset_stats.get("uitnodigingen", 0) + reset_stats.get("feedback", 0) + reset_stats.get("wedstrijden_met_begeleider", 0),
                     help=f"{reset_stats.get('uitnodigingen', 0)} uitnodigingen, {reset_stats.get('feedback', 0)} feedback, {reset_stats.get('wedstrijden_met_begeleider', 0)} wedstrijden")
        with col_s3:
            st.metric("Apparaten", reset_stats.get("devices", 0))
        with col_s4:
            st.metric("Speler instellingen", reset_stats.get("speler_settings", 0))
        
        st.divider()
        
        # Beloningen resetten
        st.markdown("### 💰 Beloningen (Punten & Strikes)")
        
        col_bel1, col_bel2 = st.columns(2)
        
        with col_bel1:
            st.markdown("**Per speler:**")
            scheidsrechters = laad_scheidsrechters()
            beloningen = laad_beloningen()
            
            # Filter spelers met punten of strikes
            spelers_met_data = []
            for nbb, data in beloningen.get("spelers", {}).items():
                if data.get("punten", 0) > 0 or data.get("strikes", 0) > 0:
                    naam = scheidsrechters.get(nbb, {}).get("naam", nbb)
                    spelers_met_data.append({
                        "nbb": nbb, 
                        "naam": naam, 
                        "punten": data.get("punten", 0),
                        "strikes": data.get("strikes", 0)
                    })
            
            if spelers_met_data:
                speler_opties = {f"{s['naam']} ({s['punten']}p, {s['strikes']}s)": s['nbb'] for s in spelers_met_data}
                geselecteerde_speler = st.selectbox(
                    "Selecteer speler",
                    options=list(speler_opties.keys()),
                    key="reset_speler_select"
                )
                
                if st.button("🗑️ Reset deze speler", key="reset_speler_btn"):
                    nbb = speler_opties[geselecteerde_speler]
                    if db.reset_speler_beloningen(nbb):
                        st.success(f"Beloningen gereset voor {geselecteerde_speler.split(' (')[0]}")
                        st.rerun()
            else:
                st.success("✅ Geen spelers met punten of strikes")
        
        with col_bel2:
            st.markdown("**Alle spelers:**")
            bel_stats = reset_stats.get("beloningen", {})
            if bel_stats.get("spelers", 0) > 0:
                st.caption(f"Reset {bel_stats.get('spelers', 0)} spelers ({bel_stats.get('punten', 0)} punten, {bel_stats.get('strikes', 0)} strikes)")
                with st.expander("⚠️ Reset alle beloningen"):
                    st.error("Dit wist ALLE punten, strikes en logs!")
                    bevestig_bel = st.text_input("Type 'RESET' ter bevestiging", key="bevestig_alle_bel")
                    if st.button("🗑️ Reset ALLE beloningen", type="primary", key="reset_alle_bel_btn"):
                        if bevestig_bel == "RESET":
                            success, aantal = db.reset_alle_beloningen()
                            if success:
                                st.success(f"Beloningen gereset voor {aantal} spelers")
                                st.rerun()
                        else:
                            st.warning("Type 'RESET' om te bevestigen")
            else:
                st.success("✅ Geen beloningen om te resetten")
        
        st.divider()
        
        # MSE Begeleiding resetten
        st.markdown("### 👥 MSE Begeleiding")
        
        col_mse1, col_mse2, col_mse3 = st.columns(3)
        
        with col_mse1:
            uitn_count = reset_stats.get("uitnodigingen", 0)
            st.markdown(f"**Uitnodigingen:** {uitn_count}")
            if uitn_count > 0:
                if st.button("🗑️ Reset uitnodigingen", key="reset_uitnodigingen_btn"):
                    success, aantal = db.reset_alle_begeleidingsuitnodigingen()
                    if success:
                        st.success(f"{aantal} verwijderd")
                        st.rerun()
            else:
                st.success("✅ Geen data")
        
        with col_mse2:
            fb_count = reset_stats.get("feedback", 0)
            st.markdown(f"**Feedback:** {fb_count}")
            if fb_count > 0:
                if st.button("🗑️ Reset feedback", key="reset_feedback_btn"):
                    success, aantal = db.reset_alle_begeleiding_feedback()
                    if success:
                        st.success(f"{aantal} verwijderd")
                        st.rerun()
            else:
                st.success("✅ Geen data")
        
        with col_mse3:
            beg_count = reset_stats.get("wedstrijden_met_begeleider", 0)
            st.markdown(f"**Begeleiders in wedstrijden:** {beg_count}")
            if beg_count > 0:
                if st.button("🗑️ Reset begeleiders", key="reset_begeleiders_btn"):
                    success, aantal = db.reset_begeleiders_uit_wedstrijden()
                    if success:
                        st.success(f"{aantal} wedstrijden bijgewerkt")
                        st.rerun()
            else:
                st.success("✅ Geen data")
        
        st.divider()
        
        # Apparaten resetten
        st.markdown("### 📱 Apparaten")
        
        col_app1, col_app2 = st.columns(2)
        
        with col_app1:
            dev_count = reset_stats.get("devices", 0)
            st.markdown(f"**Device tokens:** {dev_count}")
            if dev_count > 0:
                with st.expander("⚠️ Reset alle apparaten"):
                    st.caption("Iedereen moet opnieuw verifiëren")
                    if st.button("🗑️ Reset apparaten", key="reset_devices_btn"):
                        success, aantal = db.reset_alle_device_tokens()
                        if success:
                            st.success(f"{aantal} apparaten verwijderd")
                            st.rerun()
            else:
                st.success("✅ Geen apparaten")
        
        with col_app2:
            set_count = reset_stats.get("speler_settings", 0)
            st.markdown(f"**Speler instellingen:** {set_count}")
            if set_count > 0:
                with st.expander("⚠️ Reset apparaat instellingen"):
                    st.caption("Reset max apparaten en goedkeurings-instellingen")
                    if st.button("🗑️ Reset instellingen", key="reset_speler_settings_btn"):
                        success, aantal = db.reset_speler_settings()
                        if success:
                            st.success(f"{aantal} instellingen gereset")
                            st.rerun()
            else:
                st.success("✅ Geen instellingen")
    
    with tab_versie:
        st.subheader("ℹ️ Over Ref Planner")
        st.write(f"**Versie:** {APP_VERSIE}")
        st.write(f"**Datum:** {APP_VERSIE_DATUM}")
        
        with st.expander("📋 Changelog"):
            st.markdown(APP_CHANGELOG)

def bepaal_niveau_uit_team(teamnaam: str) -> int:
    """Bepaal niveau 1-5 uit de teamnaam van Waterdragers."""
    # Haal het team-deel uit de naam (bijv. "Waterdragers - X10-1" -> "X10-1")
    if " - " in teamnaam:
        team = teamnaam.split(" - ")[-1].strip().upper()
    else:
        team = teamnaam.strip().upper()
    
    # Verwijder eventuele asterisk (bijv. "M18-2*")
    team = team.rstrip("*")
    
    # Niveau-indeling op basis van teamnaam
    # Niveau 1: X10-1, X10-2, X12-2, V12-2
    # Niveau 2: X12-1, V12-1, X14-2, M16-2
    # Niveau 3: X14-1, M16-1, V16-2
    # Niveau 4: V16-1, M18-2, M18-3
    # Niveau 5: M18-1, M20-1, MSE-1
    
    niveau_1 = ["X10-1", "X10-2", "X12-2", "V12-2"]
    niveau_2 = ["X12-1", "V12-1", "X14-2", "M16-2"]
    niveau_3 = ["X14-1", "M16-1", "V16-2"]
    niveau_4 = ["V16-1", "M18-2", "M18-3"]
    niveau_5 = ["M18-1", "M20-1", "MSE-1"]
    
    if team in niveau_1:
        return 1
    elif team in niveau_2:
        return 2
    elif team in niveau_3:
        return 3
    elif team in niveau_4:
        return 4
    elif team in niveau_5:
        return 5
    
    # Fallback op basis van leeftijdscategorie als team niet exact matcht
    if "X10" in team:
        return 1
    elif "X12" in team or "V12" in team:
        # X12-1 en V12-1 zijn niveau 2, rest niveau 1
        if "-1" in team:
            return 2
        return 1
    elif "X14" in team:
        # X14-1 is niveau 3, X14-2 is niveau 2
        if "-1" in team:
            return 3
        return 2
    elif "M16" in team:
        # M16-1 is niveau 3, M16-2 is niveau 2
        if "-1" in team:
            return 3
        return 2
    elif "V16" in team:
        # V16-1 is niveau 4, V16-2 is niveau 3
        if "-1" in team:
            return 4
        return 3
    elif "M18" in team:
        # M18-1 is niveau 5, M18-2 en M18-3 zijn niveau 4
        if "-1" in team:
            return 5
        return 4
    elif "M20" in team or "M22" in team:
        return 5
    elif "MSE" in team:
        return 5
    
    return 2  # Default


def bepaal_niveau_uit_competitie(competitie: str) -> int:
    """Fallback: bepaal niveau uit de NBB competitie string."""
    competitie = competitie.upper()
    
    if "U10" in competitie or "U12" in competitie:
        return 1
    elif "U14" in competitie:
        return 2
    elif "U16" in competitie:
        if "3E DIVISIE" in competitie or "2E DIVISIE" in competitie:
            return 3
        return 2
    elif "U18" in competitie or "U20" in competitie or "U22" in competitie:
        return 3
    elif "SENIOREN" in competitie or "MSE" in competitie:
        if "1E DIVISIE" in competitie or "2E DIVISIE" in competitie or "3E DIVISIE" in competitie:
            return 5
        return 4
    
    return 2  # Default


def toon_synchronisatie_tab():
    """Synchronisatie tab: synchroniseer wedstrijden met Competitie Planner en NBB data."""
    
    # ==========================================================================
    # SECTIE 1: SYNCHRONISATIE MET COMPETITIE PLANNER
    # ==========================================================================
    import cp_sync
    
    st.write("**🔄 Synchronisatie met Competitie Planner**")
    
    # Check connectie
    if not cp_sync.is_cp_connected():
        st.warning("⚠️ Geen verbinding met Competitie Planner database. Controleer de credentials in Streamlit secrets.")
    else:
        st.success("✅ Verbonden met Competitie Planner")
        
        # Seizoen selectie
        seizoenen = cp_sync.get_beschikbare_seizoenen()
        
        if not seizoenen:
            st.info("Geen seizoenen gevonden in Competitie Planner.")
        else:
            col_cp1, col_cp2 = st.columns(2)
            
            with col_cp1:
                geselecteerd_seizoen = st.selectbox(
                    "Seizoen",
                    seizoenen,
                    key="cp_sync_seizoen"
                )
            
            with col_cp2:
                seizoenshelften = cp_sync.get_beschikbare_seizoenshelften(geselecteerd_seizoen)
                seizoenshelft_opties = ["Alle"] + seizoenshelften
                geselecteerde_helft = st.selectbox(
                    "Seizoenshelft",
                    seizoenshelft_opties,
                    key="cp_sync_helft"
                )
            
            # Vergelijk knop
            if st.button("🔍 Vergelijk met Competitie Planner", key="cp_vergelijk_btn"):
                helft_filter = None if geselecteerde_helft == "Alle" else geselecteerde_helft
                
                with st.spinner("Wedstrijden ophalen uit Competitie Planner..."):
                    cp_wedstrijden = cp_sync.get_wedstrijden_van_cp(geselecteerd_seizoen, helft_filter)
                
                if not cp_wedstrijden:
                    st.warning("Geen wedstrijden gevonden in Competitie Planner voor deze selectie.")
                else:
                    st.info(f"📊 {len(cp_wedstrijden)} wedstrijden gevonden in Competitie Planner")
                    
                    # Debug: toon eerste paar wedstrijden uit CP
                    with st.expander("🔧 Debug info (CP data)", expanded=False):
                        for i, cp_wed in enumerate(cp_wedstrijden[:5]):
                            home = cp_wed.get('home_team_name', '')
                            away = cp_wed.get('away_team_name', '')
                            is_thuis = home.lower().startswith('waterdragers')
                            type_icon = "🏠" if is_thuis else "🚗"
                            
                            # Toon hoe de match key eruit ziet
                            bob_fmt = cp_sync.map_cp_naar_bob(cp_wed)
                            datum_key = bob_fmt.get('datum', '')[:16] if bob_fmt.get('datum') else ''
                            # Genormaliseerde key (zonder sterretjes)
                            thuis_norm = bob_fmt.get('thuisteam', '').lower().replace('*', '')
                            uit_norm = bob_fmt.get('uitteam', '').lower().replace('*', '')
                            
                            st.write(f"**CP #{i+1} {type_icon}:** {home} vs {away}")
                            st.write(f"  Datum: {cp_wed.get('scheduled_date')} {cp_wed.get('scheduled_time')}")
                            st.write(f"  → BOB formaat: {bob_fmt.get('thuisteam')} vs {bob_fmt.get('uitteam')}")
                            st.code(f"Key: {datum_key}|{thuis_norm}|{uit_norm}")
                    
                    # Laad BOB wedstrijden (thuis én uit)
                    bob_wedstrijden_dict = laad_wedstrijden()
                    bob_wedstrijden_list = [
                        {**wed, 'wed_id': wed_id} 
                        for wed_id, wed in bob_wedstrijden_dict.items()
                    ]
                    
                    # Debug: toon eerste paar wedstrijden uit BOB
                    with st.expander("🔧 Debug info (BOB data)", expanded=False):
                        for i, bob_wed in enumerate(bob_wedstrijden_list[:5]):
                            type_icon = "🏠" if bob_wed.get('type', 'thuis') == 'thuis' else "🚗"
                            datum_key = bob_wed.get('datum', '').replace('T', ' ')[:16] if bob_wed.get('datum') else ''
                            # Genormaliseerde key (zonder sterretjes)
                            thuis_norm = bob_wed.get('thuisteam', '').lower().replace('*', '')
                            uit_norm = bob_wed.get('uitteam', '').lower().replace('*', '')
                            
                            st.write(f"**BOB #{i+1} {type_icon}:** {bob_wed.get('thuisteam')} vs {bob_wed.get('uitteam')}")
                            st.write(f"  Datum: {bob_wed.get('datum')}")
                            st.write(f"  NBB nr: {bob_wed.get('nbb_wedstrijd_nr')}")
                            st.code(f"Key: {datum_key}|{thuis_norm}|{uit_norm}")
                    
                    # Debug: zoek specifieke match voor eerste CP wedstrijd
                    with st.expander("🔍 Debug: Match analyse eerste CP wedstrijd", expanded=False):
                        if cp_wedstrijden:
                            first_cp = cp_wedstrijden[0]
                            first_bob_fmt = cp_sync.map_cp_naar_bob(first_cp)
                            
                            st.write("**Zoeken naar match voor:**")
                            st.write(f"  Thuisteam: `{first_bob_fmt.get('thuisteam')}`")
                            st.write(f"  Uitteam: `{first_bob_fmt.get('uitteam')}`")
                            st.write(f"  Datum: `{first_bob_fmt.get('datum')}`")
                            
                            # Zoek in BOB naar wedstrijden met hetzelfde Waterdragers team
                            eigen_team = first_bob_fmt.get('thuisteam', '').lower()
                            st.write(f"\n**BOB wedstrijden met vergelijkbaar eigen team:**")
                            
                            found_any = False
                            for bob_wed in bob_wedstrijden_list:
                                bob_thuis = bob_wed.get('thuisteam', '').lower()
                                if eigen_team[:15] in bob_thuis or bob_thuis[:15] in eigen_team:
                                    found_any = True
                                    bob_datum = bob_wed.get('datum', '').replace('T', ' ')[:16]
                                    cp_datum = first_bob_fmt.get('datum', '')[:16]
                                    datum_match = "✅" if bob_datum == cp_datum else "❌"
                                    
                                    st.write(f"  {datum_match} BOB: {bob_wed.get('thuisteam')} vs {bob_wed.get('uitteam')}")
                                    st.write(f"      Datum BOB: `{bob_datum}` | Datum CP: `{cp_datum}`")
                                    st.write(f"      Uitteam BOB: `{bob_wed.get('uitteam', '').lower()}`")
                                    st.write(f"      Uitteam CP:  `{first_bob_fmt.get('uitteam', '').lower()}`")
                            
                            if not found_any:
                                st.warning(f"Geen BOB wedstrijden gevonden met team '{eigen_team[:20]}...'")
                    
                    # Vergelijk
                    resultaat = cp_sync.vergelijk_wedstrijden(cp_wedstrijden, bob_wedstrijden_list)
                    
                    # Opslaan in session state voor verwerking
                    st.session_state['cp_sync_resultaat'] = resultaat
                    st.session_state['cp_sync_uitgevoerd'] = True
            
            # Toon resultaten als vergelijking is uitgevoerd
            if st.session_state.get('cp_sync_uitgevoerd') and 'cp_sync_resultaat' in st.session_state:
                resultaat = st.session_state['cp_sync_resultaat']
                
                # Samenvatting
                st.divider()
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("✅ Ongewijzigd", len(resultaat['ongewijzigd']))
                col_s2.metric("➕ Nieuw", len(resultaat['nieuw']))
                col_s3.metric("✏️ Gewijzigd", len(resultaat['gewijzigd']))
                col_s4.metric("❌ Niet in CP", len(resultaat['verwijderd']))
                
                # NIEUWE WEDSTRIJDEN
                if resultaat['nieuw']:
                    st.subheader(f"➕ Nieuwe wedstrijden ({len(resultaat['nieuw'])})")
                    st.write("Deze wedstrijden staan in CP maar nog niet in BOB.")
                    
                    # Selectie voor toevoegen
                    if 'cp_nieuw_selectie' not in st.session_state:
                        st.session_state['cp_nieuw_selectie'] = [True] * len(resultaat['nieuw'])
                    
                    for i, item in enumerate(resultaat['nieuw']):
                        bob_fmt = item['bob_format']
                        datum_str = bob_fmt.get('datum', '')[:16] if bob_fmt.get('datum') else 'Onbekend'
                        # Gebruik eigen_team_code voor weergave
                        eigen_team = bob_fmt.get('eigen_team_code', '?')
                        wed_type = "🏠" if bob_fmt.get('type') == 'thuis' else "🚗"
                        tegenstander = bob_fmt.get('uitteam') if bob_fmt.get('type') == 'thuis' else bob_fmt.get('thuisteam')
                        
                        col_check, col_info = st.columns([1, 11])
                        with col_check:
                            st.session_state['cp_nieuw_selectie'][i] = st.checkbox(
                                "Toevoegen",
                                value=st.session_state['cp_nieuw_selectie'][i],
                                key=f"cp_nieuw_{i}",
                                label_visibility="collapsed"
                            )
                        with col_info:
                            st.write(f"{wed_type} **{datum_str}** | {eigen_team} vs {tegenstander} | Niveau {bob_fmt.get('niveau', '?')} | Veld {bob_fmt.get('veld', '-')}")
                    
                    # Toevoegen knop
                    geselecteerd_nieuw = sum(st.session_state['cp_nieuw_selectie'])
                    if geselecteerd_nieuw > 0:
                        if st.button(f"➕ Voeg {geselecteerd_nieuw} wedstrijden toe aan BOB", key="cp_add_btn"):
                            toegevoegd = 0
                            for i, item in enumerate(resultaat['nieuw']):
                                if st.session_state['cp_nieuw_selectie'][i]:
                                    bob_fmt = item['bob_format']
                                    # Genereer wed_id
                                    nbb_nr = bob_fmt.get('nbb_wedstrijd_nr', '')
                                    wed_id = f"cp_{nbb_nr}" if nbb_nr else f"cp_{datetime.now().timestamp()}"
                                    
                                    # Verwijder interne velden
                                    wed_data = {k: v for k, v in bob_fmt.items() if not k.startswith('_')}
                                    wed_data['type'] = 'thuis'
                                    
                                    # Opslaan
                                    try:
                                        sla_wedstrijd_op(wed_id, wed_data)
                                        toegevoegd += 1
                                    except Exception as e:
                                        st.error(f"Fout bij toevoegen: {e}")
                            
                            if toegevoegd > 0:
                                st.success(f"✅ {toegevoegd} wedstrijden toegevoegd!")
                                # Reset state
                                del st.session_state['cp_sync_resultaat']
                                del st.session_state['cp_sync_uitgevoerd']
                                st.rerun()
                
                # GEWIJZIGDE WEDSTRIJDEN
                if resultaat['gewijzigd']:
                    st.subheader(f"✏️ Gewijzigde wedstrijden ({len(resultaat['gewijzigd'])})")
                    st.write("Deze wedstrijden hebben verschillen tussen CP en BOB.")
                    
                    if 'cp_wijzig_selectie' not in st.session_state:
                        st.session_state['cp_wijzig_selectie'] = [False] * len(resultaat['gewijzigd'])
                    
                    for i, item in enumerate(resultaat['gewijzigd']):
                        bob = item['bob']
                        bob_fmt = item['bob_format']
                        wijzigingen = item['wijzigingen']
                        
                        with st.expander(f"📅 {bob.get('thuisteam', '?')} vs {bob.get('uitteam', '?')}", expanded=False):
                            # Toon wijzigingen
                            for wijz in wijzigingen:
                                st.write(f"**{wijz['label']}:** {wijz['bob_waarde']} → {wijz['cp_waarde']}")
                            
                            # Scheidsrechters info
                            scheids_info = []
                            if bob.get('scheids_1'):
                                scheids_info.append(f"1e: {bob['scheids_1']}")
                            if bob.get('scheids_2'):
                                scheids_info.append(f"2e: {bob['scheids_2']}")
                            if scheids_info:
                                st.info(f"👥 Huidige scheidsrechters: {', '.join(scheids_info)}")
                            
                            st.session_state['cp_wijzig_selectie'][i] = st.checkbox(
                                "CP waarden overnemen (scheidsrechters blijven behouden)",
                                value=st.session_state['cp_wijzig_selectie'][i],
                                key=f"cp_wijzig_{i}"
                            )
                    
                    # Bijwerken knop
                    geselecteerd_wijzig = sum(st.session_state['cp_wijzig_selectie'])
                    if geselecteerd_wijzig > 0:
                        if st.button(f"✏️ Werk {geselecteerd_wijzig} wedstrijden bij", key="cp_update_btn"):
                            bijgewerkt = 0
                            for i, item in enumerate(resultaat['gewijzigd']):
                                if st.session_state['cp_wijzig_selectie'][i]:
                                    bob = item['bob']
                                    bob_fmt = item['bob_format']
                                    wed_id = bob.get('wed_id')
                                    
                                    if wed_id:
                                        # Update alleen de gewijzigde velden
                                        update_data = {}
                                        for wijz in item['wijzigingen']:
                                            veld = wijz['veld']
                                            update_data[veld] = bob_fmt.get(veld)
                                        
                                        # Voeg nbb_wedstrijd_nr toe als die nog niet gezet is
                                        if bob_fmt.get('nbb_wedstrijd_nr') and not bob.get('nbb_wedstrijd_nr'):
                                            update_data['nbb_wedstrijd_nr'] = bob_fmt['nbb_wedstrijd_nr']
                                        
                                        try:
                                            sla_wedstrijd_op(wed_id, update_data)
                                            bijgewerkt += 1
                                        except Exception as e:
                                            st.error(f"Fout bij bijwerken: {e}")
                            
                            if bijgewerkt > 0:
                                st.success(f"✅ {bijgewerkt} wedstrijden bijgewerkt!")
                                del st.session_state['cp_sync_resultaat']
                                del st.session_state['cp_sync_uitgevoerd']
                                st.rerun()
                
                # VERWIJDERDE WEDSTRIJDEN (in BOB maar niet in CP)
                if resultaat['verwijderd']:
                    st.subheader(f"❌ Niet meer in CP ({len(resultaat['verwijderd'])})")
                    st.write("Deze wedstrijden staan in BOB maar niet (meer) in CP. Mogelijk geannuleerd of verplaatst.")
                    
                    for item in resultaat['verwijderd']:
                        bob = item['bob']
                        st.write(f"• 📅 {bob.get('datum', '?')[:16]} | {bob.get('thuisteam', '?')} vs {bob.get('uitteam', '?')}")
                    
                    st.info("💡 Deze wedstrijden worden niet automatisch verwijderd. Controleer handmatig of ze geannuleerd moeten worden.")
    
    st.divider()
    
    # ==========================================================================
    # SECTIE 2: SYNCHRONISATIE MET NBB (bestaande functionaliteit)
    # ==========================================================================
    st.write("**🔄 Synchronisatie met NBB**")
    st.write("Upload een NBB export om bestaande wedstrijden te completeren of verschillen te detecteren.")
    
    # Instellingen
    col1, col2 = st.columns(2)
    with col1:
        thuislocatie = st.text_input("Thuislocatie (plaatsnaam)", value="NIEUWERKERK", 
                                      key="sync_thuisloc",
                                      help="Wedstrijden op deze locatie worden als thuiswedstrijd gemarkeerd")
    with col2:
        club_naam = st.text_input("Clubnaam in teamnamen", value="Waterdragers", key="sync_club")
    
    uploaded_sync = st.file_uploader("Upload NBB Excel", type=["xlsx", "xls"], key="sync_nbb")
    
    if not uploaded_sync:
        st.info("📤 Upload een NBB Excel bestand om te beginnen met synchroniseren.")
        return
    
    try:
        import pandas as pd
        df = pd.read_excel(uploaded_sync)
        
        # Check of dit een NBB bestand is
        required_cols = ["Datum", "Tijd", "Thuisteam", "Uitteam", "Plaatsnaam"]
        missing = [c for c in required_cols if c not in df.columns]
        
        if missing:
            st.error(f"Ontbrekende kolommen: {missing}")
            return
        
        # Filter op club en thuiswedstrijden
        df_club = df[
            (df["Thuisteam"].str.contains(club_naam, case=False, na=False) |
             df["Uitteam"].str.contains(club_naam, case=False, na=False))
        ]
        
        # Filter alleen thuiswedstrijden
        df_thuis = df_club[
            df_club["Plaatsnaam"].str.upper().str.contains(thuislocatie.upper(), na=False)
        ].copy()
        
        if len(df_thuis) == 0:
            st.warning(f"Geen thuiswedstrijden gevonden voor '{club_naam}' op locatie '{thuislocatie}'")
            return
        
        # Filter alleen TOEKOMSTIGE wedstrijden (vandaag of later)
        vandaag = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        df_thuis["datum_parsed"] = pd.to_datetime(df_thuis["Datum"])
        df_thuis = df_thuis[df_thuis["datum_parsed"] >= vandaag].copy()
        
        if len(df_thuis) == 0:
            st.warning(f"Geen toekomstige thuiswedstrijden gevonden. Alleen wedstrijden vanaf vandaag worden gesynchroniseerd.")
            return
        
        st.success(f"📊 {len(df_thuis)} toekomstige thuiswedstrijden gevonden in NBB bestand")
        
        # Laad bestaande wedstrijden en scheidsrechters
        wedstrijden = laad_wedstrijden()
        scheidsrechters = laad_scheidsrechters()
        
        # Maak lookup van bestaande wedstrijden op basis van datum/tijd/teams
        def maak_match_key(datum_str, thuisteam, uitteam):
            """Maak een unieke sleutel voor matching."""
            # Normaliseer teamnamen (verwijder extra spaties, lowercase)
            thuis_norm = str(thuisteam).strip().lower()
            uit_norm = str(uitteam).strip().lower()
            return f"{datum_str}|{thuis_norm}|{uit_norm}"
        
        bestaande_lookup = {}
        for wed_id, wed in wedstrijden.items():
            if wed.get("type", "thuis") != "thuis":
                continue
            key = maak_match_key(wed["datum"], wed["thuisteam"], wed["uitteam"])
            bestaande_lookup[key] = wed_id
        
        # Analyseer NBB data en match met bestaande wedstrijden
        matches = []
        nieuwe_wedstrijden = []
        
        # Extra lookup voor verplaatsingen: match alleen op teams (zonder datum)
        def maak_team_key(thuisteam, uitteam):
            """Maak een sleutel gebaseerd op alleen de teams."""
            thuis_norm = str(thuisteam).strip().lower()
            uit_norm = str(uitteam).strip().lower()
            return f"{thuis_norm}|{uit_norm}"
        
        team_lookup = {}  # team_key -> [(wed_id, wed_data), ...]
        for wed_id, wed in wedstrijden.items():
            if wed.get("type", "thuis") != "thuis":
                continue
            team_key = maak_team_key(wed["thuisteam"], wed["uitteam"])
            if team_key not in team_lookup:
                team_lookup[team_key] = []
            team_lookup[team_key].append((wed_id, wed))
        
        verplaatsingen = []  # Wedstrijden die verplaatst kunnen worden
        
        for idx, row in df_thuis.iterrows():
            datum = pd.to_datetime(row["Datum"]).strftime("%Y-%m-%d")
            tijd = str(row["Tijd"])[:5] if pd.notna(row["Tijd"]) else "00:00"
            datum_tijd = f"{datum} {tijd}"
            
            thuisteam = str(row["Thuisteam"]).strip()
            uitteam = str(row["Uitteam"]).strip()
            
            # Veld uit NBB
            veld_raw = row.get("Veld", "")
            veld_nbb = ""
            if pd.notna(veld_raw) and veld_raw != "" and str(veld_raw) != "nan":
                veld_nbb = str(veld_raw).strip().lower().replace("veld ", "").replace("veld", "").strip()
            
            # Bepaal niveau
            eigen_team = thuisteam if club_naam.lower() in thuisteam.lower() else uitteam
            niveau_nbb = bepaal_niveau_uit_team(eigen_team)
            
            # BS2 vereiste
            vereist_bs2_nbb = "MSE" in eigen_team.upper()
            
            # Match met bestaande wedstrijd op datum/tijd/teams
            key = maak_match_key(datum_tijd, thuisteam, uitteam)
            
            nbb_data = {
                "datum": datum_tijd,
                "thuisteam": thuisteam,
                "uitteam": uitteam,
                "niveau": niveau_nbb,
                "veld": veld_nbb,
                "vereist_bs2": vereist_bs2_nbb
            }
            
            if key in bestaande_lookup:
                # Exacte match op datum/tijd/teams
                wed_id = bestaande_lookup[key]
                bob_data = wedstrijden[wed_id]
                matches.append({
                    "wed_id": wed_id,
                    "nbb": nbb_data,
                    "bob": bob_data,
                    "key": key
                })
            else:
                # Geen exacte match - check of teams matchen (mogelijke verplaatsing)
                team_key = maak_team_key(thuisteam, uitteam)
                if team_key in team_lookup:
                    # Teams gevonden - check of datum anders is
                    for wed_id, bob_data in team_lookup[team_key]:
                        bob_datum = bob_data["datum"]
                        if bob_datum != datum_tijd:
                            # Datum verschilt - dit is een mogelijke verplaatsing
                            verplaatsingen.append({
                                "wed_id": wed_id,
                                "nbb": nbb_data,
                                "bob": bob_data,
                                "team_key": team_key,
                                "is_geannuleerd": bob_data.get("geannuleerd", False)
                            })
                            break  # Eén match per NBB wedstrijd
                    else:
                        # Geen verplaatsing gevonden, nieuwe wedstrijd
                        nieuwe_wedstrijden.append(nbb_data)
                else:
                    nieuwe_wedstrijden.append(nbb_data)
        
        st.divider()
        
        # FASE 0: Verplaatsingen
        if verplaatsingen:
            st.subheader("🔄 Fase 0: Verplaatsingen")
            st.write("Deze wedstrijden staan in NBB met een **andere datum** dan in BOB.")
            
            if "verplaats_selectie" not in st.session_state:
                st.session_state["verplaats_selectie"] = {}
            
            for i, verplaats in enumerate(verplaatsingen):
                bob = verplaats["bob"]
                nbb = verplaats["nbb"]
                wed_id = verplaats["wed_id"]
                is_geannuleerd = verplaats["is_geannuleerd"]
                
                status_icon = "❌" if is_geannuleerd else "📅"
                status_tekst = " (GEANNULEERD in BOB)" if is_geannuleerd else ""
                
                with st.expander(f"{status_icon} {nbb['thuisteam']} vs {nbb['uitteam']}{status_tekst}", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write("**BOB (huidig):**")
                        st.write(f"📅 {bob['datum']}")
                        if is_geannuleerd:
                            st.write("❌ **GEANNULEERD**")
                        if bob.get("scheids_1") or bob.get("scheids_2"):
                            s1 = scheidsrechters.get(bob.get("scheids_1"), {}).get("naam", "-")
                            s2 = scheidsrechters.get(bob.get("scheids_2"), {}).get("naam", "-")
                            st.write(f"👥 {s1} / {s2}")
                        else:
                            st.write("👥 Geen scheidsrechters")
                    
                    with col2:
                        st.write("**NBB (nieuw):**")
                        st.write(f"📅 {nbb['datum']}")
                        if nbb.get("veld"):
                            st.write(f"📍 Veld {nbb['veld']}")
                    
                    with col3:
                        st.write("**Actie:**")
                        actie = st.radio(
                            "Kies actie",
                            options=["verplaats", "nieuw", "negeer"],
                            format_func=lambda x: {
                                "verplaats": "🔄 Verplaats naar nieuwe datum",
                                "nieuw": "➕ Maak nieuwe wedstrijd",
                                "negeer": "⏭️ Negeer"
                            }[x],
                            key=f"verplaats_actie_{wed_id}",
                            index=0,  # Default: verplaats
                            label_visibility="collapsed"
                        )
                        if is_geannuleerd and actie == "verplaats":
                            st.caption("✅ Annulering wordt opgeheven")
                        st.session_state["verplaats_selectie"][wed_id] = {
                            "actie": actie,
                            "nbb": nbb,
                            "bob": bob,
                            "is_geannuleerd": is_geannuleerd
                        }
            
            # Verwerk verplaatsingen
            col_apply, col_info = st.columns([1, 2])
            with col_apply:
                if st.button("✅ Voer verplaatsingen uit", key="btn_verplaats", type="primary"):
                    aantal_verplaatst = 0
                    aantal_nieuw = 0
                    aantal_heractiveerd = 0
                    
                    for wed_id, selectie in st.session_state["verplaats_selectie"].items():
                        actie = selectie["actie"]
                        nbb = selectie["nbb"]
                        was_geannuleerd = selectie.get("is_geannuleerd", False)
                        
                        if actie == "verplaats":
                            # Update bestaande wedstrijd met nieuwe datum
                            wedstrijden[wed_id]["datum"] = nbb["datum"]
                            wedstrijden[wed_id]["geannuleerd"] = False  # Heractiveer indien nodig
                            wedstrijden[wed_id]["geannuleerd_op"] = None
                            if nbb.get("veld"):
                                wedstrijden[wed_id]["veld"] = nbb["veld"]
                            if nbb.get("niveau"):
                                wedstrijden[wed_id]["niveau"] = nbb["niveau"]
                            aantal_verplaatst += 1
                            if was_geannuleerd:
                                aantal_heractiveerd += 1
                            
                        elif actie == "nieuw":
                            # Maak nieuwe wedstrijd
                            nieuw_id = f"wed_{datetime.now().strftime('%Y%m%d%H%M%S')}_{aantal_nieuw}"
                            wedstrijden[nieuw_id] = {
                                "datum": nbb["datum"],
                                "thuisteam": nbb["thuisteam"],
                                "uitteam": nbb["uitteam"],
                                "niveau": nbb["niveau"],
                                "veld": nbb.get("veld", ""),
                                "vereist_bs2": nbb.get("vereist_bs2", False),
                                "type": "thuis",
                                "scheids_1": None,
                                "scheids_2": None
                            }
                            aantal_nieuw += 1
                    
                    sla_wedstrijden_op(wedstrijden)
                    st.session_state["verplaats_selectie"] = {}
                    
                    msg_parts = []
                    if aantal_verplaatst > 0:
                        msg_parts.append(f"{aantal_verplaatst} verplaatst")
                    if aantal_heractiveerd > 0:
                        msg_parts.append(f"{aantal_heractiveerd} heractiveerd")
                    if aantal_nieuw > 0:
                        msg_parts.append(f"{aantal_nieuw} nieuw aangemaakt")
                    
                    st.success(f"✅ {', '.join(msg_parts)}!")
                    st.rerun()
            
            with col_info:
                st.caption("💡 Bij 'Verplaats' worden scheidsrechters behouden. Bij 'Nieuw' moet je opnieuw toewijzen.")
            
            st.divider()
        
        # FASE 1: Completeren
        st.subheader("📥 Fase 1: Completeren")
        st.write("Vul ontbrekende velden in BOB aan met data uit NBB.")
        
        te_completeren = []
        for match in matches:
            bob = match["bob"]
            nbb = match["nbb"]
            
            ontbrekend = []
            if not bob.get("veld") and nbb.get("veld"):
                ontbrekend.append(("veld", nbb["veld"]))
            
            if ontbrekend:
                te_completeren.append({
                    "wed_id": match["wed_id"],
                    "datum": bob["datum"],
                    "thuisteam": bob["thuisteam"],
                    "uitteam": bob["uitteam"],
                    "ontbrekend": ontbrekend
                })
        
        if te_completeren:
            st.write(f"**{len(te_completeren)} wedstrijden** kunnen worden aangevuld:")
            
            # Preview tabel
            preview_data = []
            for item in te_completeren:
                velden = ", ".join([f"{v[0]}={v[1]}" for v in item["ontbrekend"]])
                preview_data.append({
                    "Datum": item["datum"],
                    "Thuisteam": item["thuisteam"],
                    "Uitteam": item["uitteam"],
                    "Aan te vullen": velden
                })
            
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)
            
            if st.button("✅ Completeer alle wedstrijden", key="btn_completeer"):
                count = 0
                for item in te_completeren:
                    wed_id = item["wed_id"]
                    for veld_naam, veld_waarde in item["ontbrekend"]:
                        wedstrijden[wed_id][veld_naam] = veld_waarde
                    count += 1
                
                sla_wedstrijden_op(wedstrijden)
                st.success(f"✅ {count} wedstrijden aangevuld!")
                st.rerun()
        else:
            st.success("✅ Alle wedstrijden zijn compleet - geen ontbrekende velden.")
        
        st.divider()
        
        # FASE 2: Vergelijken
        st.subheader("⚖️ Fase 2: Vergelijken")
        st.write("Detecteer en los verschillen op tussen BOB en NBB.")
        
        # Vergelijk velden die kunnen afwijken
        vergelijk_velden = ["veld", "niveau"]
        mismatches = []
        
        for match in matches:
            bob = match["bob"]
            nbb = match["nbb"]
            
            verschillen = []
            for veld in vergelijk_velden:
                bob_val = bob.get(veld, "")
                nbb_val = nbb.get(veld, "")
                
                # Normaliseer voor vergelijking
                bob_val_norm = str(bob_val).strip().lower() if bob_val else ""
                nbb_val_norm = str(nbb_val).strip().lower() if nbb_val else ""
                
                # Alleen verschil als beide een waarde hebben én ze verschillen
                if bob_val_norm and nbb_val_norm and bob_val_norm != nbb_val_norm:
                    verschillen.append({
                        "veld": veld,
                        "bob": bob_val,
                        "nbb": nbb_val
                    })
            
            if verschillen:
                mismatches.append({
                    "wed_id": match["wed_id"],
                    "datum": bob["datum"],
                    "thuisteam": bob["thuisteam"],
                    "uitteam": bob["uitteam"],
                    "verschillen": verschillen
                })
        
        if mismatches:
            st.warning(f"⚠️ **{len(mismatches)} wedstrijden** hebben afwijkingen:")
            
            # Session state voor keuzes
            if "sync_keuzes" not in st.session_state:
                st.session_state["sync_keuzes"] = {}
            
            for i, mismatch in enumerate(mismatches):
                with st.expander(f"📅 {mismatch['datum']} - {mismatch['thuisteam']} vs {mismatch['uitteam']}"):
                    for verschil in mismatch["verschillen"]:
                        veld = verschil["veld"]
                        bob_val = verschil["bob"]
                        nbb_val = verschil["nbb"]
                        
                        col1, col2, col3 = st.columns([2, 2, 2])
                        
                        with col1:
                            st.write(f"**{veld.capitalize()}**")
                        
                        with col2:
                            keuze_key = f"{mismatch['wed_id']}_{veld}"
                            
                            # Default naar huidige BOB waarde
                            if keuze_key not in st.session_state["sync_keuzes"]:
                                st.session_state["sync_keuzes"][keuze_key] = "bob"
                            
                            keuze = st.radio(
                                f"Keuze voor {veld}",
                                options=["bob", "nbb"],
                                format_func=lambda x: f"BOB: {bob_val}" if x == "bob" else f"NBB: {nbb_val}",
                                key=f"radio_{keuze_key}",
                                index=0 if st.session_state["sync_keuzes"].get(keuze_key) == "bob" else 1,
                                horizontal=True,
                                label_visibility="collapsed"
                            )
                            st.session_state["sync_keuzes"][keuze_key] = keuze
                        
                        with col3:
                            if keuze == "nbb":
                                st.write(f"→ wordt: **{nbb_val}**")
                            else:
                                st.write(f"→ blijft: **{bob_val}**")
            
            # Toon samenvatting van wijzigingen
            wijzigingen = []
            for mismatch in mismatches:
                for verschil in mismatch["verschillen"]:
                    keuze_key = f"{mismatch['wed_id']}_{verschil['veld']}"
                    if st.session_state["sync_keuzes"].get(keuze_key) == "nbb":
                        wijzigingen.append({
                            "wed_id": mismatch["wed_id"],
                            "veld": verschil["veld"],
                            "nieuwe_waarde": verschil["nbb"]
                        })
            
            if wijzigingen:
                st.info(f"📝 **{len(wijzigingen)} wijzigingen** geselecteerd voor NBB waarden.")
                
                if st.button("✅ Voer geselecteerde wijzigingen door", key="btn_sync_apply"):
                    for wijziging in wijzigingen:
                        wed_id = wijziging["wed_id"]
                        veld = wijziging["veld"]
                        waarde = wijziging["nieuwe_waarde"]
                        wedstrijden[wed_id][veld] = waarde
                    
                    sla_wedstrijden_op(wedstrijden)
                    st.session_state["sync_keuzes"] = {}  # Reset keuzes
                    st.success(f"✅ {len(wijzigingen)} wijzigingen doorgevoerd!")
                    st.rerun()
            else:
                st.info("Alle afwijkingen worden behouden zoals in BOB.")
        else:
            st.success("✅ Geen afwijkingen gevonden - BOB en NBB zijn in sync!")
        
        # Nieuwe wedstrijden
        if nieuwe_wedstrijden:
            st.divider()
            st.subheader("➕ Nieuwe wedstrijden in NBB")
            st.write(f"**{len(nieuwe_wedstrijden)} wedstrijden** in NBB die nog niet in BOB staan:")
            
            nieuwe_preview = []
            for nw in nieuwe_wedstrijden:
                nieuwe_preview.append({
                    "Datum": nw["datum"],
                    "Thuisteam": nw["thuisteam"],
                    "Uitteam": nw["uitteam"],
                    "Niveau": nw["niveau"],
                    "Veld": nw["veld"] or "-"
                })
            
            st.dataframe(pd.DataFrame(nieuwe_preview), use_container_width=True, hide_index=True)
            st.caption("💡 Gebruik de 'NBB Wedstrijden' tab om deze te importeren.")
        
    except Exception as e:
        st.error(f"Fout bij verwerken bestand: {e}")
        import traceback
        st.code(traceback.format_exc())


def toon_import_export():
    """Import/export functionaliteit."""
    st.subheader("Import / Export")
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📥 NBB Wedstrijden", "📥 NBB Scheidsrechters", "📥 Ledengegevens", "📥 CSV Scheidsrechters", "📥 CSV Wedstrijden", "🔄 Synchronisatie", "📤 Export"])
    
    with tab1:
        st.write("**Import wedstrijden uit NBB export**")
        st.write("Upload het Excel-bestand dat je uit club.basketball.nl hebt geëxporteerd.")
        
        # Instellingen
        col1, col2 = st.columns(2)
        with col1:
            thuislocatie = st.text_input("Thuislocatie (plaatsnaam)", value="NIEUWERKERK", 
                                          help="Wedstrijden op deze locatie worden als thuiswedstrijd gemarkeerd")
        with col2:
            standaard_reistijd = st.number_input("Standaard reistijd uitwedstrijden (min)", 
                                                  min_value=15, value=45)
        
        club_naam = st.text_input("Clubnaam in teamnamen", value="Waterdragers",
                                   help="Wordt gebruikt om te bepalen welke wedstrijden van jullie club zijn")
        
        alleen_gepland = st.checkbox("Alleen geplande wedstrijden importeren", value=True)
        
        uploaded_nbb = st.file_uploader("Upload NBB Excel", type=["xlsx", "xls"], key="import_nbb")
        
        if uploaded_nbb:
            try:
                import pandas as pd
                df = pd.read_excel(uploaded_nbb)
                
                # Check of dit een NBB bestand is
                required_cols = ["Datum", "Tijd", "Thuisteam", "Uitteam", "Competitie", "Plaatsnaam"]
                missing = [c for c in required_cols if c not in df.columns]
                
                if missing:
                    st.error(f"Ontbrekende kolommen: {missing}")
                else:
                    # Filter op status indien gewenst
                    if alleen_gepland and "Status" in df.columns:
                        df = df[df["Status"] == "Gepland"]
                    
                    # Filter op club
                    df_club = df[
                        df["Thuisteam"].str.contains(club_naam, case=False, na=False) |
                        df["Uitteam"].str.contains(club_naam, case=False, na=False)
                    ]
                    
                    st.write(f"**Gevonden: {len(df_club)} wedstrijden van {club_naam}**")
                    
                    if len(df_club) > 0:
                        # Bereken niveau voor preview
                        def get_eigen_team_niveau(row):
                            if club_naam.lower() in str(row["Thuisteam"]).lower():
                                eigen_team = row["Thuisteam"]
                            else:
                                eigen_team = row["Uitteam"]
                            return bepaal_niveau_uit_team(eigen_team)
                        
                        df_preview = df_club.copy()
                        df_preview["Niveau"] = df_preview.apply(get_eigen_team_niveau, axis=1)
                        df_preview["Type"] = df_preview.apply(
                            lambda r: "Thuis" if thuislocatie.upper() in str(r.get("Plaatsnaam", "")).upper() else "Uit",
                            axis=1
                        )
                        
                        # Preview - inclusief Veld als beschikbaar
                        preview_cols = ["Datum", "Tijd", "Thuisteam", "Uitteam", "Type", "Niveau"]
                        if "Veld" in df_preview.columns:
                            preview_cols.insert(2, "Veld")
                        st.dataframe(df_preview[preview_cols].head(20))
                        
                        # Samenvatting per niveau
                        thuis_df = df_preview[df_preview["Type"] == "Thuis"]
                        if len(thuis_df) > 0:
                            st.write("**Thuiswedstrijden per niveau:**")
                            niveau_counts = thuis_df["Niveau"].value_counts().sort_index()
                            cols = st.columns(5)
                            for i, niveau in enumerate([1, 2, 3, 4, 5]):
                                count = niveau_counts.get(niveau, 0)
                                cols[i].metric(f"Niveau {niveau}", count)
                        
                        # Scheidsrechters per niveau
                        scheidsrechters = laad_scheidsrechters()
                        if scheidsrechters:
                            st.write("**Scheidsrechters per niveau (1e scheids):**")
                            scheids_per_niveau = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                            for nbb, scheids in scheidsrechters.items():
                                niveau = scheids.get("niveau_1e_scheids", 1)
                                scheids_per_niveau[niveau] = scheids_per_niveau.get(niveau, 0) + 1
                            
                            cols = st.columns(5)
                            for i, niveau in enumerate([1, 2, 3, 4, 5]):
                                count = scheids_per_niveau.get(niveau, 0)
                                cols[i].metric(f"Niveau {niveau}", count)
                            
                            # Bereken benodigde inzet
                            st.write("**Geschatte inzet per scheidsrechter:**")
                            st.caption("Elke thuiswedstrijd heeft 2 scheidsrechters nodig. Scheidsrechters met hoger niveau kunnen ook lager fluiten.")
                            
                            # Cumulatief: niveau 5 kan alles, niveau 4 kan 1-4, etc.
                            cols = st.columns(5)
                            for i, niveau in enumerate([1, 2, 3, 4, 5]):
                                wed_count = sum(niveau_counts.get(n, 0) for n in range(1, niveau + 1))
                                scheids_count = sum(scheids_per_niveau.get(n, 0) for n in range(niveau, 6))
                                
                                if scheids_count > 0:
                                    # 2 scheidsrechters per wedstrijd, 1e scheids moet niveau hebben
                                    inzet = round(wed_count / scheids_count, 1)
                                    cols[i].metric(f"t/m Niv {niveau}", f"{inzet}x", 
                                                   help=f"{wed_count} wedstrijden, {scheids_count} scheidsrechters")
                                else:
                                    cols[i].metric(f"t/m Niv {niveau}", "-")
                        
                        if st.button("✅ Importeer deze wedstrijden"):
                            wedstrijden = laad_wedstrijden()
                            count_thuis = 0
                            count_uit = 0
                            
                            for idx, row in df_club.iterrows():
                                # Bepaal datum/tijd
                                datum = pd.to_datetime(row["Datum"]).strftime("%Y-%m-%d")
                                tijd = str(row["Tijd"])[:5] if pd.notna(row["Tijd"]) else "00:00"
                                
                                # Bepaal thuis of uit
                                plaatsnaam = str(row.get("Plaatsnaam", "")).upper()
                                is_thuis = thuislocatie.upper() in plaatsnaam
                                
                                # Bepaal niveau op basis van eigen team
                                eigen_team_raw = ""
                                if club_naam.lower() in str(row["Thuisteam"]).lower():
                                    eigen_team_raw = row["Thuisteam"]
                                else:
                                    eigen_team_raw = row["Uitteam"]
                                
                                niveau = bepaal_niveau_uit_team(eigen_team_raw)
                                
                                # Check BS2 vereiste (MSE)
                                vereist_bs2 = "MSE" in str(eigen_team_raw).upper()
                                
                                wed_id = f"wed_{datum.replace('-','')}_{tijd.replace(':','')}_{idx}"
                                
                                if is_thuis:
                                    # Thuiswedstrijd - scheidsrechters nodig
                                    # Haal veld op indien beschikbaar
                                    veld_raw = row.get("Veld", "")
                                    veld = str(veld_raw).strip() if pd.notna(veld_raw) and veld_raw != "" else ""
                                    # Verwijder "Veld " prefix als aanwezig, houd alleen nummer
                                    if veld and veld != "nan":
                                        veld = veld.lower().replace("veld ", "").replace("veld", "").strip()
                                    else:
                                        veld = ""
                                    
                                    wedstrijden[wed_id] = {
                                        "datum": f"{datum} {tijd}",
                                        "thuisteam": row["Thuisteam"],
                                        "uitteam": row["Uitteam"],
                                        "niveau": niveau,
                                        "type": "thuis",
                                        "vereist_bs2": vereist_bs2,
                                        "veld": veld,
                                        "scheids_1": None,
                                        "scheids_2": None
                                    }
                                    count_thuis += 1
                                else:
                                    # Uitwedstrijd - blokkade
                                    # Bepaal welk team van ons speelt
                                    if club_naam.lower() in str(row["Thuisteam"]).lower():
                                        eigen_team = row["Thuisteam"]
                                    else:
                                        eigen_team = row["Uitteam"]
                                    
                                    wedstrijden[wed_id] = {
                                        "datum": f"{datum} {tijd}",
                                        "thuisteam": eigen_team,  # Eigen team dat uit speelt
                                        "uitteam": row["Thuisteam"] if club_naam.lower() not in str(row["Thuisteam"]).lower() else row["Uitteam"],
                                        "niveau": niveau,
                                        "type": "uit",
                                        "vereist_bs2": False,
                                        "reistijd_minuten": standaard_reistijd,
                                        "scheids_1": None,
                                        "scheids_2": None
                                    }
                                    count_uit += 1
                            
                            sla_wedstrijden_op(wedstrijden)
                            st.success(f"✅ Geïmporteerd: {count_thuis} thuiswedstrijden, {count_uit} uitwedstrijden (blokkades)")
                            st.rerun()
                    else:
                        st.warning(f"Geen wedstrijden gevonden voor '{club_naam}'")
                        
            except Exception as e:
                st.error(f"Fout bij lezen bestand: {e}")
    
    with tab2:
        st.write("**Import scheidsrechters uit NBB export**")
        st.write("Upload het Excel-bestand met tags uit club.basketball.nl")
        st.caption("Verwacht tags zoals 'Ref niveau 1' t/m 'Ref niveau 5', 'BS2', 'Niet zondag'")
        
        col1, col2 = st.columns(2)
        with col1:
            min_wedstrijden_default = st.number_input("Standaard minimum wedstrijden", min_value=0, value=2, key="min_wed_nbb")
        with col2:
            max_wedstrijden_default = st.number_input("Standaard maximum wedstrijden", min_value=1, value=5, key="max_wed_nbb")
        
        uploaded_nbb_scheids = st.file_uploader("Upload NBB Tags Excel", type=["xlsx", "xls"], key="import_nbb_scheids")
        
        if uploaded_nbb_scheids:
            try:
                import pandas as pd
                df = pd.read_excel(uploaded_nbb_scheids)
                
                # Check of dit een NBB tags bestand is
                required_cols = ["Lidnummer", "Naam"]
                missing = [c for c in required_cols if c not in df.columns]
                
                if missing:
                    st.error(f"Ontbrekende kolommen: {missing}. Verwacht: Lidnummer, Naam, Naam Tag/Kwalificatie")
                else:
                    # Filter lege rijen
                    df = df.dropna(subset=["Lidnummer"])
                    
                    if len(df) == 0:
                        st.warning("Geen scheidsrechters gevonden met Lidnummer. Controleer of de export correct is.")
                    else:
                        # Groepeer per persoon (kan meerdere tags hebben)
                        scheids_data = {}
                        
                        for idx, row in df.iterrows():
                            nbb = str(int(row["Lidnummer"])) if pd.notna(row["Lidnummer"]) else None
                            if not nbb:
                                continue
                            
                            if nbb not in scheids_data:
                                scheids_data[nbb] = {
                                    "naam": row.get("Naam", ""),
                                    "email": row.get("E-mail", ""),
                                    "niveau_1e": 1,  # Default
                                    "bs2": False,
                                    "niet_zondag": False,
                                    "tags": []
                                }
                            
                            # Parse tag
                            tag = str(row.get("Naam Tag/Kwalificatie", "")).strip()
                            if tag and tag != "nan":
                                scheids_data[nbb]["tags"].append(tag)
                                
                                # Check voor niveau tag
                                tag_upper = tag.upper()
                                if "REF" in tag_upper or "NIVEAU" in tag_upper:
                                    # Extract nummer
                                    for i in range(5, 0, -1):
                                        if str(i) in tag:
                                            scheids_data[nbb]["niveau_1e"] = max(scheids_data[nbb]["niveau_1e"], i)
                                            break
                                
                                # Check voor BS2
                                if "BS2" in tag_upper or "BS-2" in tag_upper:
                                    scheids_data[nbb]["bs2"] = True
                                
                                # Check voor zondag
                                if "ZONDAG" in tag_upper or "SUNDAY" in tag_upper:
                                    scheids_data[nbb]["niet_zondag"] = True
                        
                        st.write(f"**Gevonden: {len(scheids_data)} scheidsrechters**")
                        
                        # Preview tabel
                        preview_data = []
                        for nbb, data in scheids_data.items():
                            preview_data.append({
                                "NBB": nbb,
                                "Naam": data["naam"],
                                "1e scheids t/m": data["niveau_1e"],
                                "BS2": "✓" if data["bs2"] else "",
                                "Niet zo": "✓" if data["niet_zondag"] else "",
                                "Tags": ", ".join(data["tags"])
                            })
                        
                        st.dataframe(pd.DataFrame(preview_data))
                        
                        if st.button("✅ Importeer scheidsrechters"):
                            scheidsrechters = laad_scheidsrechters()
                            count_nieuw = 0
                            count_update = 0
                            
                            for nbb, data in scheids_data.items():
                                is_nieuw = nbb not in scheidsrechters
                                
                                scheidsrechters[nbb] = {
                                    "naam": data["naam"],
                                    "bs2_diploma": data["bs2"],
                                    "niveau_1e_scheids": data["niveau_1e"],
                                    "niveau_2e_scheids": 5,  # Altijd 5, want 2e scheids mag altijd naast hogere 1e scheids
                                    "min_wedstrijden": scheidsrechters.get(nbb, {}).get("min_wedstrijden", min_wedstrijden_default),
                                    "max_wedstrijden": scheidsrechters.get(nbb, {}).get("max_wedstrijden", max_wedstrijden_default),
                                    "niet_op_zondag": data["niet_zondag"],
                                    "eigen_teams": scheidsrechters.get(nbb, {}).get("eigen_teams", [])
                                }
                                
                                if is_nieuw:
                                    count_nieuw += 1
                                else:
                                    count_update += 1
                            
                            sla_scheidsrechters_op(scheidsrechters)
                            st.success(f"✅ {count_nieuw} nieuwe scheidsrechters, {count_update} bijgewerkt")
                            st.rerun()
                            
            except Exception as e:
                st.error(f"Fout bij lezen bestand: {e}")
                import traceback
                st.code(traceback.format_exc())
    
    with tab3:
        st.write("**Import ledengegevens (geboortedatum & teams)**")
        st.write("Upload een NBB/FOYS ledenexport om geboortedatum en teams bij te werken bij bestaande scheidsrechters.")
        st.write("**Verwachte kolommen:** Lidnummer, Geboortedatum, Team")
        
        st.info("""
        **Team parsing:** Alleen teams met '(Teamspeler)' worden overgenomen.
        
        Voorbeeld: `V12-2 (Technische staf), V16-1 (Teamspeler)` → alleen `V16-1` wordt opgeslagen.
        """)
        
        uploaded_leden = st.file_uploader("Upload Excel of CSV", type=["xlsx", "xls", "csv"], key="import_leden")
        
        if uploaded_leden:
            try:
                import pandas as pd
                if uploaded_leden.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_leden, sep=None, engine='python')
                else:
                    df = pd.read_excel(uploaded_leden)
                
                st.write(f"**{len(df)} rijen gevonden**")
                st.write("Kolommen:", ", ".join(df.columns.tolist()))
                
                # Preview
                preview_cols = [c for c in df.columns if any(x in c.lower() for x in ['lidnummer', 'geboortedatum', 'team'])]
                if preview_cols:
                    st.dataframe(df[preview_cols].head(10))
                
                if st.button("🔄 Importeer ledengegevens", key="btn_import_leden"):
                    bijgewerkt, niet_gevonden, errors = db.import_ledengegevens(df)
                    
                    if bijgewerkt > 0:
                        st.success(f"✅ {bijgewerkt} scheidsrechters bijgewerkt")
                    if niet_gevonden > 0:
                        st.warning(f"⚠️ {niet_gevonden} lidnummers niet gevonden in scheidsrechterslijst (importeer eerst scheidsrechters)")
                    if errors > 0:
                        st.error(f"❌ {errors} fouten")
                    
                    if bijgewerkt > 0:
                        st.rerun()
            except Exception as e:
                st.error(f"Fout bij lezen bestand: {e}")
    
    with tab4:
        st.write("**Import scheidsrechters (CSV)**")
        st.write("Verwacht formaat:")
        st.code("nbb_nummer,naam,bs2_diploma,niveau_1e,niveau_2e,min,max,niet_zondag,eigen_teams")
        
        uploaded_scheids = st.file_uploader("Upload CSV", type="csv", key="import_scheids")
        if uploaded_scheids:
            import csv
            import io
            
            content = uploaded_scheids.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(content))
            
            # Preview
            rows = list(reader)
            st.info(f"📋 {len(rows)} scheidsrechters gevonden in bestand")
            
            if st.button("✅ Importeer scheidsrechters", key="btn_import_scheids"):
                scheidsrechters = laad_scheidsrechters()
                count = 0
                
                for row in rows:
                    nbb = row.get("nbb_nummer", "").strip()
                    if nbb:
                        scheidsrechters[nbb] = {
                            "naam": row.get("naam", "").strip(),
                            "bs2_diploma": row.get("bs2_diploma", "").lower() in ["ja", "yes", "true", "1"],
                            "niveau_1e_scheids": int(row.get("niveau_1e", 1)),
                            "niveau_2e_scheids": int(row.get("niveau_2e", 2)),
                            "min_wedstrijden": int(row.get("min", 2)),
                            "max_wedstrijden": int(row.get("max", 5)),
                            "niet_op_zondag": row.get("niet_zondag", "").lower() in ["ja", "yes", "true", "1"],
                            "eigen_teams": [t.strip() for t in row.get("eigen_teams", "").split(";") if t.strip()]
                        }
                        count += 1
                
                sla_scheidsrechters_op(scheidsrechters)
                st.success(f"✅ {count} scheidsrechters geïmporteerd!")
                st.rerun()
    
    with tab5:
        st.write("**Import wedstrijden (CSV)**")
        st.write("Verwacht formaat:")
        st.code("datum,tijd,thuisteam,uitteam,niveau,type,vereist_bs2,reistijd_minuten")
        st.caption("type = 'thuis' of 'uit', reistijd_minuten voor uitwedstrijden")
        
        uploaded_wed = st.file_uploader("Upload CSV", type="csv", key="import_wed")
        if uploaded_wed:
            import csv
            import io
            
            content = uploaded_wed.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(content))
            
            # Preview
            rows = list(reader)
            st.info(f"📋 {len(rows)} wedstrijden gevonden in bestand")
            
            if st.button("✅ Importeer wedstrijden", key="btn_import_wed"):
                wedstrijden = laad_wedstrijden()
                count = 0
                
                for row in rows:
                    datum = row.get("datum", "").strip()
                    tijd = row.get("tijd", "").strip()
                    thuisteam = row.get("thuisteam", "").strip()
                    
                    if datum and thuisteam:
                        wed_id = f"wed_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{count}"
                        wed_type = row.get("type", "thuis").strip().lower()
                        
                        nieuwe_wed = {
                            "datum": f"{datum} {tijd}",
                            "thuisteam": thuisteam,
                            "uitteam": row.get("uitteam", "").strip(),
                            "niveau": int(row.get("niveau", 1)),
                            "type": wed_type,
                            "vereist_bs2": row.get("vereist_bs2", "").lower() in ["ja", "yes", "true", "1"],
                            "scheids_1": None,
                            "scheids_2": None
                        }
                        
                        if wed_type == "uit":
                            nieuwe_wed["reistijd_minuten"] = int(row.get("reistijd_minuten", 60))
                        
                        wedstrijden[wed_id] = nieuwe_wed
                        count += 1
                
                sla_wedstrijden_op(wedstrijden)
                st.success(f"✅ {count} wedstrijden geïmporteerd!")
                st.rerun()
    
    with tab6:
        toon_synchronisatie_tab()
    
    with tab7:
        st.write("**📤 Exporteer data**")
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            st.markdown("**Wedstrijden:**")
            
            if st.button("📥 Thuiswedstrijden + planning", use_container_width=True):
                wedstrijden = laad_wedstrijden()
                scheidsrechters = laad_scheidsrechters()
                
                output = "datum,tijd,thuisteam,uitteam,niveau,scheids_1,scheids_2,begeleider\n"
                for wed_id, wed in sorted(wedstrijden.items(), key=lambda x: x[1]["datum"]):
                    if wed.get("type", "thuis") != "thuis":
                        continue
                    datum_obj = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                    scheids_1_naam = scheidsrechters.get(wed.get("scheids_1", ""), {}).get("naam", "")
                    scheids_2_naam = scheidsrechters.get(wed.get("scheids_2", ""), {}).get("naam", "")
                    begeleider_naam = scheidsrechters.get(wed.get("begeleider", ""), {}).get("naam", "")
                    
                    output += f"{datum_obj.strftime('%Y-%m-%d')},{datum_obj.strftime('%H:%M')},"
                    output += f"{wed['thuisteam']},{wed['uitteam']},{wed['niveau']},"
                    output += f"{scheids_1_naam},{scheids_2_naam},{begeleider_naam}\n"
                
                st.download_button(
                    "📥 Download CSV",
                    output,
                    file_name="scheidsrechter_planning.csv",
                    mime="text/csv",
                    key="dl_thuiswed"
                )
            
            if st.button("📥 Alle wedstrijden", use_container_width=True):
                wedstrijden = laad_wedstrijden()
                
                output = "datum,tijd,thuisteam,uitteam,niveau,type,vereist_bs2,reistijd_minuten\n"
                for wed_id, wed in sorted(wedstrijden.items(), key=lambda x: x[1]["datum"]):
                    datum_obj = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                    wed_type = wed.get("type", "thuis")
                    
                    output += f"{datum_obj.strftime('%Y-%m-%d')},{datum_obj.strftime('%H:%M')},"
                    output += f"{wed['thuisteam']},{wed['uitteam']},{wed['niveau']},"
                    output += f"{wed_type},{'ja' if wed.get('vereist_bs2') else 'nee'},"
                    output += f"{wed.get('reistijd_minuten', 0)}\n"
                
                st.download_button(
                    "📥 Download CSV",
                    output,
                    file_name="alle_wedstrijden.csv",
                    mime="text/csv",
                    key="dl_allewed"
                )
        
        with col_exp2:
            st.markdown("**Scheidsrechters:**")
            
            if st.button("📥 Scheidsrechters + statistieken", use_container_width=True):
                scheidsrechters = laad_scheidsrechters()
                beloningen = laad_beloningen()
                wedstrijden = laad_wedstrijden()
                
                # Tel gefloten wedstrijden per scheidsrechter (uit wedstrijden data)
                gefloten_count = {}
                for wed_id, wed in wedstrijden.items():
                    for scheids_key in ["scheids_1", "scheids_2"]:
                        nbb = wed.get(scheids_key)
                        if nbb:
                            gefloten_count[nbb] = gefloten_count.get(nbb, 0) + 1
                
                output = "nbb_nummer,naam,niveau_1e_scheids,min_wedstrijden,eigen_teams,bs2_diploma,open_voor_begeleiding,punten,strikes,gefloten_wedstrijden\n"
                for nbb, scheids in sorted(scheidsrechters.items(), key=lambda x: x[1].get("naam", "")):
                    eigen_teams = ";".join(scheids.get("eigen_teams", []))
                    bel_data = beloningen.get("spelers", {}).get(nbb, {})
                    
                    output += f"{nbb},"
                    output += f"\"{scheids.get('naam', '')}\","
                    output += f"{scheids.get('niveau_1e_scheids', 1)},"
                    output += f"{scheids.get('min_wedstrijden', 0)},"
                    output += f"\"{eigen_teams}\","
                    output += f"{'ja' if scheids.get('bs2_diploma') else 'nee'},"
                    output += f"{'ja' if scheids.get('open_voor_begeleiding') else 'nee'},"
                    output += f"{bel_data.get('punten', 0)},"
                    output += f"{bel_data.get('strikes', 0)},"
                    output += f"{gefloten_count.get(nbb, 0)}\n"
                
                st.download_button(
                    "📥 Download CSV",
                    output,
                    file_name="scheidsrechters_export.csv",
                    mime="text/csv",
                    key="dl_scheids"
                )
            
            if st.button("📥 Beloningen detail", use_container_width=True):
                scheidsrechters = laad_scheidsrechters()
                beloningen = laad_beloningen()
                
                output = "nbb_nummer,naam,punten,strikes,aantal_registraties\n"
                for nbb, data in beloningen.get("spelers", {}).items():
                    naam = scheidsrechters.get(nbb, {}).get("naam", nbb)
                    aantal_reg = len(data.get("gefloten_wedstrijden", []))
                    
                    output += f"{nbb},\"{naam}\","
                    output += f"{data.get('punten', 0)},"
                    output += f"{data.get('strikes', 0)},"
                    output += f"{aantal_reg}\n"
                
                st.download_button(
                    "📥 Download CSV",
                    output,
                    file_name="beloningen_export.csv",
                    mime="text/csv",
                    key="dl_beloningen"
                )

# ============================================================
# BEHEERDER AUTHENTICATIE
# ============================================================

def _toon_beheerder_login():
    """Toon beheerder login formulier"""
    st.title("🔐 Beheerder Login")
    
    # Check of force reset actief is
    try:
        if st.secrets.get("FORCE_RESET", False):
            st.warning("⚠️ Wachtwoord reset modus actief. Log in met het standaard wachtwoord.")
    except:
        pass
    
    with st.form("login_form"):
        wachtwoord = st.text_input("Wachtwoord", type="password")
        submitted = st.form_submit_button("Inloggen", use_container_width=True)
        
        if submitted:
            if not wachtwoord:
                st.error("Voer een wachtwoord in")
                return
            
            if db.verify_admin_password(wachtwoord):
                st.session_state.beheerder_ingelogd = True
                # Check of wachtwoord gewijzigd moet worden
                if db.needs_password_change():
                    st.session_state.moet_wachtwoord_wijzigen = True
                    st.success("✅ Ingelogd. Je moet nu een nieuw wachtwoord instellen.")
                st.rerun()
            else:
                st.error("❌ Onjuist wachtwoord")


def _toon_wachtwoord_wijzigen():
    """Toon wachtwoord wijzigen formulier"""
    st.title("🔑 Nieuw Wachtwoord Instellen")
    
    try:
        if st.secrets.get("FORCE_RESET", False):
            st.info("💡 Na het instellen van je nieuwe wachtwoord, verwijder `FORCE_RESET` uit je Streamlit Cloud Secrets.")
    except:
        pass
    
    with st.form("change_password_form"):
        nieuw_wachtwoord = st.text_input("Nieuw wachtwoord", type="password")
        bevestig_wachtwoord = st.text_input("Bevestig wachtwoord", type="password")
        submitted = st.form_submit_button("Wachtwoord opslaan", use_container_width=True)
        
        if submitted:
            if not nieuw_wachtwoord or not bevestig_wachtwoord:
                st.error("Vul beide velden in")
                return
            
            if nieuw_wachtwoord != bevestig_wachtwoord:
                st.error("Wachtwoorden komen niet overeen")
                return
            
            if len(nieuw_wachtwoord) < 8:
                st.error("Wachtwoord moet minimaal 8 tekens zijn")
                return
            
            if nieuw_wachtwoord == db.get_default_admin_password():
                st.error("Kies een ander wachtwoord dan het standaard wachtwoord")
                return
            
            # Opslaan
            if db.save_admin_password_hash(nieuw_wachtwoord):
                st.session_state.moet_wachtwoord_wijzigen = False
                st.success("✅ Wachtwoord gewijzigd!")
                st.rerun()
            else:
                st.error("Fout bij opslaan wachtwoord")


def _check_device_verificatie(nbb_nummer: str) -> bool:
    """
    Check of device geverifieerd is. Toont verificatie scherm indien nodig.
    Returns True als geverifieerd, False als verificatie scherm getoond wordt.
    """
    session_key = f"device_token_{nbb_nummer}"
    verified_key = f"device_verified_{nbb_nummer}"
    
    # Check of we net geverifieerd zijn (flag gezet in vorige run)
    if st.session_state.get(verified_key, False):
        token = st.session_state.get(session_key)
        if token and db.token_exists_in_database(nbb_nummer, token):
            if db.verify_device_token(nbb_nummer, token):
                del st.session_state[verified_key]
                return True
    
    # Check of speler geboortedatum heeft
    geboortedatum = db.get_speler_geboortedatum(nbb_nummer)
    
    if not geboortedatum:
        return True
    
    # Check of er al een device is met deze fingerprint
    device_exists, existing_token = db.device_exists_for_fingerprint(nbb_nummer)
    
    if device_exists and existing_token:
        # Device al geregistreerd - check of token geldig is
        if db.verify_device_token(nbb_nummer, existing_token):
            st.session_state[session_key] = existing_token
            return True
        
        # Token bestaat maar is pending
        if db.is_device_pending(nbb_nummer, existing_token):
            st.title("⏳ Wachten op goedkeuring")
            st.info("Dit apparaat wacht op goedkeuring.")
            if st.button("🔄 Ververs"):
                st.rerun()
            return False
    
    # Check bestaande token uit session (fallback)
    token = db.get_device_token_from_cookie(nbb_nummer)
    
    if token:
        token_exists = db.token_exists_in_database(nbb_nummer, token)
        
        if not token_exists:
            db.clear_device_token_cookie(nbb_nummer)
            st.info("Je apparaat is uitgelogd. Verifieer opnieuw.")
            st.rerun()
        else:
            if db.verify_device_token(nbb_nummer, token):
                return True
    
    # Check of we een nieuw device kunnen toevoegen
    can_add, reason = db.can_add_device(nbb_nummer)
    
    if not can_add:
        st.title("🚫 Apparaat limiet bereikt")
        st.error(reason)
        st.info("Verwijder eerst een ander apparaat.")
        return False
    
    # Nieuw device - verificatie nodig
    device_name = db._get_device_name_from_ua()
    
    st.title("🔐 Verificatie")
    st.write(f"Nieuw apparaat: **{device_name}**")
    st.write("Bevestig je identiteit met je geboortedatum.")
    
    with st.form("verificatie_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            dag = st.number_input("Dag", min_value=1, max_value=31, value=1)
        with col2:
            maand = st.number_input("Maand", min_value=1, max_value=12, value=1)
        with col3:
            jaar = st.number_input("Jaar", min_value=1950, max_value=2020, value=2005)
        
        submitted = st.form_submit_button("Verifiëren", use_container_width=True)
        
        if submitted:
            if db.verify_geboortedatum(nbb_nummer, dag, maand, jaar):
                new_token = db._generate_device_token()
                success, needs_approval = db.register_device_with_approval(nbb_nummer, new_token)
                
                if success:
                    st.session_state[session_key] = new_token
                    st.session_state[verified_key] = True
                    
                    if needs_approval:
                        st.warning("✅ Geverifieerd! Wacht op goedkeuring.")
                    else:
                        st.success("✅ Geverifieerd!")
                    st.rerun()
                else:
                    st.error("❌ Fout bij registreren.")
            else:
                st.error("❌ Geboortedatum klopt niet")
    
    return False


# ============================================================
# MAIN ROUTING
# ============================================================

def main():
    st.set_page_config(
        page_title="Scheidsrechter Planning",
        page_icon="🏀",
        layout="wide"
    )
    
    # PWA meta tags injecteren (iconen via GitHub raw)
    github_base = "https://raw.githubusercontent.com/GKN14/waterdragers-ref-planner/main"
    st.markdown(f"""
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="apple-mobile-web-app-title" content="Scheidsrechters">
        <meta name="theme-color" content="#F5B800">
        <link rel="apple-touch-icon" href="{github_base}/static/icon-192.png">
        <link rel="icon" type="image/png" sizes="192x192" href="{github_base}/static/icon-192.png">
    """, unsafe_allow_html=True)
    
    # Injecteer custom CSS
    inject_custom_css()
    
    # Logo laden indien aanwezig
    logo_path = Path(__file__).parent / "logo.png"
    
    # Haal query parameters op
    query_params = st.query_params
    
    # Route: /inschrijven/{nbb_nummer}
    if "nbb" in query_params:
        nbb_nummer = query_params["nbb"]
        
        # Device verificatie
        if not _check_device_verificatie(nbb_nummer):
            return
        
        toon_speler_view(nbb_nummer)
        return
    
    # Route: /beheer
    if "beheer" in query_params:
        # Initialiseer session state
        if "beheerder_ingelogd" not in st.session_state:
            st.session_state.beheerder_ingelogd = False
        if "moet_wachtwoord_wijzigen" not in st.session_state:
            st.session_state.moet_wachtwoord_wijzigen = False
        
        # Wachtwoord wijzigen scherm
        if st.session_state.moet_wachtwoord_wijzigen:
            _toon_wachtwoord_wijzigen()
            return
        
        # Login scherm
        if not st.session_state.beheerder_ingelogd:
            _toon_beheerder_login()
            return
        
        toon_beheerder_view()
        return
    
    # Default: landingspagina
    logo_path = Path(__file__).parent / "logo.png"
    if logo_path.exists():
        col_logo, col_title = st.columns([1, 4])
        with col_logo:
            st.image(str(logo_path), width=120)
        with col_title:
            st.title("Scheidsrechter Planning")
            st.write("BV Waterdragers")
    else:
        st.title("🏀 Scheidsrechter Planning")
        st.write("BV Waterdragers")
    
    st.divider()
    
    st.subheader("Voor scheidsrechters")
    st.write("Gebruik de link die je via e-mail/app hebt ontvangen om je in te schrijven.")
    
    st.divider()
    
    st.subheader("Voor de TC")
    st.write("Ga naar het beheerderspaneel:")
    if st.button("🔧 Beheer"):
        st.query_params["beheer"] = "1"
        st.rerun()

if __name__ == "__main__":
    main()
