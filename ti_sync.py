"""
Teamindeling Synchronisatie Module

Koppeling met de Teamindeling app database (Supabase) voor het ophalen van
U16 spelers ten behoeve van tafel officials inplanning.

Versie: 1.0.0
"""

import streamlit as st
from supabase import create_client, Client


def _get_ti_client() -> Client | None:
    """
    Maak verbinding met de Teamindeling Supabase database.
    
    Returns:
        Client | None: Supabase client of None bij fout
    """
    try:
        url = st.secrets["TI_SUPABASE_URL"]
        key = st.secrets["TI_SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError:
        return None


def is_ti_connected() -> bool:
    """Check of de Teamindeling database bereikbaar is."""
    client = _get_ti_client()
    if client is None:
        return False
    try:
        client.table('leden').select('id', count='exact').limit(1).execute()
        return True
    except Exception:
        return False


def get_u16_spelers(seizoen: str = "2025-2026") -> list[dict]:
    """
    Haal alle U16 spelers op uit de Teamindeling database.
    
    Bron: tabel 'leden', gefilterd op team LIKE '%16%'.
    
    Args:
        seizoen: Seizoen string (voor toekomstig gebruik bij seizoensfilter)
    
    Returns:
        Lijst van dicts met spelergegevens:
        [{"voornaam": str, "tussenvoegsel": str, "achternaam": str, 
          "naam": str, "team": str, "nbb_nummer": str}]
    """
    client = _get_ti_client()
    if client is None:
        return []
    
    try:
        response = client.table('leden').select(
            'voornaam, tussenvoegsel, achternaam, team, nbb_nummer'
        ).like('team', '%16%').execute()
        
        spelers = []
        for lid in response.data:
            # Stel volledige naam samen
            delen = [lid.get("voornaam", "")]
            if lid.get("tussenvoegsel"):
                delen.append(lid["tussenvoegsel"])
            delen.append(lid.get("achternaam", ""))
            volledige_naam = " ".join(delen).strip()
            
            spelers.append({
                "voornaam": lid.get("voornaam", ""),
                "tussenvoegsel": lid.get("tussenvoegsel", ""),
                "achternaam": lid.get("achternaam", ""),
                "naam": volledige_naam,
                "team": lid.get("team", ""),
                "nbb_nummer": lid.get("nbb_nummer", "")
            })
        
        # Sorteer op team, dan achternaam
        spelers.sort(key=lambda s: (s["team"], s["achternaam"]))
        return spelers
    
    except Exception as e:
        st.error(f"❌ Fout bij ophalen U16 spelers: {e}")
        return []


def get_u16_teams() -> list[str]:
    """
    Haal alle U16 teamnamen op uit de Teamindeling database.
    
    Returns:
        Gesorteerde lijst van teamnamen, bijv. ["M16-1", "M16-2", "V16-1", "V16-2"]
    """
    client = _get_ti_client()
    if client is None:
        return []
    
    try:
        response = client.table('teams').select(
            'naam'
        ).eq('categorie', 'U16').eq('seizoen', '2025-2026').execute()
        
        teams = sorted([t["naam"] for t in response.data])
        return teams
    
    except Exception as e:
        st.error(f"❌ Fout bij ophalen U16 teams: {e}")
        return []


def get_spelers_per_team(spelers: list[dict]) -> dict[str, list[dict]]:
    """
    Groepeer spelers per team.
    
    Args:
        spelers: Lijst van speler-dicts (uit get_u16_spelers)
    
    Returns:
        Dict met team als key en lijst van spelers als value
        {"M16-1": [{"naam": "...", ...}, ...]}
    """
    per_team = {}
    for speler in spelers:
        team = speler.get("team", "Onbekend")
        if team not in per_team:
            per_team[team] = []
        per_team[team].append(speler)
    return per_team
