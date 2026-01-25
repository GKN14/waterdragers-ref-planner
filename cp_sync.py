"""
cp_sync.py - Koppeling BOB ↔ Competitie Planner

Synchroniseert wedstrijden vanuit de Competitie Planner database naar BOB,
zodat scheidsrechters zich kunnen inschrijven op thuiswedstrijden.
"""

from supabase import create_client, Client
import streamlit as st
from datetime import datetime, date, time
from typing import Optional


# =============================================================================
# DATABASE CONNECTIE
# =============================================================================

def get_cp_client() -> Optional[Client]:
    """Maak verbinding met Competitie Planner database."""
    try:
        url = st.secrets["CP_SUPABASE_URL"]
        key = st.secrets["CP_SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError:
        return None


def is_cp_connected() -> bool:
    """Check of CP database bereikbaar is."""
    client = get_cp_client()
    if not client:
        return False
    try:
        client.table('matches').select('id', count='exact').limit(1).execute()
        return True
    except:
        return False


# =============================================================================
# DATA OPHALEN UIT COMPETITIE PLANNER
# =============================================================================

def get_beschikbare_seizoenen() -> list[str]:
    """Haal beschikbare seizoenen op uit Competitie Planner."""
    client = get_cp_client()
    if not client:
        return []
    
    try:
        response = client.table('matches').select('seizoen').execute()
        seizoenen = list(set(r['seizoen'] for r in response.data if r.get('seizoen')))
        return sorted(seizoenen, reverse=True)
    except Exception as e:
        st.error(f"Fout bij ophalen seizoenen: {e}")
        return []


def get_beschikbare_seizoenshelften(seizoen: str) -> list[str]:
    """Haal beschikbare seizoenshelften op voor een seizoen."""
    client = get_cp_client()
    if not client:
        return []
    
    try:
        response = client.table('matches').select('seizoenshelft').eq('seizoen', seizoen).execute()
        helften = list(set(r['seizoenshelft'] for r in response.data if r.get('seizoenshelft')))
        # Sorteer logisch: 1e helft voor 2e helft
        return sorted(helften)
    except Exception as e:
        st.error(f"Fout bij ophalen seizoenshelften: {e}")
        return []


def get_wedstrijden_van_cp(seizoen: str, seizoenshelft: Optional[str] = None) -> list[dict]:
    """
    Haal wedstrijden op uit Competitie Planner.
    
    Args:
        seizoen: Bijv. "2025-2026"
        seizoenshelft: Optioneel, "1e helft" of "2e helft"
    
    Returns:
        Lijst met wedstrijden uit CP
    """
    client = get_cp_client()
    if not client:
        return []
    
    try:
        query = client.table('matches').select('*').eq('seizoen', seizoen)
        
        if seizoenshelft:
            query = query.eq('seizoenshelft', seizoenshelft)
        
        # Alleen wedstrijden met geplande datum/tijd
        query = query.not_.is_('scheduled_date', 'null')
        query = query.not_.is_('scheduled_time', 'null')
        
        response = query.order('scheduled_date').order('scheduled_time').execute()
        return response.data or []
    except Exception as e:
        st.error(f"Fout bij ophalen CP wedstrijden: {e}")
        return []


# =============================================================================
# MAPPING FUNCTIES
# =============================================================================

def extract_team_code(home_team_name: str) -> str:
    """
    Extract teamcode uit volledige naam.
    "Waterdragers - V16-2" → "V16-2"
    "Waterdragers - MSE-1" → "MSE-1"
    """
    if " - " in home_team_name:
        return home_team_name.split(" - ")[-1]
    return home_team_name


def bepaal_niveau(team_code: str) -> int:
    """
    Bepaal het niveau op basis van de teamcode.
    
    Niveau-indeling:
    1 = U10, U12 (X10, X12, V10, V12, M10, M12)
    2 = U14, U16 recreatie
    3 = U16 hogere divisie, U18
    4 = Senioren lager, U20/U22
    5 = Senioren hoger, MSE
    """
    team_upper = team_code.upper()
    
    # MSE is altijd niveau 5
    if 'MSE' in team_upper:
        return 5
    
    # Extract categorie (X10, V16, M18, etc.)
    categorie = ''.join(c for c in team_upper if c.isalpha() or c.isdigit())
    
    # Niveau bepalen op basis van leeftijdscategorie
    if any(x in categorie for x in ['X10', 'X12', 'V10', 'V12', 'M10', 'M12', 'U10', 'U12']):
        return 1
    elif any(x in categorie for x in ['X14', 'V14', 'M14', 'U14']):
        return 2
    elif any(x in categorie for x in ['X16', 'V16', 'M16', 'U16']):
        return 2  # Kan 2 of 3 zijn, default 2
    elif any(x in categorie for x in ['X18', 'V18', 'M18', 'U18']):
        return 3
    elif any(x in categorie for x in ['M20', 'M22', 'V20', 'V22', 'U20', 'U22']):
        return 4
    else:
        # Senioren of onbekend
        return 4
    

def bepaal_bs2_vereist(team_code: str) -> bool:
    """Bepaal of BS2 vereist is (alleen voor MSE wedstrijden)."""
    return 'MSE' in team_code.upper()


def map_cp_naar_bob(cp_wedstrijd: dict) -> dict:
    """
    Map een wedstrijd van CP-formaat naar BOB-formaat.
    
    Args:
        cp_wedstrijd: Wedstrijd dict uit Competitie Planner
    
    Returns:
        Wedstrijd dict in BOB-formaat
    """
    # Extract team code
    thuisteam = extract_team_code(cp_wedstrijd.get('home_team_name', ''))
    
    # Combineer datum en tijd
    datum_str = cp_wedstrijd.get('scheduled_date', '')
    tijd_str = cp_wedstrijd.get('scheduled_time', '00:00:00')
    
    # Parse naar datetime
    try:
        if datum_str:
            datum = datetime.strptime(f"{datum_str} {tijd_str}", "%Y-%m-%d %H:%M:%S")
        else:
            datum = None
    except ValueError:
        try:
            # Probeer alternatief formaat
            datum = datetime.strptime(f"{datum_str} {tijd_str}", "%Y-%m-%d %H:%M")
        except:
            datum = None
    
    # Veld nummer naar string
    veld = cp_wedstrijd.get('field_number')
    veld_str = str(veld) if veld else None
    
    return {
        'nbb_wedstrijd_nr': cp_wedstrijd.get('nbb_id'),
        'datum': datum.isoformat() if datum else None,
        'thuisteam': thuisteam,
        'uitteam': cp_wedstrijd.get('away_team_name', ''),
        'niveau': bepaal_niveau(thuisteam),
        'vereist_bs2': bepaal_bs2_vereist(thuisteam),
        'veld': veld_str,
        'type': 'thuis',
        # Extra velden voor weergave/debugging
        '_cp_id': cp_wedstrijd.get('id'),
        '_cp_poule': cp_wedstrijd.get('poule'),
        '_cp_competitie': cp_wedstrijd.get('competitie'),
        '_cp_accommodatie': cp_wedstrijd.get('accommodatie'),
    }


# =============================================================================
# SYNC LOGICA
# =============================================================================

def vergelijk_wedstrijden(cp_wedstrijden: list[dict], bob_wedstrijden: list[dict]) -> dict:
    """
    Vergelijk wedstrijden tussen CP en BOB.
    
    Returns:
        Dict met categorieën: nieuw, gewijzigd, ongewijzigd, verwijderd
    """
    resultaat = {
        'nieuw': [],
        'gewijzigd': [],
        'ongewijzigd': [],
        'verwijderd': [],
    }
    
    # Maak lookup dict voor BOB wedstrijden op nbb_wedstrijd_nr
    bob_lookup = {}
    bob_zonder_nbb = []
    
    for wed in bob_wedstrijden:
        nbb_nr = wed.get('nbb_wedstrijd_nr')
        if nbb_nr:
            bob_lookup[nbb_nr] = wed
        else:
            bob_zonder_nbb.append(wed)
    
    # Track welke BOB wedstrijden we gezien hebben
    gezien_nbb_nrs = set()
    
    # Loop door CP wedstrijden
    for cp_wed in cp_wedstrijden:
        bob_format = map_cp_naar_bob(cp_wed)
        nbb_nr = bob_format['nbb_wedstrijd_nr']
        
        if not nbb_nr:
            continue
        
        gezien_nbb_nrs.add(nbb_nr)
        
        if nbb_nr not in bob_lookup:
            # Nieuwe wedstrijd
            resultaat['nieuw'].append({
                'cp': cp_wed,
                'bob_format': bob_format,
            })
        else:
            # Bestaande wedstrijd - check op wijzigingen
            bob_wed = bob_lookup[nbb_nr]
            wijzigingen = detecteer_wijzigingen(bob_format, bob_wed)
            
            if wijzigingen:
                resultaat['gewijzigd'].append({
                    'cp': cp_wed,
                    'bob': bob_wed,
                    'bob_format': bob_format,
                    'wijzigingen': wijzigingen,
                })
            else:
                resultaat['ongewijzigd'].append({
                    'cp': cp_wed,
                    'bob': bob_wed,
                })
    
    # Check voor verwijderde wedstrijden (in BOB maar niet meer in CP)
    for nbb_nr, bob_wed in bob_lookup.items():
        if nbb_nr not in gezien_nbb_nrs:
            resultaat['verwijderd'].append({
                'bob': bob_wed,
            })
    
    return resultaat


def detecteer_wijzigingen(cp_bob_format: dict, bob_wed: dict) -> list[dict]:
    """
    Detecteer wijzigingen tussen CP en BOB versie van een wedstrijd.
    
    Returns:
        Lijst met wijzigingen, elk met 'veld', 'cp_waarde', 'bob_waarde'
    """
    wijzigingen = []
    
    # Velden om te vergelijken
    velden = [
        ('datum', 'Datum/tijd'),
        ('uitteam', 'Uitteam'),
        ('veld', 'Veld'),
        ('niveau', 'Niveau'),
    ]
    
    for veld, label in velden:
        cp_waarde = cp_bob_format.get(veld)
        bob_waarde = bob_wed.get(veld)
        
        # Speciale vergelijking voor datum (string vs datetime)
        if veld == 'datum':
            if cp_waarde and bob_waarde:
                # Normaliseer naar vergelijkbaar formaat
                try:
                    if isinstance(bob_waarde, str):
                        # Parse BOB datum
                        bob_dt = datetime.fromisoformat(bob_waarde.replace('Z', '+00:00'))
                    else:
                        bob_dt = bob_waarde
                    
                    cp_dt = datetime.fromisoformat(cp_waarde) if isinstance(cp_waarde, str) else cp_waarde
                    
                    # Vergelijk zonder timezone info voor eenvoud
                    if cp_dt.replace(tzinfo=None) != bob_dt.replace(tzinfo=None):
                        wijzigingen.append({
                            'veld': veld,
                            'label': label,
                            'cp_waarde': cp_dt.strftime('%d-%m-%Y %H:%M'),
                            'bob_waarde': bob_dt.strftime('%d-%m-%Y %H:%M'),
                        })
                except:
                    pass
        else:
            # Normale vergelijking
            if str(cp_waarde or '') != str(bob_waarde or ''):
                wijzigingen.append({
                    'veld': veld,
                    'label': label,
                    'cp_waarde': cp_waarde,
                    'bob_waarde': bob_waarde,
                })
    
    return wijzigingen


# =============================================================================
# SYNC ACTIES
# =============================================================================

def voeg_wedstrijd_toe(bob_format: dict, db) -> bool:
    """
    Voeg een nieuwe wedstrijd toe aan BOB.
    
    Args:
        bob_format: Wedstrijd in BOB-formaat
        db: Database module referentie
    
    Returns:
        True als succesvol
    """
    try:
        # Verwijder interne CP velden
        wedstrijd_data = {k: v for k, v in bob_format.items() if not k.startswith('_')}
        
        # Genereer wed_id als die er niet is
        if 'wed_id' not in wedstrijd_data or not wedstrijd_data['wed_id']:
            # Gebruik nbb_wedstrijd_nr als basis voor wed_id
            wedstrijd_data['wed_id'] = f"cp_{bob_format.get('nbb_wedstrijd_nr', datetime.now().timestamp())}"
        
        # Voeg toe via database module
        db.voeg_wedstrijd_toe(wedstrijd_data)
        return True
    except Exception as e:
        st.error(f"Fout bij toevoegen wedstrijd: {e}")
        return False


def update_wedstrijd(wed_id: str, wijzigingen: dict, db) -> bool:
    """
    Update een bestaande wedstrijd in BOB.
    
    Args:
        wed_id: ID van de wedstrijd in BOB
        wijzigingen: Dict met veld -> nieuwe waarde
        db: Database module referentie
    
    Returns:
        True als succesvol
    """
    try:
        db.update_wedstrijd(wed_id, wijzigingen)
        return True
    except Exception as e:
        st.error(f"Fout bij updaten wedstrijd: {e}")
        return False


def markeer_als_geannuleerd(wed_id: str, db) -> bool:
    """
    Markeer een wedstrijd als geannuleerd (niet verwijderen).
    
    Args:
        wed_id: ID van de wedstrijd in BOB
        db: Database module referentie
    
    Returns:
        True als succesvol
    """
    try:
        db.update_wedstrijd(wed_id, {'geannuleerd': True})
        return True
    except Exception as e:
        st.error(f"Fout bij annuleren wedstrijd: {e}")
        return False
