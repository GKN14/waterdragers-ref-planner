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

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

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
BEHEERDER_WACHTWOORD = "waterdragers2025"  # Pas aan!

# Teams waaruit scheidsrechters komen (vanaf U16, plus coaches van lagere teams)
SCHEIDSRECHTER_TEAMS = [
    "X14-1",  # Voor coaches
    "M16-1", "M16-2",
    "V16-1", "V16-2",
    "M18-1", "M18-2", "M18-3",
    "M20-1",
    "MSE"
]

def team_match(volledig_team: str, eigen_team: str) -> bool:
    """
    Check of een volledige teamnaam (bijv. 'Waterdragers - M18-3**') 
    matcht met een eigen team (bijv. 'M18-3').
    """
    if not volledig_team or not eigen_team:
        return False
    
    # Normaliseer: uppercase en verwijder sterretjes
    volledig = str(volledig_team).upper().replace("*", "").strip()
    eigen = str(eigen_team).upper().replace("*", "").strip()
    
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

def laad_scheidsrechters() -> dict:
    return laad_json("scheidsrechters.json")

def laad_wedstrijden() -> dict:
    return laad_json("wedstrijden.json")

def laad_inschrijvingen() -> dict:
    return laad_json("inschrijvingen.json")

def laad_instellingen() -> dict:
    instellingen = laad_json("instellingen.json")
    if not instellingen:
        instellingen = {
            "inschrijf_deadline": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
            "niveaus": {
                "1": "X10-1, X10-2, X12-2, V12-2",
                "2": "X12-1, V12-1, X14-2, M16-2", 
                "3": "X14-1, M16-1, V16-2",
                "4": "V16-1, M18-2, M18-3",
                "5": "M18-1, M20-1, MSE (BS2 vereist)"
            }
        }
        sla_json_op("instellingen.json", instellingen)
    return instellingen

def sla_scheidsrechters_op(data: dict):
    sla_json_op("scheidsrechters.json", data)

def sla_wedstrijden_op(data: dict):
    sla_json_op("wedstrijden.json", data)

def sla_inschrijvingen_op(data: dict):
    sla_json_op("inschrijvingen.json", data)

def sla_instellingen_op(data: dict):
    sla_json_op("instellingen.json", data)

def laad_beloningen() -> dict:
    """Laad beloningen (punten, strikes per speler)."""
    beloningen = laad_json("beloningen.json")
    if not beloningen:
        beloningen = {
            "seizoen": "2024-2025",
            "spelers": {}
        }
        sla_json_op("beloningen.json", beloningen)
    return beloningen

def sla_beloningen_op(data: dict):
    sla_json_op("beloningen.json", data)

def laad_klusjes() -> dict:
    """Laad klusjes (toegewezen aan spelers)."""
    return laad_json("klusjes.json")

def sla_klusjes_op(data: dict):
    sla_json_op("klusjes.json", data)

def laad_vervangingsverzoeken() -> dict:
    """Laad openstaande vervangingsverzoeken."""
    return laad_json("vervangingsverzoeken.json")

def sla_vervangingsverzoeken_op(data: dict):
    sla_json_op("vervangingsverzoeken.json", data)

def laad_beschikbare_klusjes() -> list:
    """Laad de lijst met beschikbare klusjes die TC kan toewijzen."""
    data = laad_json("beschikbare_klusjes.json")
    if not data:
        # Default klusjes
        data = [
            {"id": "ballen_oppompen", "naam": "Ballen oppompen", "omschrijving": "Ballen oppompen op alle 3 locaties", "strikes_waarde": 1},
            {"id": "coach_ondersteunen", "naam": "Coach ondersteunen (2x)", "omschrijving": "2x een coach ondersteunen bij een training, bijv. 1-op-1 fundamental training met een speler", "strikes_waarde": 1},
        ]
        sla_json_op("beschikbare_klusjes.json", data)
    return data

def sla_beschikbare_klusjes_op(data: list):
    sla_json_op("beschikbare_klusjes.json", data)

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
        "strike_log": speler_data.get("strike_log", [])
    }

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
    nu = datetime.now()
    verschil = wed_datum - nu
    uren = verschil.total_seconds() / 3600
    
    if uren < 24:
        return {"is_inval": True, "bonus": 5, "uren": 24}
    elif uren < 48:
        return {"is_inval": True, "bonus": 3, "uren": 48}
    else:
        return {"is_inval": False, "bonus": 0, "uren": 0}

def bereken_punten_voor_wedstrijd(nbb_nummer: str, wed_id: str, wedstrijden: dict, scheidsrechters: dict) -> dict:
    """
    Bereken hoeveel punten een speler krijgt voor een wedstrijd.
    Returns: {"basis": int, "lastig_tijdstip": int, "inval_bonus": int, "totaal": int, "details": str, "berekening": dict}
    """
    wed = wedstrijden.get(wed_id, {})
    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    nu = datetime.now()
    
    # Bereken uren tot wedstrijd
    verschil = wed_datum - nu
    uren_tot_wedstrijd = verschil.total_seconds() / 3600
    
    # Basis: 1 punt
    basis = 1
    
    # Lastig tijdstip: +1
    lastig = 1 if is_lastig_tijdstip(nbb_nummer, wed_datum, wedstrijden, scheidsrechters) else 0
    
    # Last-minute inval: +3 of +5
    inval_info = is_last_minute_inval(wed_id, wed_datum)
    inval_bonus = inval_info["bonus"]
    
    totaal = basis + lastig + inval_bonus
    
    details = []
    details.append("1 basis")
    if lastig:
        details.append("+1 lastig tijdstip")
    if inval_bonus:
        details.append(f"+{inval_bonus} inval <{inval_info['uren']}u")
    
    # Gedetailleerde berekening voor transparantie
    berekening = {
        "inschrijf_moment": nu.isoformat(),
        "inschrijf_moment_leesbaar": nu.strftime("%d-%m-%Y %H:%M"),
        "wedstrijd_datum": wed_datum.isoformat(),
        "wedstrijd_datum_leesbaar": wed_datum.strftime("%d-%m-%Y %H:%M"),
        "uren_tot_wedstrijd": round(uren_tot_wedstrijd, 1),
        "is_inval_48u": uren_tot_wedstrijd < 48,
        "is_inval_24u": uren_tot_wedstrijd < 24,
        "is_lastig_tijdstip": lastig == 1
    }
    
    return {
        "basis": basis,
        "lastig_tijdstip": lastig,
        "inval_bonus": inval_bonus,
        "totaal": totaal,
        "details": ", ".join(details),
        "berekening": berekening
    }

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
    """Check of inschrijfperiode nog loopt."""
    instellingen = laad_instellingen()
    deadline = datetime.strptime(instellingen["inschrijf_deadline"], "%Y-%m-%d")
    return datetime.now() <= deadline

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
        return {"ingeschreven_zelf": False, "bezet": True, "naam": naam, "beschikbaar": False, "reden": ""}
    
    # Positie is open - check of speler mag inschrijven
    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    
    # Check niveau
    max_niveau = scheids.get("niveau_1e_scheids", 1) if als_eerste else scheids.get("niveau_2e_scheids", 5)
    if wed["niveau"] > max_niveau:
        return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": f"niveau {wed['niveau']} te hoog"}
    
    # Check BS2 vereiste
    if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
        return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": "BS2 vereist"}
    
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
        return {"ingeschreven_zelf": False, "bezet": False, "naam": "", "beschikbaar": False, "reden": "eigen wedstrijd"}
    
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
    max_niveau = scheids["niveau_1e_scheids"] if als_eerste else scheids["niveau_2e_scheids"]
    
    beschikbaar = []
    for wed_id, wed in wedstrijden.items():
        # Alleen thuiswedstrijden tonen (uitwedstrijden zijn alleen voor blokkade)
        if wed.get("type") == "uit":
            continue
        
        # Check niveau
        if wed["niveau"] > max_niveau:
            continue
        
        # Check BS2 vereiste
        if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
            continue
        
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

