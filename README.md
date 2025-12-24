# Scheidsrechter Planning App

Streamlit applicatie voor het plannen van scheidsrechters bij BV Waterdragers.

## Installatie

```bash
pip install -r requirements.txt
```

## Lokaal draaien

```bash
streamlit run app.py
```

De app draait dan op http://localhost:8501

## URLs

| URL | Gebruik |
|-----|---------|
| `/?nbb=12345678` | Inschrijfpagina voor speler met NBB-nummer 12345678 |
| `/?beheer=1` | Beheerderspaneel (wachtwoord vereist) |

## Beheerder wachtwoord

Standaard: `waterdragers2025`

Pas aan in `app.py` (regel 12): `BEHEERDER_WACHTWOORD = "jouw_wachtwoord"`

## E-mail template club.basketball.nl

In de e-mail template kun je de volgende link gebruiken:

```
https://jouw-app.streamlit.app/?nbb={{lidnummer}}
```

(Pas de URL aan naar je eigen Streamlit Community Cloud URL)

## Data bestanden

De app slaat data op in JSON bestanden in de `data/` map:

- `scheidsrechters.json` - Scheidsrechterslijst
- `wedstrijden.json` - Wedstrijden en toewijzingen  
- `instellingen.json` - Deadline en niveau-omschrijvingen
- `inschrijvingen.json` - (wordt automatisch aangemaakt)

## Import CSV formaat

### Scheidsrechters

```csv
nbb_nummer,naam,bs2_diploma,niveau_1e,niveau_2e,min,max,niet_zondag,eigen_teams
12345678,Jan de Vries,ja,4,5,2,5,nee,HS1;U18-1
23456789,Karin Bakker,ja,5,5,2,4,nee,DS1
```

Let op: eigen_teams zijn gescheiden met puntkomma (;)

### Wedstrijden

```csv
datum,tijd,thuisteam,uitteam,niveau,type,vereist_bs2,reistijd_minuten
2025-01-11,14:00,U12-1,Grasshoppers U12,1,thuis,nee,0
2025-01-11,10:00,HS1,Rotterdam,4,uit,nee,45
```

**Velden:**
- `type`: "thuis" (scheidsrechters nodig) of "uit" (alleen blokkade)
- `reistijd_minuten`: alleen relevant voor uitwedstrijden
- Bij uitwedstrijden is "thuisteam" het eigen team dat uit speelt

**Blokkade-logica:** 
Spelers kunnen niet fluiten wanneer hun eigen team speelt (thuis of uit). Bij uitwedstrijden wordt de reistijd meegenomen in de blokkade.

## Deployen naar Streamlit Community Cloud

1. Maak een GitHub repository aan
2. Push deze bestanden naar de repository
3. Ga naar https://share.streamlit.io
4. Koppel je GitHub account
5. Selecteer de repository en `app.py`
6. Deploy!

De data blijft bewaard zolang de app actief is op Streamlit Cloud.

## Niveaus

| Niveau | Wedstrijden |
|--------|-------------|
| 1 | U10, U12 |
| 2 | U14, U16 recreatie |
| 3 | U16 hogere divisie, U18 |
| 4 | Senioren lager |
| 5 | Senioren hoger, MSE |

Deze zijn aanpasbaar in het beheerderspaneel.
