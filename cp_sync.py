"""
cp_sync.py - Koppeling BOB ↔ Competitie Planner

Synchroniseert wedstrijden vanuit de Competitie Planner database naar BOB,
zodat scheidsrechters zich kunnen inschrijven op thuiswedstrijden.

Versie: 1.32.17
Datum: 2026-01-27
"""

from supabase import create_client, Client
import streamlit as st
from datetime import datetime, date, time
from typing import Optional

# Module versie (synchroon met app.py)
CP_SYNC_VERSIE = "1.32.17"


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
    Haal alle Waterdragers wedstrijden op uit Competitie Planner (thuis én uit).
    
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
        # Haal thuiswedstrijden op
        query_thuis = client.table('matches').select('*').eq('seizoen', seizoen)
        if seizoenshelft:
            query_thuis = query_thuis.eq('seizoenshelft', seizoenshelft)
        query_thuis = query_thuis.ilike('home_team_name', 'Waterdragers%')
        query_thuis = query_thuis.not_.is_('scheduled_date', 'null')
        query_thuis = query_thuis.not_.is_('scheduled_time', 'null')
        
        response_thuis = query_thuis.order('scheduled_date').order('scheduled_time').execute()
        thuis_wedstrijden = response_thuis.data or []
        
        # Haal uitwedstrijden op
        query_uit = client.table('matches').select('*').eq('seizoen', seizoen)
        if seizoenshelft:
            query_uit = query_uit.eq('seizoenshelft', seizoenshelft)
        query_uit = query_uit.ilike('away_team_name', 'Waterdragers%')
        query_uit = query_uit.not_.is_('scheduled_date', 'null')
        query_uit = query_uit.not_.is_('scheduled_time', 'null')
        
        response_uit = query_uit.order('scheduled_date').order('scheduled_time').execute()
        uit_wedstrijden = response_uit.data or []
        
        # Combineer en sorteer
        alle_wedstrijden = thuis_wedstrijden + uit_wedstrijden
        alle_wedstrijden.sort(key=lambda x: (x.get('scheduled_date', ''), x.get('scheduled_time', '')))
        
        return alle_wedstrijden
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
    
    BELANGRIJK: BOB slaat ALLE wedstrijden op met Waterdragers in het 'thuisteam' veld,
    ongeacht of het een thuis- of uitwedstrijd is. Het 'type' veld bepaalt of het 
    thuis ('thuis') of uit ('uit') is.
    
    Args:
        cp_wedstrijd: Wedstrijd dict uit Competitie Planner
    
    Returns:
        Wedstrijd dict in BOB-formaat
    """
    home_team = cp_wedstrijd.get('home_team_name', '')
    away_team = cp_wedstrijd.get('away_team_name', '')
    
    # Bepaal of het een thuis- of uitwedstrijd is
    is_thuiswedstrijd = home_team.lower().startswith('waterdragers')
    
    # BOB formaat: Waterdragers altijd in 'thuisteam' veld
    if is_thuiswedstrijd:
        bob_thuisteam = home_team
        bob_uitteam = away_team
    else:
        # Uitwedstrijd: wissel de teams om voor BOB
        bob_thuisteam = away_team  # Waterdragers
        bob_uitteam = home_team    # Tegenstander
    
    # Bepaal het eigen team (Waterdragers team) voor niveau bepaling
    eigen_team = home_team if is_thuiswedstrijd else away_team
    eigen_team_code = extract_team_code(eigen_team)
    
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
    
    # Veld nummer naar string (alleen relevant voor thuiswedstrijden)
    veld = cp_wedstrijd.get('field_number')
    veld_str = str(veld) if veld else None
    
    return {
        'nbb_wedstrijd_nr': cp_wedstrijd.get('nbb_id'),
        'datum': datum.strftime('%Y-%m-%d %H:%M') if datum else None,  # Spatie formaat zoals BOB
        'thuisteam': bob_thuisteam,  # In BOB altijd Waterdragers
        'uitteam': bob_uitteam,       # In BOB altijd tegenstander
        'eigen_team_code': eigen_team_code,  # Voor weergave
        'niveau': bepaal_niveau(eigen_team_code),
        'vereist_bs2': bepaal_bs2_vereist(eigen_team_code),
        'veld': veld_str,
        'type': 'thuis' if is_thuiswedstrijd else 'uit',
        # Extra velden voor weergave/debugging
        '_cp_id': cp_wedstrijd.get('id'),
        '_cp_poule': cp_wedstrijd.get('poule'),
        '_cp_competitie': cp_wedstrijd.get('competitie'),
        '_cp_accommodatie': cp_wedstrijd.get('accommodatie'),
        '_is_thuiswedstrijd': is_thuiswedstrijd,
    }


# =============================================================================
# SYNC LOGICA
# =============================================================================

def vergelijk_wedstrijden(cp_wedstrijden: list[dict], bob_wedstrijden: list[dict]) -> dict:
    """
    Vergelijk wedstrijden tussen CP en BOB.
    
    Let op: BOB slaat ALLE wedstrijden op met Waterdragers in het 'thuisteam' veld,
    ook uitwedstrijden. Het 'type' veld bepaalt of het thuis of uit is.
    
    Matching strategie:
    1. Eerst op nbb_wedstrijd_nr (meest betrouwbaar)
    2. Fallback op datum/tijd + genormaliseerde teams
    
    Returns:
        Dict met categorieën: nieuw, gewijzigd, ongewijzigd, verwijderd
    """
    resultaat = {
        'nieuw': [],
        'gewijzigd': [],
        'ongewijzigd': [],
        'verwijderd': [],
    }
    
    # Maak lookup dicts voor BOB wedstrijden
    bob_lookup_nbb = {}  # op nbb_wedstrijd_nr
    bob_lookup_key = {}  # op datum + teams (fallback)
    
    def normaliseer_teams(team1: str, team2: str) -> tuple[str, str]:
        """
        Normaliseer teams zodat Waterdragers altijd eerst staat.
        Verwijdert ook sterretjes (*) die in BOB worden gebruikt voor markering.
        """
        # Verwijder sterretjes en normaliseer
        t1 = str(team1).strip().lower().replace('*', '')
        t2 = str(team2).strip().lower().replace('*', '')
        
        # Waterdragers altijd eerst
        if t1.startswith('waterdragers'):
            return (t1, t2)
        elif t2.startswith('waterdragers'):
            return (t2, t1)
        else:
            # Geen Waterdragers gevonden, sorteer alfabetisch
            return (t1, t2) if t1 < t2 else (t2, t1)
    
    def maak_match_key(datum_str: str, team1: str, team2: str) -> str:
        """Maak een unieke sleutel voor matching op datum/teams."""
        # Normaliseer datum (alleen datum + tijd, zonder timezone)
        # Verwijder T separator en neem eerste 16 karakters
        datum_norm = datum_str.replace('T', ' ')[:16] if datum_str else ''
        # Normaliseer teams (Waterdragers altijd eerst)
        t1_norm, t2_norm = normaliseer_teams(team1, team2)
        return f"{datum_norm}|{t1_norm}|{t2_norm}"
    
    for wed in bob_wedstrijden:
        nbb_nr = wed.get('nbb_wedstrijd_nr')
        if nbb_nr:
            bob_lookup_nbb[nbb_nr] = wed
        
        # Key-based lookup met genormaliseerde teams
        key = maak_match_key(
            wed.get('datum', ''),
            wed.get('thuisteam', ''),
            wed.get('uitteam', '')
        )
        bob_lookup_key[key] = wed
    
    # Track welke BOB wedstrijden we gezien hebben
    gezien_bob_ids = set()
    
    # Loop door CP wedstrijden
    for cp_wed in cp_wedstrijden:
        bob_format = map_cp_naar_bob(cp_wed)
        nbb_nr = bob_format['nbb_wedstrijd_nr']
        
        # Probeer eerst te matchen op nbb_wedstrijd_nr
        bob_wed = None
        if nbb_nr and nbb_nr in bob_lookup_nbb:
            bob_wed = bob_lookup_nbb[nbb_nr]
        
        # Fallback: match op datum + genormaliseerde teams
        if not bob_wed:
            # Gebruik originele CP teamnamen voor key
            cp_key = maak_match_key(
                bob_format.get('datum', ''),
                cp_wed.get('home_team_name', ''),
                cp_wed.get('away_team_name', '')
            )
            if cp_key in bob_lookup_key:
                bob_wed = bob_lookup_key[cp_key]
        
        if bob_wed:
            # Gevonden in BOB
            wed_id = bob_wed.get('wed_id')
            if wed_id:
                gezien_bob_ids.add(wed_id)
            
            # Check op wijzigingen
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
        else:
            # Nieuwe wedstrijd
            resultaat['nieuw'].append({
                'cp': cp_wed,
                'bob_format': bob_format,
            })
    
    # Check voor verwijderde wedstrijden (in BOB maar niet meer in CP)
    for wed in bob_wedstrijden:
        wed_id = wed.get('wed_id')
        if wed_id and wed_id not in gezien_bob_ids:
            resultaat['verwijderd'].append({
                'bob': wed,
            })
    
    # ==========================================================================
    # EXTRA PASS: Detecteer verplaatste wedstrijden
    # ==========================================================================
    # Als een wedstrijd in "nieuw" dezelfde teams heeft als een wedstrijd in "verwijderd",
    # dan is het waarschijnlijk een verplaatste wedstrijd (datum gewijzigd).
    # Verplaats deze naar "gewijzigd" met de datum als wijziging.
    
    def maak_team_key(team1: str, team2: str) -> str:
        """Maak een key op basis van alleen teams (zonder datum)."""
        t1, t2 = normaliseer_teams(team1, team2)
        return f"{t1}|{t2}"
    
    def is_incomplete_bob_record(bob: dict) -> bool:
        """Check of een BOB record lege/ontbrekende teamnamen heeft."""
        thuisteam = bob.get('thuisteam', '').strip()
        uitteam = bob.get('uitteam', '').strip()
        return not thuisteam or not uitteam
    
    # ==========================================================================
    # PASS 1: Match incomplete BOB records (lege teamnamen) op datum
    # ==========================================================================
    # Dit zijn corrupte records die we kunnen repareren door de teamnamen uit CP te halen
    
    # Bouw lookup voor incomplete verwijderde wedstrijden op datum
    incomplete_lookup = {}
    for item in resultaat['verwijderd']:
        bob = item['bob']
        if is_incomplete_bob_record(bob):
            bob_datum = bob.get('datum', '')[:16].replace('T', ' ') if bob.get('datum') else ''
            if bob_datum:
                incomplete_lookup[bob_datum] = item
    
    nieuwe_te_verwijderen = []
    verwijderde_te_verwijderen = []
    
    # Match nieuwe CP wedstrijden met incomplete BOB records op datum
    for i, nieuw_item in enumerate(resultaat['nieuw']):
        bob_fmt = nieuw_item['bob_format']
        cp_datum = bob_fmt.get('datum', '')[:16] if bob_fmt.get('datum') else ''
        
        if cp_datum in incomplete_lookup:
            # Gevonden! Dit is een incomplete BOB record die we kunnen aanvullen
            verwijderd_item = incomplete_lookup.pop(cp_datum)
            bob_wed = verwijderd_item['bob']
            
            # Maak wijzigingen lijst - vul teamnamen aan
            wijzigingen = []
            
            # Toon datum als bevestiging (niet als wijziging, maar ter info)
            bob_datum = bob_wed.get('datum', '')[:16].replace('T', ' ') if bob_wed.get('datum') else ''
            try:
                from datetime import datetime
                dt = datetime.strptime(bob_datum, '%Y-%m-%d %H:%M')
                datum_display = dt.strftime('%d-%m-%Y %H:%M')
            except:
                datum_display = bob_datum
            
            wijzigingen.append({
                'veld': '_datum_info',  # Underscore = niet updaten, alleen tonen
                'label': 'Datum',
                'cp_waarde': datum_display,
                'bob_waarde': datum_display,
                '_info_only': True,  # Markeer als info-only
            })
            
            # Thuisteam toevoegen
            if not bob_wed.get('thuisteam', '').strip():
                wijzigingen.append({
                    'veld': 'thuisteam',
                    'label': 'Thuisteam',
                    'cp_waarde': bob_fmt.get('thuisteam', ''),
                    'bob_waarde': '(leeg)',
                })
            
            # Uitteam toevoegen
            if not bob_wed.get('uitteam', '').strip():
                wijzigingen.append({
                    'veld': 'uitteam',
                    'label': 'Uitteam',
                    'cp_waarde': bob_fmt.get('uitteam', ''),
                    'bob_waarde': '(leeg)',
                })
            
            # Type toevoegen als die ontbreekt
            if not bob_wed.get('type'):
                wijzigingen.append({
                    'veld': 'type',
                    'label': 'Type',
                    'cp_waarde': bob_fmt.get('type', 'thuis'),
                    'bob_waarde': '(leeg)',
                })
            
            # Niveau toevoegen als die ontbreekt
            if not bob_wed.get('niveau'):
                wijzigingen.append({
                    'veld': 'niveau',
                    'label': 'Niveau',
                    'cp_waarde': bob_fmt.get('niveau', 1),
                    'bob_waarde': '(leeg)',
                })
            
            # Voeg toe aan gewijzigd met speciale markering
            resultaat['gewijzigd'].append({
                'cp': nieuw_item['cp'],
                'bob': bob_wed,
                'bob_format': bob_fmt,
                'wijzigingen': wijzigingen,
                '_incomplete': True,  # Markeer als incomplete record reparatie
            })
            
            nieuwe_te_verwijderen.append(i)
            verwijderde_te_verwijderen.append(verwijderd_item)
    
    # Verwijder gematche items
    for i in sorted(nieuwe_te_verwijderen, reverse=True):
        resultaat['nieuw'].pop(i)
    
    for item in verwijderde_te_verwijderen:
        if item in resultaat['verwijderd']:
            resultaat['verwijderd'].remove(item)
    
    # ==========================================================================
    # PASS 2: Match complete BOB records op teams (verplaatste wedstrijden)
    # ==========================================================================
    
    # Bouw lookup voor complete verwijderde wedstrijden op teams
    verwijderd_lookup = {}
    for item in resultaat['verwijderd']:
        bob = item['bob']
        if not is_incomplete_bob_record(bob):  # Alleen complete records
            team_key = maak_team_key(bob.get('thuisteam', ''), bob.get('uitteam', ''))
            if team_key not in verwijderd_lookup:
                verwijderd_lookup[team_key] = []
            verwijderd_lookup[team_key].append(item)
    
    nieuwe_te_verwijderen = []
    verwijderde_te_verwijderen = []
    
    # Check nieuwe wedstrijden tegen verwijderde op teams
    for i, nieuw_item in enumerate(resultaat['nieuw']):
        bob_fmt = nieuw_item['bob_format']
        team_key = maak_team_key(bob_fmt.get('thuisteam', ''), bob_fmt.get('uitteam', ''))
        
        if team_key in verwijderd_lookup and verwijderd_lookup[team_key]:
            # Gevonden! Dit is waarschijnlijk een verplaatste wedstrijd
            verwijderd_item = verwijderd_lookup[team_key].pop(0)  # Neem eerste match
            bob_wed = verwijderd_item['bob']
            
            # Maak wijzigingen lijst (vooral datum)
            wijzigingen = []
            
            # Datum wijziging
            cp_datum = bob_fmt.get('datum', '')[:16] if bob_fmt.get('datum') else ''
            bob_datum = bob_wed.get('datum', '')[:16] if bob_wed.get('datum') else ''
            if cp_datum != bob_datum:
                # Format voor weergave
                try:
                    from datetime import datetime
                    cp_dt = datetime.strptime(cp_datum, '%Y-%m-%d %H:%M')
                    bob_dt = datetime.strptime(bob_datum.replace('T', ' ')[:16], '%Y-%m-%d %H:%M')
                    wijzigingen.append({
                        'veld': 'datum',
                        'label': 'Datum/tijd',
                        'cp_waarde': cp_dt.strftime('%d-%m-%Y %H:%M'),
                        'bob_waarde': bob_dt.strftime('%d-%m-%Y %H:%M'),
                    })
                except:
                    wijzigingen.append({
                        'veld': 'datum',
                        'label': 'Datum/tijd',
                        'cp_waarde': cp_datum,
                        'bob_waarde': bob_datum,
                    })
            
            # Veld wijziging (alleen als CP een waarde heeft)
            cp_veld = bob_fmt.get('veld')
            bob_veld = bob_wed.get('veld')
            if cp_veld and str(cp_veld) != str(bob_veld or ''):
                wijzigingen.append({
                    'veld': 'veld',
                    'label': 'Veld',
                    'cp_waarde': cp_veld,
                    'bob_waarde': bob_veld,
                })
            
            # Voeg toe aan gewijzigd
            resultaat['gewijzigd'].append({
                'cp': nieuw_item['cp'],
                'bob': bob_wed,
                'bob_format': bob_fmt,
                'wijzigingen': wijzigingen,
                '_verplaatst': True,  # Markeer als verplaatste wedstrijd
            })
            
            nieuwe_te_verwijderen.append(i)
            verwijderde_te_verwijderen.append(verwijderd_item)
    
    # Verwijder de gematche items uit nieuw en verwijderd (in omgekeerde volgorde)
    for i in sorted(nieuwe_te_verwijderen, reverse=True):
        resultaat['nieuw'].pop(i)
    
    for item in verwijderde_te_verwijderen:
        if item in resultaat['verwijderd']:
            resultaat['verwijderd'].remove(item)
    
    return resultaat


def detecteer_wijzigingen(cp_bob_format: dict, bob_wed: dict) -> list[dict]:
    """
    Detecteer wijzigingen tussen CP en BOB versie van een wedstrijd.
    
    Returns:
        Lijst met wijzigingen, elk met 'veld', 'cp_waarde', 'bob_waarde'
    
    Let op: 
    - 'niveau' wordt NIET vergeleken (alleen in BOB beheerd)
    - 'thuisteam'/'uitteam' worden NIET vergeleken (matching is al op teams gebaseerd)
    - Lege CP veld waarden overschrijven BOB niet (uitwedstrijden hebben geen veld)
    """
    wijzigingen = []
    
    # Velden om te vergelijken
    # NB: niveau en teams staan hier NIET bij
    velden = [
        ('datum', 'Datum/tijd', True),   # altijd vergelijken
        ('veld', 'Veld', False),          # alleen als CP waarde heeft
    ]
    
    for veld, label, altijd_vergelijken in velden:
        cp_waarde = cp_bob_format.get(veld)
        bob_waarde = bob_wed.get(veld)
        
        # Skip als CP waarde leeg is en dit veld niet altijd vergeleken hoeft te worden
        if not altijd_vergelijken and not cp_waarde:
            continue
        
        # Speciale vergelijking voor datum (string vs datetime)
        if veld == 'datum':
            if cp_waarde and bob_waarde:
                # Normaliseer naar vergelijkbaar formaat
                try:
                    def parse_datum(val):
                        """Parse datum string naar datetime, ongeacht formaat."""
                        if isinstance(val, datetime):
                            return val
                        if isinstance(val, str):
                            # Normaliseer: vervang T door spatie, verwijder timezone
                            val_clean = val.replace('T', ' ').replace('Z', '').split('+')[0]
                            # Probeer verschillende formaten
                            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                                try:
                                    return datetime.strptime(val_clean[:len(fmt.replace('%', ''))], fmt)
                                except:
                                    continue
                        return None
                    
                    bob_dt = parse_datum(bob_waarde)
                    cp_dt = parse_datum(cp_waarde)
                    
                    if bob_dt and cp_dt and bob_dt != cp_dt:
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