def tel_wedstrijden_op_eigen_niveau(nbb_nummer: str) -> dict:
    """
    Tel wedstrijden op eigen niveau voor minimum check.
    
    Returns dict met:
    - totaal: totaal aantal wedstrijden
    - op_niveau: aantal wedstrijden op eigen niveau (niveau van 1e scheids)
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
            # Tel als "op niveau" als wedstrijd niveau == eigen niveau
            if wed.get("niveau", 1) == eigen_niveau:
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
    
    kandidaten = []
    for nbb, scheids in scheidsrechters.items():
        max_niveau = scheids["niveau_1e_scheids"] if als_eerste else scheids["niveau_2e_scheids"]
        eigen_niveau = scheids.get("niveau_1e_scheids", 1)
        
        # Check niveau
        if wed["niveau"] > max_niveau:
            continue
        
        # Check BS2 vereiste
        if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
            continue
        
        # Check eigen team (thuiswedstrijd van eigen team) - flexibele matching
        eigen_teams_scheids = scheids.get("eigen_teams", [])
        is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams_scheids)
        is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams_scheids)
        if is_eigen_thuis or is_eigen_uit:
            continue
        
        # Check zondag
        if scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6:
            continue
        
        # Check of scheidsrechter op dit tijdstip een eigen wedstrijd heeft
        if heeft_eigen_wedstrijd(nbb, wed_datum, wedstrijden, scheidsrechters):
            continue
        
        # Check maximum (totaal aantal wedstrijden)
        huidig_totaal = tel_wedstrijden_scheidsrechter(nbb)
        if huidig_totaal >= scheids.get("max_wedstrijden", 99):
            continue
        
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
        
        # Is deze wedstrijd op eigen niveau?
        is_op_eigen_niveau = wed_niveau == eigen_niveau
        
        # Tekort berekenen: alleen relevant als wedstrijd op eigen niveau is
        if is_op_eigen_niveau:
            tekort = max(0, min_wed - op_niveau)
        else:
            tekort = 0  # Wedstrijd niet op eigen niveau telt niet mee voor minimum
        
        kandidaten.append({
            "nbb_nummer": nbb,
            "naam": scheids["naam"],
            "huidig_aantal": huidig_totaal,
            "op_niveau": op_niveau,
            "eigen_niveau": eigen_niveau,
            "min_wedstrijden": min_wed,
            "max_wedstrijden": scheids.get("max_wedstrijden", 99),
            "tekort": tekort,
            "is_op_eigen_niveau": is_op_eigen_niveau
        })
    
    # Sorteer: eerst wie tekort heeft op eigen niveau, dan op minste wedstrijden
    return sorted(kandidaten, key=lambda x: (-x["tekort"], x["huidig_aantal"]))

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
    
    # Sidebar met legenda
    with st.sidebar:
        st.markdown("### 📋 Legenda")
        
        # Niveau uitleg
        st.markdown("**Niveaus**")
        niveaus = instellingen.get("niveaus", {})
        for niveau in sorted(niveaus.keys(), key=int):
            omschrijving = niveaus[niveau]
            st.markdown(f"**{niveau}** - {omschrijving}")
        
        st.divider()
        
        # Kleuren uitleg
        st.markdown("**Kleuren**")
        st.markdown("""
        <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 0.5rem; margin: 0.25rem 0; border-radius: 0 0.25rem 0.25rem 0; font-size: 0.85rem;">
            ⭐ <strong>Jouw niveau</strong>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div style="background-color: #f0f2f6; border-left: 4px solid #6c757d; padding: 0.5rem; margin: 0.25rem 0; border-radius: 0 0.25rem 0.25rem 0; font-size: 0.85rem;">
            🏀 Onder jouw niveau
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 0.5rem; margin: 0.25rem 0; border-radius: 0 0.25rem 0.25rem 0; font-size: 0.85rem;">
            🏠🚗 Eigen wedstrijd
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Iconen uitleg
        st.markdown("**Symbolen**")
        st.markdown("🙋 Jij bent ingeschreven")
        st.markdown("👤 Iemand anders")
        st.markdown("📋 Beschikbaar")
        
        st.divider()
        
        # Jouw gegevens
        st.markdown("**Jouw gegevens**")
        eigen_niveau = scheids.get("niveau_1e_scheids", 1)
        st.markdown(f"1e scheids niveau: **{eigen_niveau}**")
        niveau_2e = scheids.get("niveau_2e_scheids", 5)
        st.markdown(f"2e scheids niveau: **{niveau_2e}**")
        if scheids.get("bs2_diploma", False):
            st.markdown("✅ BS2 diploma")
        eigen_teams = scheids.get("eigen_teams", [])
        if eigen_teams:
            st.markdown(f"Teams: {', '.join(eigen_teams)}")
        
        st.divider()
        
        # Puntensysteem uitleg
        st.markdown("### 🏆 Punten verdienen")
        st.markdown("""
        Wedstrijden **boven je minimum** leveren punten op:
        
        | Actie | Punten |
        |-------|--------|
        | Wedstrijd fluiten | 1 |
        | Lastig tijdstip* | +1 |
        | Invallen <48 uur | +3 |
        | Invallen <24 uur | +5 |
        
        *Lastig = apart terugkomen om te fluiten
        
        **15 punten** = voucher Clinic!
        """)
        
        st.divider()
        
        # Strikes uitleg
        st.markdown("### ⚠️ Strikes")
        st.markdown("""
        | Situatie | Strikes |
        |----------|---------|
        | Afmelding <48u | 1 |
        | Afmelding <24u | 2 |
        | No-show | 5 |
        
        **Met vervanging** = geen strike!
        
        Strikes wegwerken:
        - Klusje doen (-1)
        - Extra wedstrijd (-1)
        - Invallen <48u (-2)
        """)
        
        # Toon eigen puntenhistorie als er punten zijn
        if speler_stats["punten"] > 0 or speler_stats["strikes"] > 0:
            st.divider()
            st.markdown("### 📊 Jouw historie")
            
            if speler_stats["gefloten_wedstrijden"]:
                with st.expander(f"🏆 Punten ({speler_stats['punten']} totaal)"):
                    for wed_reg in reversed(speler_stats["gefloten_wedstrijden"][-5:]):
                        berekening = wed_reg.get("berekening", {})
                        if berekening:
                            st.markdown(f"""
                            **+{wed_reg['punten']}** op {berekening.get('inschrijf_moment_leesbaar', '?')}  
                            *{berekening.get('uren_tot_wedstrijd', '?')}u tot wedstrijd*
                            """)
                        else:
                            st.markdown(f"**+{wed_reg['punten']}** - {wed_reg.get('reden', '')}")
            
            if speler_stats["strike_log"]:
                with st.expander(f"⚠️ Strikes ({speler_stats['strikes']} actief)"):
                    for strike in reversed(speler_stats["strike_log"][-5:]):
                        teken = "+" if strike["strikes"] > 0 else ""
                        st.markdown(f"**{teken}{strike['strikes']}** - {strike['reden']}")
    
    # Header met logo
    logo_path = Path(__file__).parent / "logo.png"
    if logo_path.exists():
        col_logo, col_title = st.columns([1, 4])
        with col_logo:
            st.image(str(logo_path), width=100)
        with col_title:
            st.title("Scheidsrechter Inschrijving")
            st.subheader(f"Welkom, {scheids['naam']}")
    else:
        st.title("🏀 Scheidsrechter Inschrijving")
        st.subheader(f"Welkom, {scheids['naam']}")
    
    # Status - niveau-gebaseerde telling
    niveau_stats = tel_wedstrijden_op_eigen_niveau(nbb_nummer)
    huidig_aantal = niveau_stats["totaal"]
    op_niveau = niveau_stats["op_niveau"]
    eigen_niveau = niveau_stats["niveau"]
    min_wed = scheids.get("min_wedstrijden", 0)
    max_wed = scheids.get("max_wedstrijden", 99)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Totaal", huidig_aantal)
    with col2:
        st.metric(f"Op niveau {eigen_niveau}", op_niveau, 
                  help=f"Wedstrijden op jouw niveau ({eigen_niveau}) tellen mee voor je minimum")
    with col3:
        st.metric("Minimum", min_wed)
    with col4:
        st.metric("Maximum", max_wed)
    with col5:
        st.metric("🏆 Punten", speler_stats["punten"], help="Punten voor wedstrijden boven je minimum")
    with col6:
        strikes = speler_stats["strikes"]
        if strikes >= 5:
            st.metric("⚠️ Strikes", strikes, delta="Gesprek TC", delta_color="inverse")
        elif strikes >= 3:
            st.metric("⚠️ Strikes", strikes, delta="Waarschuwing", delta_color="inverse")
        else:
            st.metric("Strikes", strikes)
    
    # Check of aan minimum is voldaan (op eigen niveau)
    if op_niveau < min_wed:
        tekort = min_wed - op_niveau
        st.warning(f"⚠️ Je moet nog **{tekort}** wedstrijd(en) kiezen op niveau {eigen_niveau}.")
    elif huidig_aantal >= max_wed:
        st.success("✅ Je hebt je maximum bereikt.")
    else:
        st.success(f"✅ Je hebt aan je minimum voldaan ({op_niveau}/{min_wed} wedstrijden op niveau {eigen_niveau}).")
    
    # Toon open klusjes indien aanwezig
    klusjes = laad_klusjes()
    mijn_klusjes = [k for k_id, k in klusjes.items() if k.get("nbb_nummer") == nbb_nummer and not k.get("afgerond", False)]
    
    if mijn_klusjes:
        st.divider()
        st.subheader("🔧 Open klusjes")
        for klusje in mijn_klusjes:
            with st.container():
                st.warning(f"""
                **{klusje['naam']}**  
                {klusje['omschrijving']}  
                *Levert {klusje['strikes_waarde']} strike(s) kwijtschelding op*
                """)
                st.caption("Meld je bij de TC als je dit klusje hebt afgerond.")
    
    # Toon inkomende vervangingsverzoeken
    verzoeken = laad_vervangingsverzoeken()
    inkomende_verzoeken = [v for v_id, v in verzoeken.items() 
                          if v.get("vervanger_nbb") == nbb_nummer 
                          and v.get("status") == "pending"]
    
    if inkomende_verzoeken:
        st.divider()
        st.subheader("📨 Vervangingsverzoeken")
        for verzoek in inkomende_verzoeken:
            wed = wedstrijden.get(verzoek["wed_id"], {})
            if not wed:
                continue
            
            wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
            dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
            aanvrager = scheidsrechters.get(verzoek["aanvrager_nbb"], {}).get("naam", "Onbekend")
            
            # Bereken potentiële punten
            punten_info = bereken_punten_voor_wedstrijd(nbb_nummer, verzoek["wed_id"], wedstrijden, scheidsrechters)
            
            with st.container():
                st.info(f"""
                **{aanvrager}** vraagt of jij kunt invallen:  
                📅 **{dag} {wed_datum.strftime('%d-%m %H:%M')}** - {wed['thuisteam']} vs {wed['uitteam']}  
                👕 {verzoek['positie']}  
                🏆 **{punten_info['totaal']} punten** ({punten_info['details']})
                
                📊 *Berekening: inschrijving om {punten_info['berekening']['inschrijf_moment_leesbaar']}, wedstrijd om {punten_info['berekening']['wedstrijd_datum_leesbaar']} = {punten_info['berekening']['uren_tot_wedstrijd']} uur van tevoren*
                """)
                
                col_accept, col_reject = st.columns(2)
                with col_accept:
                    if st.button("✅ Accepteren", key=f"accept_{verzoek['id']}", type="primary"):
                        # Herbereken punten op exact moment van acceptatie
                        punten_info_definitief = bereken_punten_voor_wedstrijd(nbb_nummer, verzoek["wed_id"], wedstrijden, scheidsrechters)
                        
                        # Verzoek accepteren
                        positie_key = "scheids_1" if verzoek["positie"] == "1e scheidsrechter" else "scheids_2"
                        wedstrijden[verzoek["wed_id"]][positie_key] = nbb_nummer
                        sla_wedstrijden_op(wedstrijden)
                        
                        # Ken punten toe met volledige berekening voor transparantie
                        voeg_punten_toe(
                            nbb_nummer, 
                            punten_info_definitief['totaal'], 
                            punten_info_definitief['details'], 
                            verzoek["wed_id"],
                            punten_info_definitief['berekening']
                        )
                        
                        # Originele aanvrager afmelden
                        if verzoek["positie"] == "1e scheidsrechter":
                            wedstrijden[verzoek["wed_id"]]["scheids_1"] = nbb_nummer
                        else:
                            wedstrijden[verzoek["wed_id"]]["scheids_2"] = nbb_nummer
                        sla_wedstrijden_op(wedstrijden)
                        
                        # Verzoek status updaten met registratie details
                        verzoeken[verzoek["id"]]["status"] = "accepted"
                        verzoeken[verzoek["id"]]["bevestigd_op"] = datetime.now().isoformat()
                        verzoeken[verzoek["id"]]["punten_berekening"] = punten_info_definitief['berekening']
                        sla_vervangingsverzoeken_op(verzoeken)
                        
                        # Toon gedetailleerde bevestiging
                        st.success(f"""
                        ✅ **Vervanging geaccepteerd!**  
                        
                        🕐 Geregistreerd: **{punten_info_definitief['berekening']['inschrijf_moment_leesbaar']}**  
                        📅 Wedstrijd: **{punten_info_definitief['berekening']['wedstrijd_datum_leesbaar']}**  
                        ⏱️ Tijd tot wedstrijd: **{punten_info_definitief['berekening']['uren_tot_wedstrijd']} uur**  
                        🏆 Punten: **{punten_info_definitief['totaal']}** ({punten_info_definitief['details']})
                        """)
                        st.rerun()
                
                with col_reject:
                    if st.button("❌ Weigeren", key=f"reject_{verzoek['id']}"):
                        verzoeken[verzoek["id"]]["status"] = "rejected"
                        sla_vervangingsverzoeken_op(verzoeken)
                        st.rerun()
    
    # Check deadline en bepaal doelmaand
    deadline = datetime.strptime(instellingen["inschrijf_deadline"], "%Y-%m-%d")
    dagen_over = (deadline - datetime.now()).days
    
    # Bepaal doelmaand (zelfde logica als bij wedstrijden filter)
    maand_namen = ["", "januari", "februari", "maart", "april", "mei", "juni", 
                   "juli", "augustus", "september", "oktober", "november", "december"]
    if deadline.day <= 15:
        info_maand = maand_namen[deadline.month]
    else:
        info_maand = maand_namen[1 if deadline.month == 12 else deadline.month + 1]
    
    if dagen_over < 0:
        st.info(f"📅 De inschrijfperiode is gesloten. Je kunt je wedstrijden hieronder bekijken.")
        kan_inschrijven = False
    else:
        st.info(f"📅 Inschrijven voor **{info_maand}** kan nog {dagen_over} dagen (tot {deadline.strftime('%d-%m-%Y')})")
        kan_inschrijven = True
    
    st.divider()
    
    # Toon huidige inschrijvingen
    st.subheader("🎯 Je hebt jezelf ingeschreven om te fluiten:")
    
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
                elif kan_inschrijven:
                    # Afmelden met expander voor opties
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
                                wedstrijden[wed["id"]][positie] = None
                                sla_wedstrijden_op(wedstrijden)
                                
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
                                vervanger_opties = {f"{k['naam']} ({k['huidig_aantal']}/{k['max_wedstrijden']} wed)": k['nbb_nummer'] for k in kandidaten}
                                
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
    
    if not kan_inschrijven:
        return
    
    st.divider()
    
    # Gecombineerd wedstrijdenoverzicht
    st.subheader("📝 Wedstrijdenoverzicht")
    
    # Bepaal welke maand getoond moet worden op basis van deadline
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
    
    maand_namen = ["", "januari", "februari", "maart", "april", "mei", "juni", 
                   "juli", "augustus", "september", "oktober", "november", "december"]
    
    # Filter optie
    toon_alle = st.toggle(f"Toon ook wedstrijden buiten {maand_namen[doel_maand]}", value=False, 
                          help=f"Standaard zie je alleen wedstrijden van {maand_namen[doel_maand]} {doel_jaar}. Zet aan om alle toekomstige wedstrijden te zien.")
    
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
        if not toon_alle:
            if wed_datum.month != doel_maand or wed_datum.year != doel_jaar:
                continue
        
        # Check of dit een eigen wedstrijd is
        is_eigen_thuis = any(team_match(wed["thuisteam"], et) for et in eigen_teams)
        is_eigen_uit = any(team_match(wed["uitteam"], et) for et in eigen_teams)
        
        if wed.get("type") == "uit":
            # Uitwedstrijd van eigen team
            if is_eigen_thuis:
                reistijd = wed.get("reistijd_minuten", 45)
                terug_tijd = wed_datum + timedelta(minutes=reistijd) + timedelta(hours=1, minutes=30) + timedelta(minutes=reistijd)
                alle_items.append({
                    "id": wed_id,
                    "type": "eigen_uit",
                    "datum": wed["datum"],
                    "wed_datum": wed_datum,
                    "thuisteam": wed["thuisteam"],
                    "uitteam": wed["uitteam"],
                    "terug_tijd": terug_tijd
                })
        else:
            # Thuiswedstrijd
            if is_eigen_thuis or is_eigen_uit:
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
                # Wedstrijd om te fluiten
                alle_items.append({
                    "id": wed_id,
                    "type": "fluiten",
                    "datum": wed["datum"],
                    "wed_datum": wed_datum,
                    **wed
                })
    
    # Sorteer chronologisch
    alle_items = sorted(alle_items, key=lambda x: x["datum"])
    
    if not alle_items:
        st.write("*Geen wedstrijden in deze periode.*")
    else:
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
            st.markdown(f"""
            <div style="background-color: {header_kleur}; color: white; padding: 0.5rem 1rem; border-radius: 0.5rem 0.5rem 0 0; margin-top: 1rem;">
                <strong>📆 {dag_naam} {wed_datum.strftime('%d-%m-%Y')}</strong>{buiten_tekst}
            </div>
            <div style="background-color: {bg_kleur}; padding: 0.5rem; border-radius: 0 0 0.5rem 0.5rem; margin-bottom: 1rem;">
            </div>
            """, unsafe_allow_html=True)
            
            # Container voor dag-inhoud
            with st.container():
                for item in dag_items:
                    item_datum = item["wed_datum"]
                    
                    if item["type"] == "eigen_uit":
                        # Eigen uitwedstrijd - opvallend blok
                        st.warning(f"🚗 **{item_datum.strftime('%H:%M')} - {item['thuisteam']}** @ {item['uitteam']}  \n*Jouw wedstrijd • Terug ±{item['terug_tijd'].strftime('%H:%M')}*")
                            
                    elif item["type"] == "eigen_thuis":
                        # Eigen thuiswedstrijd - opvallend blok
                        st.warning(f"🏠 **{item_datum.strftime('%H:%M')} - {item['thuisteam']}** vs {item['uitteam']}  \n*Jouw wedstrijd • Klaar ±{item['eind_tijd'].strftime('%H:%M')}*")
                            
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
                        
                        # Fluitwedstrijd - prominenter als op eigen niveau
                        if is_eigen_niveau:
                            # Eigen niveau: groene box met ster
                            st.markdown(f"""
                            <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 0.75rem; border-radius: 0 0.5rem 0.5rem 0; margin: 0.5rem 0;">
                                ⭐ <strong>{item_datum.strftime('%H:%M')}</strong> · {wed['thuisteam']} - {wed['uitteam']} · <strong>Niveau {wed['niveau']}</strong> <em>(jouw niveau)</em>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            # Onder eigen niveau: grijze box (minder prominent)
                            st.markdown(f"""
                            <div style="background-color: #f0f2f6; border-left: 4px solid #6c757d; padding: 0.75rem; border-radius: 0 0.5rem 0.5rem 0; margin: 0.5rem 0;">
                                🏀 <strong>{item_datum.strftime('%H:%M')}</strong> · {wed['thuisteam']} - {wed['uitteam']} · <em>Niveau {wed['niveau']}</em>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # Scheidsrechter opties
                        col_1e, col_2e = st.columns(2)
                        
                        with col_1e:
                            if status_1e["ingeschreven_zelf"]:
                                st.markdown(f"🙋 **1e scheids:** Jij")
                                if st.button("❌ Afmelden", key=f"afmeld_1e_{wed['id']}"):
                                    wedstrijden[wed["id"]]["scheids_1"] = None
                                    sla_wedstrijden_op(wedstrijden)
                                    st.rerun()
                            elif status_1e["bezet"]:
                                st.markdown(f"👤 **1e scheids:** {status_1e['naam']}")
                            elif status_1e["beschikbaar"]:
                                if huidig_aantal < max_wed:
                                    # Bereken potentiële punten als boven minimum
                                    punten_info = None
                                    if op_niveau >= min_wed:
                                        punten_info = bereken_punten_voor_wedstrijd(nbb_nummer, wed['id'], wedstrijden, scheidsrechters)
                                    
                                    button_label = "📋 1e scheids"
                                    if punten_info:
                                        button_label = f"📋 1e scheids (+{punten_info['totaal']}🏆)"
                                    
                                    if st.button(button_label, key=f"1e_{wed['id']}", type="primary" if is_eigen_niveau else "secondary"):
                                        # Herbereken punten op exact moment van inschrijving
                                        punten_definitief = bereken_punten_voor_wedstrijd(nbb_nummer, wed['id'], wedstrijden, scheidsrechters) if punten_info else None
                                        
                                        wedstrijden[wed["id"]]["scheids_1"] = nbb_nummer
                                        sla_wedstrijden_op(wedstrijden)
                                        
                                        # Ken punten toe als boven minimum, met berekening
                                        if punten_definitief:
                                            voeg_punten_toe(
                                                nbb_nummer, 
                                                punten_definitief['totaal'], 
                                                punten_definitief['details'], 
                                                wed['id'],
                                                punten_definitief['berekening']
                                            )
                                            
                                            # Toon bevestiging met details bij inval bonus
                                            if punten_definitief['inval_bonus'] > 0:
                                                st.success(f"""
                                                ✅ **Ingeschreven!**  
                                                🕐 Geregistreerd: **{punten_definitief['berekening']['inschrijf_moment_leesbaar']}**  
                                                ⏱️ {punten_definitief['berekening']['uren_tot_wedstrijd']} uur tot wedstrijd  
                                                🏆 **{punten_definitief['totaal']} punten** ({punten_definitief['details']})
                                                """)
                                        
                                        st.rerun()
                                else:
                                    st.caption("~~1e scheids~~ *(max bereikt)*")
                            else:
                                st.caption(f"~~1e scheids~~ *({status_1e['reden']})*")
                        
                        with col_2e:
                            if status_2e["ingeschreven_zelf"]:
                                st.markdown(f"🙋 **2e scheids:** Jij")
                                if st.button("❌ Afmelden", key=f"afmeld_2e_{wed['id']}"):
                                    wedstrijden[wed["id"]]["scheids_2"] = None
                                    sla_wedstrijden_op(wedstrijden)
                                    st.rerun()
                            elif status_2e["bezet"]:
                                st.markdown(f"👤 **2e scheids:** {status_2e['naam']}")
                            elif status_2e["beschikbaar"]:
                                if huidig_aantal < max_wed:
                                    # Bereken potentiële punten als boven minimum
                                    punten_info = None
                                    if op_niveau >= min_wed:
                                        punten_info = bereken_punten_voor_wedstrijd(nbb_nummer, wed['id'], wedstrijden, scheidsrechters)
                                    
                                    button_label = "📋 2e scheids"
                                    if punten_info:
                                        button_label = f"📋 2e scheids (+{punten_info['totaal']}🏆)"
                                    
                                    if st.button(button_label, key=f"2e_{wed['id']}", type="primary" if is_eigen_niveau else "secondary"):
                                        # Herbereken punten op exact moment van inschrijving
                                        punten_definitief = bereken_punten_voor_wedstrijd(nbb_nummer, wed['id'], wedstrijden, scheidsrechters) if punten_info else None
                                        
                                        wedstrijden[wed["id"]]["scheids_2"] = nbb_nummer
                                        sla_wedstrijden_op(wedstrijden)
                                        
                                        # Ken punten toe als boven minimum, met berekening
                                        if punten_definitief:
                                            voeg_punten_toe(
                                                nbb_nummer, 
                                                punten_definitief['totaal'], 
                                                punten_definitief['details'], 
                                                wed['id'],
                                                punten_definitief['berekening']
                                            )
                                            
                                            # Toon bevestiging met details bij inval bonus
                                            if punten_definitief['inval_bonus'] > 0:
                                                st.success(f"""
                                                ✅ **Ingeschreven!**  
                                                🕐 Geregistreerd: **{punten_definitief['berekening']['inschrijf_moment_leesbaar']}**  
                                                ⏱️ {punten_definitief['berekening']['uren_tot_wedstrijd']} uur tot wedstrijd  
                                                🏆 **{punten_definitief['totaal']} punten** ({punten_definitief['details']})
                                                """)
                                        
                                        st.rerun()
                                else:
                                    st.caption("~~2e scheids~~ *(max bereikt)*")
                            else:
                                st.caption(f"~~2e scheids~~ *({status_2e['reden']})*")

# ============================================================
# BEHEERDER VIEW
# ============================================================

def toon_beheerder_view():
    """Toon het beheerderspaneel."""
    # Header met logo
    logo_path = Path(__file__).parent / "logo.png"
    if logo_path.exists():
        col_logo, col_title = st.columns([1, 4])
        with col_logo:
            st.image(str(logo_path), width=100)
        with col_title:
            st.title("Beheerder - Scheidsrechter Planning")
    else:
        st.title("🔧 Beheerder - Scheidsrechter Planning")
    
    # Statistieken berekenen
    wedstrijden = laad_wedstrijden()
    nu = datetime.now()
    
    thuis_nog_te_spelen = 0
    niet_compleet = 0
    
    for wed_id, wed in wedstrijden.items():
        # Alleen thuiswedstrijden
        if wed.get("type", "thuis") != "thuis":
            continue
        
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        
        # Nog te spelen?
        if wed_datum > nu:
            thuis_nog_te_spelen += 1
            
            # Niet compleet? (mist 1e of 2e scheids)
            if not wed.get("scheids_1") or not wed.get("scheids_2"):
                niet_compleet += 1
    
    # Toon statistieken
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Thuiswedstrijden te spelen", thuis_nog_te_spelen)
    with col2:
        st.metric("Nog in te vullen", niet_compleet)
    with col3:
        if thuis_nog_te_spelen > 0:
            percentage = round((thuis_nog_te_spelen - niet_compleet) / thuis_nog_te_spelen * 100)
            st.metric("Compleet", f"{percentage}%")
        else:
            st.metric("Compleet", "-")
    
    st.divider()
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📅 Wedstrijden", 
        "👥 Scheidsrechters", 
        "🏆 Beloningen",
        "🖼️ Weekend Overzicht",
        "⚙️ Instellingen",
        "📊 Import/Export"
    ])
    
    with tab1:
        toon_wedstrijden_beheer()
    
    with tab2:
        toon_scheidsrechters_beheer()
    
    with tab3:
        toon_beloningen_beheer()
    
    with tab4:
        toon_weekend_overzicht()
    
    with tab5:
        toon_instellingen_beheer()
    
    with tab6:
        toon_import_export()

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
    weekend_opties = {v["label"]: v["dagen"] for k, v in weekend_lijst}
    
    # Weekend selectie
    st.markdown("**Selecteer weekend**")
    gekozen_weekend = st.selectbox("Kies een weekend", list(weekend_opties.keys()))
    gekozen_dagen = sorted(weekend_opties[gekozen_weekend])
    
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


def toon_bewerk_formulier(wed: dict, wedstrijden: dict, scheidsrechters: dict):
    """Toon het bewerk formulier voor een wedstrijd."""
    st.markdown("---")
    st.markdown("**📝 Wedstrijd bewerken**")
    
    wed_data = wedstrijden[wed["id"]]
    huidige_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    
    with st.form(f"bewerk_form_{wed['id']}"):
        col_d, col_t, col_v = st.columns(3)
        
        with col_d:
            nieuwe_datum = st.date_input(
                "Datum", 
                value=huidige_datum.date(),
                key=f"edit_datum_{wed['id']}"
            )
        
        with col_t:
            nieuwe_tijd = st.time_input(
                "Tijd",
                value=huidige_datum.time(),
                key=f"edit_tijd_{wed['id']}"
            )
        
        with col_v:
            huidig_veld = wed_data.get("veld", "")
            nieuw_veld = st.text_input(
                "Veld",
                value=huidig_veld,
                key=f"edit_veld_{wed['id']}",
                placeholder="bijv. 1, 2, 3..."
            )
        
        col_niveau, col_bs2 = st.columns(2)
        with col_niveau:
            nieuw_niveau = st.selectbox(
                "Niveau",
                options=[1, 2, 3, 4, 5],
                index=wed_data.get("niveau", 1) - 1,
                key=f"edit_niveau_{wed['id']}"
            )
        with col_bs2:
            nieuw_bs2 = st.checkbox(
                "Vereist BS2",
                value=wed_data.get("vereist_bs2", False),
                key=f"edit_bs2_{wed['id']}"
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
                            if st.button("🗑️", key=f"delwed_{wed['id']}", help="Verwijder wedstrijd"):
                                del wedstrijden[wed["id"]]
                                sla_wedstrijden_op(wedstrijden)
                                st.rerun()
                    
                    # Bewerk formulier voor geannuleerde wedstrijd
                    if st.session_state.get(f"bewerk_{wed['id']}", False):
                        toon_bewerk_formulier(wed, wedstrijden, scheidsrechters)
                else:
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        st.write("**1e Scheidsrechter:**")
                        if wed["scheids_1_naam"]:
                            st.write(f"✓ {wed['scheids_1_naam']}")
                            if st.button("Verwijderen", key=f"del1_{wed['id']}"):
                                wedstrijden[wed["id"]]["scheids_1"] = None
                                sla_wedstrijden_op(wedstrijden)
                                st.rerun()
                        else:
                            kandidaten = get_kandidaten_voor_wedstrijd(wed["id"], als_eerste=True)
                            if kandidaten:
                                keuzes = ["-- Selecteer --"] + [
                                    f"{k['naam']} ({k['huidig_aantal']}/{k['max_wedstrijden']})" + 
                                    (f" ⚠️ nog {k['tekort']} nodig" if k['tekort'] > 0 else "")
                                    for k in kandidaten
                                ]
                                selectie = st.selectbox("Kies 1e scheids", keuzes, key=f"sel1_{wed['id']}")
                                if selectie != "-- Selecteer --":
                                    idx = keuzes.index(selectie) - 1
                                    if st.button("Toewijzen", key=f"assign1_{wed['id']}"):
                                        wedstrijden[wed["id"]]["scheids_1"] = kandidaten[idx]["nbb_nummer"]
                                        sla_wedstrijden_op(wedstrijden)
                                        st.rerun()
                            else:
                                st.warning("Geen geschikte kandidaten")
                    
                    with col2:
                        st.write("**2e Scheidsrechter:**")
                        if wed["scheids_2_naam"]:
                            st.write(f"✓ {wed['scheids_2_naam']}")
                            if st.button("Verwijderen", key=f"del2_{wed['id']}"):
                                wedstrijden[wed["id"]]["scheids_2"] = None
                                sla_wedstrijden_op(wedstrijden)
                                st.rerun()
                        else:
                            kandidaten = get_kandidaten_voor_wedstrijd(wed["id"], als_eerste=False)
                            if kandidaten:
                                keuzes = ["-- Selecteer --"] + [
                                    f"{k['naam']} ({k['huidig_aantal']}/{k['max_wedstrijden']})" +
                                    (f" ⚠️ nog {k['tekort']} nodig" if k['tekort'] > 0 else "")
                                    for k in kandidaten
                                ]
                                selectie = st.selectbox("Kies 2e scheids", keuzes, key=f"sel2_{wed['id']}")
                                if selectie != "-- Selecteer --":
                                    idx = keuzes.index(selectie) - 1
                                    if st.button("Toewijzen", key=f"assign2_{wed['id']}"):
                                        wedstrijden[wed["id"]]["scheids_2"] = kandidaten[idx]["nbb_nummer"]
                                        sla_wedstrijden_op(wedstrijden)
                                        st.rerun()
                            else:
                                st.warning("Geen geschikte kandidaten")
                    
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
                            if st.button("🗑️", key=f"delwed_{wed['id']}", help="Verwijder wedstrijd"):
                                del wedstrijden[wed["id"]]
                                sla_wedstrijden_op(wedstrijden)
                                st.rerun()
                
                # Bewerk formulier (buiten de columns, volledige breedte)
                if st.session_state.get(f"bewerk_{wed['id']}", False):
                    toon_bewerk_formulier(wed, wedstrijden, scheidsrechters)
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
                        if st.button("🗑️", key=f"delwed_{wed['id']}", help="Verwijder wedstrijd"):
                            del wedstrijden[wed["id"]]
                            sla_wedstrijden_op(wedstrijden)
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
        totaal_max = 0
        for nbb, scheids in scheidsrechters.items():
            niveau = scheids.get("niveau_1e_scheids", 1)
            scheids_per_niveau[niveau] = scheids_per_niveau.get(niveau, 0) + 1
            totaal_min += scheids.get("min_wedstrijden", 0)
            totaal_max += scheids.get("max_wedstrijden", 0)
        
        st.write("**Scheidsrechters per niveau (1e scheids):**")
        cols = st.columns(6)
        for i, niveau in enumerate([1, 2, 3, 4, 5]):
            count = scheids_per_niveau.get(niveau, 0)
            cols[i].metric(f"Niveau {niveau}", count)
        cols[5].metric("Totaal", len(scheidsrechters))
        
        st.caption(f"Totale capaciteit: {totaal_min} - {totaal_max} wedstrijden | {len(scheidsrechters)} scheidsrechters")
        st.divider()
    
    # Legenda
    if deadline_verstreken:
        st.caption("✅ Voldoet aan minimum op eigen niveau | ⚠️ Nog niet genoeg wedstrijden op eigen niveau")
    else:
        st.caption("✅ Voldoet aan minimum op eigen niveau | ⏳ Inschrijving loopt nog")
    
    st.info("ℹ️ Het minimum aantal wedstrijden moet op het **eigen niveau** gefluiten worden. Wedstrijden op een lager niveau tellen niet mee voor het minimum.")
    
    # Statistieken
    for nbb, scheids in sorted(scheidsrechters.items(), key=lambda x: x[1]["naam"]):
        niveau_stats = tel_wedstrijden_op_eigen_niveau(nbb)
        huidig = niveau_stats["totaal"]
        op_niveau = niveau_stats["op_niveau"]
        eigen_niveau = niveau_stats["niveau"]
        min_wed = scheids.get("min_wedstrijden", 0)
        max_wed = scheids.get("max_wedstrijden", 99)
        
        # Status bepalen op basis van wedstrijden op eigen niveau
        if op_niveau >= min_wed:
            status = "✅"  # Voldoet aan minimum
        elif deadline_verstreken:
            status = "⚠️"  # Deadline verstreken en nog niet genoeg
        else:
            status = "⏳"  # Nog niet genoeg, maar deadline nog niet verstreken
        
        label = f"{status} {scheids['naam']} - {op_niveau}/{min_wed} op niv.{eigen_niveau} (totaal: {huidig})"
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
                        bs2_diploma = st.checkbox("BS2 diploma", value=bool(scheids.get("bs2_diploma", False)), key=f"bs2_{nbb}")
                        niet_op_zondag = st.checkbox("Niet op zondag", value=bool(scheids.get("niet_op_zondag", False)), key=f"zondag_{nbb}")
                    with col2:
                        # Zorg voor geldige index (0-4)
                        idx_1e = max(0, min(4, scheids.get("niveau_1e_scheids", 1) - 1))
                        idx_2e = max(0, min(4, scheids.get("niveau_2e_scheids", 5) - 1))
                        
                        niveau_1e = st.selectbox("1e scheids t/m niveau", [1, 2, 3, 4, 5], 
                                                  index=idx_1e, key=f"niv1_{nbb}")
                        niveau_2e = st.selectbox("2e scheids t/m niveau", [1, 2, 3, 4, 5], 
                                                  index=idx_2e, key=f"niv2_{nbb}")
                        min_w = st.number_input("Minimum wedstrijden", min_value=0, 
                                                value=int(scheids.get("min_wedstrijden", 2) or 2), key=f"min_{nbb}")
                        max_w = st.number_input("Maximum wedstrijden", min_value=1, 
                                                value=int(scheids.get("max_wedstrijden", 5) or 5), key=f"max_{nbb}")
                    
                    eigen_teams = st.multiselect(
                        "Eigen teams", 
                        options=SCHEIDSRECHTER_TEAMS,
                        default=[t for t in scheids.get("eigen_teams", []) if t in SCHEIDSRECHTER_TEAMS],
                        key=f"teams_{nbb}"
                    )
                    
                    col_save, col_delete = st.columns(2)
                    with col_save:
                        if st.form_submit_button("💾 Opslaan"):
                            scheidsrechters[nbb] = {
                                "naam": nieuwe_naam,
                                "bs2_diploma": bs2_diploma,
                                "niet_op_zondag": niet_op_zondag,
                                "niveau_1e_scheids": niveau_1e,
                                "niveau_2e_scheids": niveau_2e,
                                "min_wedstrijden": min_w,
                                "max_wedstrijden": max_w,
                                "eigen_teams": eigen_teams
                            }
                            sla_scheidsrechters_op(scheidsrechters)
                            st.session_state[edit_key] = False
                            st.success("Scheidsrechter bijgewerkt!")
                            st.rerun()
                    with col_delete:
                        if st.form_submit_button("🗑️ Verwijderen", type="secondary"):
                            del scheidsrechters[nbb]
                            sla_scheidsrechters_op(scheidsrechters)
                            st.session_state[edit_key] = False
                            st.success("Scheidsrechter verwijderd!")
                            st.rerun()
            else:
                # Weergave modus
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**NBB-nummer:** {nbb}")
                    st.write(f"**BS2 diploma:** {'Ja' if scheids.get('bs2_diploma') else 'Nee'}")
                    st.write(f"**Niet op zondag:** {'Ja' if scheids.get('niet_op_zondag') else 'Nee'}")
                
                with col2:
                    st.write(f"**1e scheids t/m niveau:** {scheids.get('niveau_1e_scheids', '-')}")
                    st.write(f"**2e scheids t/m niveau:** {scheids.get('niveau_2e_scheids', '-')}")
                    st.write(f"**Eigen teams:** {', '.join(scheids.get('eigen_teams', [])) or '-'}")
                
                # Link voor inschrijving
                st.code(f"?nbb={nbb}")
    
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
            niveau_2e = st.selectbox("2e scheids t/m niveau", [1, 2, 3, 4, 5], index=4)
            min_wed = st.number_input("Minimum wedstrijden", min_value=0, value=2)
            max_wed = st.number_input("Maximum wedstrijden", min_value=1, value=5)
        
        eigen_teams = st.multiselect("Eigen teams", options=SCHEIDSRECHTER_TEAMS)
        
        if st.form_submit_button("Toevoegen"):
            if nbb_nummer and naam:
                scheidsrechters[nbb_nummer] = {
                    "naam": naam,
                    "bs2_diploma": bs2_diploma,
                    "niet_op_zondag": niet_op_zondag,
                    "niveau_1e_scheids": niveau_1e,
                    "niveau_2e_scheids": niveau_2e,
                    "min_wedstrijden": min_wed,
                    "max_wedstrijden": max_wed,
                    "eigen_teams": eigen_teams
                }
                sla_scheidsrechters_op(scheidsrechters)
                st.success("Scheidsrechter toegevoegd!")
                st.rerun()
            else:
                st.error("NBB-nummer en naam zijn verplicht")

def toon_beloningen_beheer():
    """Beheer beloningen: ranglijst, strikes, klusjes."""
    scheidsrechters = laad_scheidsrechters()
    beloningen = laad_beloningen()
    klusjes = laad_klusjes()
    verzoeken = laad_vervangingsverzoeken()
    
    st.subheader("🏆 Beloningen & Strikes Beheer")
    
    subtab1, subtab2, subtab3, subtab4, subtab5 = st.tabs([
        "📊 Ranglijst", 
        "⚠️ Strikes Toekennen", 
        "🔧 Klusjes Toewijzen",
        "📋 Klusjes Instellingen",
        "🔄 Vervangingsverzoeken"
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
                    
                    if speler_details["gefloten_wedstrijden"]:
                        st.write("**Puntenhistorie:**")
                        wedstrijden_data = laad_wedstrijden()
                        for wed_reg in reversed(speler_details["gefloten_wedstrijden"][-10:]):  # Laatste 10
                            wed = wedstrijden_data.get(wed_reg.get("wed_id", ""), {})
                            wed_naam = f"{wed.get('thuisteam', '?')} vs {wed.get('uitteam', '?')}" if wed else "Onbekende wedstrijd"
                            
                            berekening = wed_reg.get("berekening", {})
                            if berekening:
                                st.markdown(f"""
                                - **+{wed_reg['punten']}** - {wed_naam}  
                                  *Geregistreerd: {berekening.get('inschrijf_moment_leesbaar', '?')} | {berekening.get('uren_tot_wedstrijd', '?')} uur tot wedstrijd*
                                """)
                            else:
                                st.markdown(f"- **+{wed_reg['punten']}** - {wed_naam} ({wed_reg.get('reden', '')})")
                    else:
                        st.caption("Nog geen wedstrijden geregistreerd.")
                    
                    if speler_details["strike_log"]:
                        st.write("**Strike historie:**")
                        for strike in reversed(speler_details["strike_log"][-5:]):  # Laatste 5
                            teken = "+" if strike["strikes"] > 0 else ""
                            st.markdown(f"- **{teken}{strike['strikes']}** - {strike['reden']}")
            
            # Clinic drempel info
            st.divider()
            clinic_kandidaten = [s for s in ranglijst if s["punten"] >= 15]
            if clinic_kandidaten:
                st.success(f"**{len(clinic_kandidaten)} speler(s)** hebben 15+ punten en kunnen een voucher Clinic claimen!")
                for k in clinic_kandidaten:
                    st.write(f"  • {k['naam']} ({k['punten']} punten)")
    
    with subtab2:
        st.write("**Strikes toekennen**")
        st.caption("Gebruik dit voor no-shows of late afmeldingen die niet via de app zijn gegaan.")
        
        # Selecteer speler
        speler_opties = {f"{s['naam']} (NBB: {nbb})": nbb for nbb, s in scheidsrechters.items()}
        
        if speler_opties:
            geselecteerde_speler = st.selectbox("Selecteer speler", options=list(speler_opties.keys()))
            geselecteerde_nbb = speler_opties[geselecteerde_speler]
            
            # Toon huidige status
            stats = get_speler_stats(geselecteerde_nbb)
            st.info(f"Huidige status: {stats['punten']} punten, {stats['strikes']} strikes")
            
            col1, col2 = st.columns(2)
            
            with col1:
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
                
                opmerking = st.text_input("Opmerking (optioneel)")
                
                if st.button("⚠️ Strike toekennen", type="primary"):
                    reden_tekst = f"{strike_reden}"
                    if opmerking:
                        reden_tekst += f" - {opmerking}"
                    voeg_strike_toe(geselecteerde_nbb, strike_aantal, reden_tekst)
                    st.success(f"{strike_aantal} strike(s) toegekend!")
                    st.rerun()
            
            with col2:
                st.write("**Strike verwijderen**")
                st.caption("Voor correcties of na het voltooien van een klusje buiten de app om.")
                
                verwijder_aantal = st.number_input("Aantal strikes verwijderen", min_value=1, max_value=10, value=1)
                verwijder_reden = st.text_input("Reden voor verwijdering")
                
                if st.button("✅ Strike verwijderen"):
                    if verwijder_reden:
                        verwijder_strike(geselecteerde_nbb, verwijder_aantal, verwijder_reden)
                        st.success(f"{verwijder_aantal} strike(s) verwijderd!")
                        st.rerun()
                    else:
                        st.error("Vul een reden in")
    
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
                                # Bereken strikes
                                uren_tot_wed = (wed_datum - datetime.fromisoformat(verzoek["aangemaakt_op"])).total_seconds() / 3600
                                if uren_tot_wed < 24:
                                    strikes = 2
                                elif uren_tot_wed < 48:
                                    strikes = 1
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

def toon_instellingen_beheer():
    """Beheer instellingen."""
    instellingen = laad_instellingen()
    
    st.subheader("Instellingen")
    
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
    # Niveau 5: M18-1, M20-1, MSE
    
    niveau_1 = ["X10-1", "X10-2", "X12-2", "V12-2"]
    niveau_2 = ["X12-1", "V12-1", "X14-2", "M16-2"]
    niveau_3 = ["X14-1", "M16-1", "V16-2"]
    niveau_4 = ["V16-1", "M18-2", "M18-3"]
    niveau_5 = ["M18-1", "M20-1", "MSE"]
    
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


def toon_import_export():
    """Import/export functionaliteit."""
    st.subheader("Import / Export")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📥 NBB Wedstrijden", "📥 NBB Scheidsrechters", "📥 CSV Scheidsrechters", "📥 CSV Wedstrijden", "📤 Export"])
    
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
        st.write("**Import scheidsrechters (CSV)**")
        st.write("Verwacht formaat:")
        st.code("nbb_nummer,naam,bs2_diploma,niveau_1e,niveau_2e,min,max,niet_zondag,eigen_teams")
        
        uploaded_scheids = st.file_uploader("Upload CSV", type="csv", key="import_scheids")
        if uploaded_scheids:
            import csv
            import io
            
            content = uploaded_scheids.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(content))
            
            scheidsrechters = laad_scheidsrechters()
            count = 0
            
            for row in reader:
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
            st.success(f"{count} scheidsrechters geïmporteerd!")
    
    with tab4:
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
            
            wedstrijden = laad_wedstrijden()
            count = 0
            
            for row in reader:
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
            st.success(f"{count} wedstrijden geïmporteerd!")
    
    with tab5:
        st.write("**Export planning (CSV)**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Download thuiswedstrijden + planning"):
                wedstrijden = laad_wedstrijden()
                scheidsrechters = laad_scheidsrechters()
                
                output = "datum,tijd,thuisteam,uitteam,niveau,scheids_1,scheids_2\n"
                for wed_id, wed in sorted(wedstrijden.items(), key=lambda x: x[1]["datum"]):
                    if wed.get("type", "thuis") != "thuis":
                        continue
                    datum_obj = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                    scheids_1_naam = scheidsrechters.get(wed.get("scheids_1", ""), {}).get("naam", "")
                    scheids_2_naam = scheidsrechters.get(wed.get("scheids_2", ""), {}).get("naam", "")
                    
                    output += f"{datum_obj.strftime('%Y-%m-%d')},{datum_obj.strftime('%H:%M')},"
                    output += f"{wed['thuisteam']},{wed['uitteam']},{wed['niveau']},"
                    output += f"{scheids_1_naam},{scheids_2_naam}\n"
                
                st.download_button(
                    "📥 Download CSV",
                    output,
                    file_name="scheidsrechter_planning.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("📥 Download alle wedstrijden"):
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
                    mime="text/csv"
                )

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
        toon_speler_view(nbb_nummer)
        return
    
    # Route: /beheer
    if "beheer" in query_params:
        # Simpele wachtwoord check via session state
        if "beheerder_ingelogd" not in st.session_state:
            st.session_state.beheerder_ingelogd = False
        
        if not st.session_state.beheerder_ingelogd:
            st.title("🔐 Beheerder Login")
            wachtwoord = st.text_input("Wachtwoord", type="password")
            if st.button("Inloggen"):
                if wachtwoord == BEHEERDER_WACHTWOORD:
                    st.session_state.beheerder_ingelogd = True
                    st.rerun()
                else:
                    st.error("Onjuist wachtwoord")
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
