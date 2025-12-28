"""
Database module voor Supabase connectie
Ref Planner - BV Waterdragers

Inclusief:
- Admin authenticatie (wachtwoord in database)
- Device verificatie (geboortedatum check)
- Geofiltering (alleen Nederland)
"""

import os
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import json
import hashlib
import secrets
import requests
import re

# Cookie manager voor device tokens
try:
    import extra_streamlit_components as stx
    _cookie_manager = stx.CookieManager(key="device_cookie_manager")
except ImportError:
    _cookie_manager = None

# Supabase configuratie - ALLEEN via secrets (geen hardcoded values meer)
def get_supabase_config():
    """Haal Supabase configuratie op uit secrets"""
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
        if url and key:
            return url, key
    except Exception as e:
        st.error(f"Supabase configuratie niet gevonden in secrets: {e}")
    
    # Fallback naar environment variables (voor lokaal development)
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return url, key
    
    st.error("SUPABASE_URL en SUPABASE_KEY moeten geconfigureerd zijn in Streamlit Secrets")
    st.stop()

SUPABASE_URL, SUPABASE_KEY = get_supabase_config()

@st.cache_resource
def get_supabase_client() -> Client:
    """Maak een Supabase client (cached)"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# GEOFILTERING
# ============================================================

@st.cache_data(ttl=3600)
def _get_country_from_ip(ip: str) -> str:
    """Haal land op via IP adres (cached voor 1 uur)"""
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=2)
        return response.json().get("countryCode", "NL")
    except:
        return "NL"  # Bij fout: toegang geven

def check_geo_access() -> bool:
    """
    Check of gebruiker uit Nederland komt.
    Stopt de app als toegang geweigerd wordt.
    """
    try:
        ip = st.context.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    except:
        ip = ""
    
    if not ip:
        return True  # Geen IP = lokaal development
    
    country = _get_country_from_ip(ip)
    
    if country != "NL":
        st.error("🚫 Deze app is alleen toegankelijk vanuit Nederland.")
        st.stop()
        return False
    
    return True

# ============================================================
# ADMIN AUTHENTICATIE
# ============================================================

def _hash_password(password: str) -> str:
    """Hash een wachtwoord met SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_stored_admin_password_hash() -> str | None:
    """Haal opgeslagen admin wachtwoord hash op uit database"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("admin_settings").select("value").eq("key", "password_hash").execute()
        if response.data:
            return response.data[0]["value"]
        return None
    except Exception as e:
        return None

def save_admin_password_hash(password: str) -> bool:
    """Sla nieuwe admin wachtwoord hash op in database"""
    try:
        supabase = get_supabase_client()
        password_hash = _hash_password(password)
        record = {
            "key": "password_hash",
            "value": password_hash,
            "updated_at": datetime.now().isoformat()
        }
        supabase.table("admin_settings").upsert(record).execute()
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan wachtwoord: {e}")
        return False

def verify_admin_password(input_password: str) -> bool:
    """Verifieer admin wachtwoord tegen database of default"""
    stored_hash = get_stored_admin_password_hash()
    
    # Check of force reset actief is
    force_reset = st.secrets.get("FORCE_RESET", False)
    if force_reset:
        default_password = st.secrets.get("ADMIN_PASSWORD", "")
        return input_password == default_password
    
    # Geen hash in database = eerste keer, gebruik default
    if stored_hash is None:
        default_password = st.secrets.get("ADMIN_PASSWORD", "")
        return input_password == default_password
    
    # Vergelijk met opgeslagen hash
    return _hash_password(input_password) == stored_hash

def needs_password_change() -> bool:
    """Check of wachtwoord gewijzigd moet worden (eerste login of force reset)"""
    force_reset = st.secrets.get("FORCE_RESET", False)
    if force_reset:
        return True
    
    stored_hash = get_stored_admin_password_hash()
    return stored_hash is None

def get_default_admin_password() -> str:
    """Haal default admin wachtwoord op uit secrets"""
    return st.secrets.get("ADMIN_PASSWORD", "")

# ============================================================
# DEVICE VERIFICATIE
# ============================================================

def _generate_device_token() -> str:
    """Genereer een unieke device token"""
    return secrets.token_urlsafe(32)

def get_device_token_from_cookie(nbb_nummer: str) -> str | None:
    """Haal device token op uit cookie"""
    if _cookie_manager is None:
        # Fallback naar session state
        return st.session_state.get(f"device_token_{nbb_nummer}")
    
    try:
        token = _cookie_manager.get(f"device_token_{nbb_nummer}")
        return token
    except:
        return None

def save_device_token_to_cookie(nbb_nummer: str, token: str) -> bool:
    """Sla device token op in cookie (90 dagen geldig)"""
    if _cookie_manager is None:
        # Fallback naar session state
        st.session_state[f"device_token_{nbb_nummer}"] = token
        return True
    
    try:
        _cookie_manager.set(f"device_token_{nbb_nummer}", token, max_age=90*24*60*60)
        return True
    except:
        # Fallback naar session state
        st.session_state[f"device_token_{nbb_nummer}"] = token
        return True

def clear_device_token_cookie(nbb_nummer: str) -> bool:
    """Verwijder device token uit cookie"""
    # Clear session state
    session_key = f"device_token_{nbb_nummer}"
    if session_key in st.session_state:
        del st.session_state[session_key]
    
    if _cookie_manager is None:
        return True
    
    try:
        _cookie_manager.delete(f"device_token_{nbb_nummer}")
        return True
    except:
        return True

def token_exists_in_database(speler_id: str, token: str) -> bool:
    """Check of een token bestaat in de database (ongeacht approved status)"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("device_tokens").select("id").eq("speler_id", speler_id).eq("token", token).execute()
        return bool(response.data)
    except:
        return False

def get_device_count(speler_id: str) -> int:
    """Tel aantal gekoppelde devices voor speler"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("device_tokens").select("id", count="exact").eq("speler_id", speler_id).execute()
        return response.count or 0
    except:
        return 0

def get_devices(speler_id: str) -> list:
    """Haal alle devices op voor een speler"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("device_tokens").select("*").eq("speler_id", speler_id).order("created_at", desc=True).execute()
        return response.data or []
    except:
        return []

def remove_device(device_id: int, speler_id: str) -> bool:
    """Verwijder een device"""
    try:
        supabase = get_supabase_client()
        supabase.table("device_tokens").delete().eq("id", device_id).eq("speler_id", speler_id).execute()
        return True
    except:
        return False

def remove_device_admin(device_id: int) -> bool:
    """Verwijder een device (beheerder - geen speler_id check)"""
    try:
        supabase = get_supabase_client()
        supabase.table("device_tokens").delete().eq("id", device_id).execute()
        return True
    except:
        return False

def get_all_devices() -> list:
    """Haal alle devices op (voor beheerder)"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("device_tokens").select("*").order("created_at", desc=True).execute()
        return response.data or []
    except:
        return []

def get_device_stats() -> dict:
    """Haal device statistieken op (voor beheerder)"""
    try:
        supabase = get_supabase_client()
        
        # Alle devices
        all_devices = supabase.table("device_tokens").select("speler_id", count="exact").execute()
        total_devices = all_devices.count or 0
        
        # Unieke spelers met devices
        devices_data = supabase.table("device_tokens").select("speler_id").execute()
        unique_spelers = len(set(d["speler_id"] for d in devices_data.data)) if devices_data.data else 0
        
        # Spelers met geboortedatum (kunnen verifiëren)
        spelers_met_geb = supabase.table("scheidsrechters").select("nbb_nummer").neq("geboortedatum", None).execute()
        spelers_met_geboortedatum = len(spelers_met_geb.data) if spelers_met_geb.data else 0
        
        # Pending approvals
        pending = supabase.table("device_tokens").select("id", count="exact").eq("approved", False).execute()
        pending_approvals = pending.count or 0
        
        return {
            "total_devices": total_devices,
            "unique_spelers": unique_spelers,
            "spelers_met_geboortedatum": spelers_met_geboortedatum,
            "pending_approvals": pending_approvals
        }
    except:
        return {"total_devices": 0, "unique_spelers": 0, "spelers_met_geboortedatum": 0, "pending_approvals": 0}

# ============================================================
# SPELER DEVICE INSTELLINGEN
# ============================================================

def get_speler_device_settings(speler_id: str) -> dict:
    """Haal device instellingen op voor een speler"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("speler_settings").select("*").eq("speler_id", speler_id).execute()
        if response.data:
            return {
                "max_devices": response.data[0].get("max_devices"),
                "require_approval": response.data[0].get("require_approval", False)
            }
        return {"max_devices": None, "require_approval": False}
    except:
        return {"max_devices": None, "require_approval": False}

def save_speler_device_settings(speler_id: str, max_devices: int | None, require_approval: bool) -> bool:
    """Sla device instellingen op voor een speler"""
    try:
        supabase = get_supabase_client()
        record = {
            "speler_id": speler_id,
            "max_devices": max_devices,
            "require_approval": require_approval,
            "updated_at": datetime.now().isoformat()
        }
        supabase.table("speler_settings").upsert(record).execute()
        return True
    except:
        return False

def get_pending_devices(speler_id: str) -> list:
    """Haal apparaten op die wachten op goedkeuring"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("device_tokens").select("*").eq("speler_id", speler_id).eq("approved", False).order("created_at", desc=True).execute()
        return response.data or []
    except:
        return []

def approve_device(device_id: int, speler_id: str) -> bool:
    """Keur een apparaat goed"""
    try:
        supabase = get_supabase_client()
        supabase.table("device_tokens").update({"approved": True}).eq("id", device_id).eq("speler_id", speler_id).execute()
        return True
    except:
        return False

def reject_device(device_id: int, speler_id: str) -> bool:
    """Weiger een apparaat (verwijder het)"""
    return remove_device(device_id, speler_id)

def can_add_device(speler_id: str) -> tuple[bool, str]:
    """Check of speler een nieuw apparaat kan toevoegen. Returns (allowed, reason)"""
    settings = get_speler_device_settings(speler_id)
    current_count = get_device_count(speler_id)
    
    max_devices = settings.get("max_devices")
    if max_devices and current_count >= max_devices:
        return False, f"Maximum aantal apparaten ({max_devices}) bereikt"
    
    return True, ""

def needs_approval(speler_id: str) -> bool:
    """Check of nieuw apparaat goedkeuring nodig heeft"""
    settings = get_speler_device_settings(speler_id)
    if not settings.get("require_approval", False):
        return False
    
    # Eerste apparaat heeft nooit goedkeuring nodig
    current_count = get_device_count(speler_id)
    return current_count > 0

def register_device_with_approval(speler_id: str, token: str, device_name: str = None) -> tuple[bool, bool]:
    """
    Registreer device met mogelijke goedkeuring.
    Returns: (success, needs_approval)
    """
    try:
        supabase = get_supabase_client()
        
        # Check of we kunnen toevoegen
        can_add, reason = can_add_device(speler_id)
        if not can_add:
            st.error(reason)
            return False, False
        
        # Bepaal of goedkeuring nodig is
        requires_approval = needs_approval(speler_id)
        
        if not device_name:
            try:
                user_agent = st.context.headers.get("User-Agent", "")
                if "Mobile" in user_agent or "Android" in user_agent or "iPhone" in user_agent:
                    device_name = "Mobiel"
                elif "Tablet" in user_agent or "iPad" in user_agent:
                    device_name = "Tablet"
                else:
                    device_name = "Computer"
            except:
                device_name = "Apparaat"
            
            count = get_device_count(speler_id)
            device_name = f"{device_name} {count + 1}"
        
        record = {
            "speler_id": speler_id,
            "token": token,
            "device_name": device_name,
            "approved": not requires_approval,
            "last_used": datetime.now().isoformat()
        }
        supabase.table("device_tokens").insert(record).execute()
        return True, requires_approval
    except Exception as e:
        st.error(f"Fout bij registreren device: {e}")
        return False, False

def format_datetime(dt_string: str) -> str:
    """Format datetime string naar leesbaar formaat met tijd"""
    if not dt_string:
        return "?"
    try:
        # Parse ISO format
        dt = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
        return dt.strftime("%d-%m-%Y %H:%M")
    except:
        return dt_string[:16] if len(dt_string) >= 16 else dt_string

def verify_device_token(speler_id: str, token: str) -> bool:
    """Check of device token geldig en goedgekeurd is voor speler"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("device_tokens").select("id, approved").eq("speler_id", speler_id).eq("token", token).execute()
        
        if response.data:
            device = response.data[0]
            # Check of apparaat goedgekeurd is
            if not device.get("approved", True):
                return False
            # Update last_used
            supabase.table("device_tokens").update({"last_used": datetime.now().isoformat()}).eq("id", device["id"]).execute()
            return True
        return False
    except:
        return False

def is_device_pending(speler_id: str, token: str) -> bool:
    """Check of device wacht op goedkeuring"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("device_tokens").select("approved").eq("speler_id", speler_id).eq("token", token).execute()
        if response.data:
            return not response.data[0].get("approved", True)
        return False
    except:
        return False

def register_device(speler_id: str, token: str, device_name: str = None) -> bool:
    """Registreer een nieuw device"""
    try:
        supabase = get_supabase_client()
        
        if not device_name:
            try:
                user_agent = st.context.headers.get("User-Agent", "")
                if "Mobile" in user_agent or "Android" in user_agent or "iPhone" in user_agent:
                    device_name = "Mobiel"
                elif "Tablet" in user_agent or "iPad" in user_agent:
                    device_name = "Tablet"
                else:
                    device_name = "Computer"
            except:
                device_name = "Apparaat"
            
            count = get_device_count(speler_id)
            device_name = f"{device_name} {count + 1}"
        
        record = {
            "speler_id": speler_id,
            "token": token,
            "device_name": device_name,
            "approved": True,
            "last_used": datetime.now().isoformat()
        }
        supabase.table("device_tokens").insert(record).execute()
        return True
    except Exception as e:
        st.error(f"Fout bij registreren device: {e}")
        return False

def get_speler_geboortedatum(nbb_nummer: str) -> str | None:
    """Haal geboortedatum op voor een speler"""
    try:
        supabase = get_supabase_client()
        response = supabase.table("scheidsrechters").select("geboortedatum").eq("nbb_nummer", nbb_nummer).execute()
        if response.data and response.data[0].get("geboortedatum"):
            return response.data[0]["geboortedatum"]
        return None
    except:
        return None

def verify_geboortedatum(nbb_nummer: str, dag: int, maand: int, jaar: int) -> bool:
    """Verifieer geboortedatum voor een speler"""
    stored_date = get_speler_geboortedatum(nbb_nummer)
    if not stored_date:
        return False
    
    # Format ingevoerde datum
    try:
        ingevoerde_datum = f"{jaar:04d}-{maand:02d}-{dag:02d}"
    except:
        return False
    
    # Vergelijk (stored_date kan YYYY-MM-DD of datetime string zijn)
    stored_date_str = str(stored_date)[:10]
    return ingevoerde_datum == stored_date_str

# ============================================================
# IMPORT LEDENGEGEVENS (geboortedatum + teams)
# ============================================================

def _parse_teams_from_cell(team_cell: str) -> list:
    """
    Parse teams uit een cel. Filtert alleen 'Teamspeler' teams.
    
    Voorbeelden:
    - "V12-2 (Technische staf), V16-1 (Teamspeler)" -> ["V16-1"]
    - "HS1*, DS2 (Teamspeler)" -> ["DS2"]
    - "U18-1 (Teamspeler), HS2 (Teamspeler)" -> ["U18-1", "HS2"]
    """
    if not team_cell or not isinstance(team_cell, str):
        return []
    
    teams = []
    # Split op komma
    parts = team_cell.split(",")
    
    for part in parts:
        part = part.strip()
        # Check of dit een Teamspeler is
        if "(Teamspeler)" in part:
            # Haal teamnaam (alles voor de haakjes)
            team_name = part.split("(")[0].strip()
            # Verwijder sterretjes
            team_name = team_name.replace("*", "").strip()
            if team_name:
                teams.append(team_name)
    
    return teams

def import_ledengegevens(df) -> tuple[int, int, int]:
    """
    Importeer ledengegevens (geboortedatum en teams) uit pandas DataFrame.
    Matcht op Lidnummer met bestaande scheidsrechters.
    
    Verwachte kolommen: Lidnummer, Geboortedatum, Team
    
    Returns: (bijgewerkt, niet_gevonden, errors)
    """
    bijgewerkt = 0
    niet_gevonden = 0
    errors = 0
    
    supabase = get_supabase_client()
    
    # Bepaal kolomnamen (case-insensitive)
    kolommen = {col.lower(): col for col in df.columns}
    
    lidnummer_col = kolommen.get("lidnummer")
    geboortedatum_col = kolommen.get("geboortedatum")
    team_col = kolommen.get("team")
    
    if not lidnummer_col:
        st.error("Kolom 'Lidnummer' niet gevonden in bestand")
        return 0, 0, len(df)
    
    for _, row in df.iterrows():
        try:
            # Haal lidnummer op
            nbb_nummer = str(row[lidnummer_col]).strip()
            if not nbb_nummer or nbb_nummer == "nan":
                continue
            
            # Check of scheidsrechter bestaat
            response = supabase.table("scheidsrechters").select("nbb_nummer").eq("nbb_nummer", nbb_nummer).execute()
            if not response.data:
                niet_gevonden += 1
                continue
            
            # Bouw update record
            update_data = {"updated_at": datetime.now().isoformat()}
            
            # Geboortedatum
            if geboortedatum_col and row.get(geboortedatum_col):
                geb_value = row[geboortedatum_col]
                # Converteer naar date string
                if hasattr(geb_value, 'strftime'):
                    # pandas Timestamp of datetime
                    geboortedatum = geb_value.strftime("%Y-%m-%d")
                else:
                    # String - probeer te parsen
                    geb_str = str(geb_value).strip()
                    if geb_str and geb_str != "nan":
                        # Probeer verschillende formaten
                        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]:
                            try:
                                dt = datetime.strptime(geb_str, fmt)
                                geboortedatum = dt.strftime("%Y-%m-%d")
                                break
                            except:
                                continue
                        else:
                            geboortedatum = None
                    else:
                        geboortedatum = None
                
                if geboortedatum:
                    update_data["geboortedatum"] = geboortedatum
            
            # Teams
            if team_col and row.get(team_col):
                teams = _parse_teams_from_cell(str(row[team_col]))
                if teams:
                    update_data["eigen_teams"] = teams
            
            # Update alleen als er data is (naast updated_at)
            if len(update_data) > 1:
                supabase.table("scheidsrechters").update(update_data).eq("nbb_nummer", nbb_nummer).execute()
                bijgewerkt += 1
            
        except Exception as e:
            errors += 1
    
    # Invalideer cache
    if "_db_cache_scheidsrechters" in st.session_state:
        del st.session_state["_db_cache_scheidsrechters"]
    
    return bijgewerkt, niet_gevonden, errors

# ============================================================
# SCHEIDSRECHTERS
# ============================================================

def laad_scheidsrechters() -> dict:
    """Laad alle scheidsrechters uit Supabase (met caching)"""
    cache_key = "_db_cache_scheidsrechters"
    
    # Return cached versie als beschikbaar
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("scheidsrechters").select("*").execute()
        
        # Converteer naar dict met nbb_nummer als key
        result = {}
        for row in response.data:
            nbb = row.pop("nbb_nummer")
            # Verwijder database metadata velden
            row.pop("created_at", None)
            row.pop("updated_at", None)
            result[nbb] = row
        
        # Cache resultaat
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.error(f"Fout bij laden scheidsrechters: {e}")
        return {}

def sla_scheidsrechters_op(scheidsrechters: dict) -> bool:
    """Sla alle scheidsrechters op naar Supabase (bulk)"""
    try:
        supabase = get_supabase_client()
        
        records = []
        for nbb_nummer, data in scheidsrechters.items():
            record = {
                "nbb_nummer": nbb_nummer,
                "updated_at": datetime.now().isoformat(),
                **data
            }
            records.append(record)
        
        # Bulk upsert in batches van 100
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            supabase.table("scheidsrechters").upsert(batch).execute()
        
        # Invalideer cache
        if "_db_cache_scheidsrechters" in st.session_state:
            del st.session_state["_db_cache_scheidsrechters"]
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan scheidsrechters: {e}")
        return False

def sla_scheidsrechter_op(nbb_nummer: str, data: dict) -> bool:
    """Sla één scheidsrechter op naar Supabase"""
    try:
        supabase = get_supabase_client()
        record = {
            "nbb_nummer": nbb_nummer,
            "updated_at": datetime.now().isoformat(),
            **data
        }
        supabase.table("scheidsrechters").upsert(record).execute()
        
        # Update cache in-place (sneller dan volledig herladen)
        if "_db_cache_scheidsrechters" in st.session_state:
            st.session_state["_db_cache_scheidsrechters"][nbb_nummer] = data
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan scheidsrechter: {e}")
        return False

def verwijder_scheidsrechter(nbb_nummer: str) -> bool:
    """Verwijder een scheidsrechter"""
    try:
        supabase = get_supabase_client()
        supabase.table("scheidsrechters").delete().eq("nbb_nummer", nbb_nummer).execute()
        
        # Update cache in-place
        if "_db_cache_scheidsrechters" in st.session_state:
            st.session_state["_db_cache_scheidsrechters"].pop(nbb_nummer, None)
        
        return True
    except Exception as e:
        st.error(f"Fout bij verwijderen scheidsrechter: {e}")
        return False
# ============================================================
# WEDSTRIJDEN
# ============================================================

def laad_wedstrijden() -> dict:
    """Laad alle wedstrijden uit Supabase (met caching)"""
    cache_key = "_db_cache_wedstrijden"
    
    # Return cached versie als beschikbaar
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("wedstrijden").select("*").execute()
        
        # Converteer naar dict met wed_id als key
        result = {}
        for row in response.data:
            wed_id = row.pop("wed_id")
            # Converteer datum terug naar string formaat
            if row.get("datum"):
                dt = datetime.fromisoformat(row["datum"].replace("Z", "+00:00"))
                row["datum"] = dt.strftime("%Y-%m-%d %H:%M")
            # Verwijder database metadata velden
            row.pop("created_at", None)
            row.pop("updated_at", None)
            result[wed_id] = row
        
        # Cache resultaat
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.error(f"Fout bij laden wedstrijden: {e}")
        return {}

def sla_wedstrijden_op(wedstrijden: dict) -> bool:
    """Sla alle wedstrijden op naar Supabase (bulk)"""
    try:
        supabase = get_supabase_client()
        
        records = []
        for wed_id, data in wedstrijden.items():
            # Converteer datum naar ISO formaat
            datum_str = data.get("datum", "")
            if datum_str:
                try:
                    dt = datetime.strptime(datum_str, "%Y-%m-%d %H:%M")
                    datum_iso = dt.isoformat()
                except:
                    datum_iso = datum_str
            else:
                datum_iso = None
            
            record = {
                "wed_id": wed_id,
                "datum": datum_iso,
                "thuisteam": data.get("thuisteam", ""),
                "uitteam": data.get("uitteam", ""),
                "niveau": data.get("niveau", 1),
                "vereist_bs2": data.get("vereist_bs2", False),
                "scheids_1": data.get("scheids_1"),
                "scheids_2": data.get("scheids_2"),
                "type": data.get("type", "thuis"),
                "reistijd_minuten": data.get("reistijd_minuten", 45),
                "geannuleerd": data.get("geannuleerd", False),
                "updated_at": datetime.now().isoformat()
            }
            records.append(record)
        
        # Bulk upsert in batches van 100
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            supabase.table("wedstrijden").upsert(batch).execute()
        
        # Invalideer cache
        if "_db_cache_wedstrijden" in st.session_state:
            del st.session_state["_db_cache_wedstrijden"]
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan wedstrijden: {e}")
        return False

def sla_wedstrijd_op(wed_id: str, data: dict) -> bool:
    """Sla één wedstrijd op naar Supabase"""
    try:
        supabase = get_supabase_client()
        
        # Converteer datum naar ISO formaat
        datum_str = data.get("datum", "")
        if datum_str:
            try:
                dt = datetime.strptime(datum_str, "%Y-%m-%d %H:%M")
                datum_iso = dt.isoformat()
            except:
                datum_iso = datum_str
        else:
            datum_iso = None
        
        record = {
            "wed_id": wed_id,
            "datum": datum_iso,
            "thuisteam": data.get("thuisteam", ""),
            "uitteam": data.get("uitteam", ""),
            "niveau": data.get("niveau", 1),
            "vereist_bs2": data.get("vereist_bs2", False),
            "scheids_1": data.get("scheids_1"),
            "scheids_2": data.get("scheids_2"),
            "begeleider": data.get("begeleider"),
            "type": data.get("type", "thuis"),
            "reistijd_minuten": data.get("reistijd_minuten", 45),
            "geannuleerd": data.get("geannuleerd", False),
            "updated_at": datetime.now().isoformat()
        }
        supabase.table("wedstrijden").upsert(record).execute()
        
        # Update cache in-place (sneller dan volledig herladen)
        if "_db_cache_wedstrijden" in st.session_state:
            st.session_state["_db_cache_wedstrijden"][wed_id] = data
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan wedstrijd: {e}")
        return False

def verwijder_wedstrijd(wed_id: str) -> bool:
    """Verwijder een wedstrijd"""
    try:
        supabase = get_supabase_client()
        supabase.table("wedstrijden").delete().eq("wed_id", wed_id).execute()
        
        # Update cache in-place
        if "_db_cache_wedstrijden" in st.session_state:
            st.session_state["_db_cache_wedstrijden"].pop(wed_id, None)
        
        return True
    except Exception as e:
        st.error(f"Fout bij verwijderen wedstrijd: {e}")
        return False

def verwijder_alle_wedstrijden() -> bool:
    """Verwijder alle wedstrijden"""
    try:
        supabase = get_supabase_client()
        # Delete all by selecting all and deleting
        supabase.table("wedstrijden").delete().neq("wed_id", "").execute()
        
        # Leeg cache volledig
        if "_db_cache_wedstrijden" in st.session_state:
            st.session_state["_db_cache_wedstrijden"] = {}
        
        return True
    except Exception as e:
        st.error(f"Fout bij verwijderen alle wedstrijden: {e}")
        return False

# ============================================================
# INSTELLINGEN
# ============================================================

def laad_instellingen() -> dict:
    """Laad instellingen uit Supabase (met caching)"""
    cache_key = "_db_cache_instellingen"
    
    # Return cached versie als beschikbaar
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("instellingen").select("*").execute()
        
        result = {}
        for row in response.data:
            key = row["key"]
            value = row["value"]
            # JSONB wordt automatisch geparsed
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except:
                    pass
            result[key] = value
        
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.error(f"Fout bij laden instellingen: {e}")
        return st.session_state.get(cache_key, {"inschrijf_deadline": "2025-01-08", "niveaus": {}})

def sla_instellingen_op(instellingen: dict) -> bool:
    """Sla instellingen op naar Supabase"""
    try:
        supabase = get_supabase_client()
        
        for key, value in instellingen.items():
            record = {
                "key": key,
                "value": json.dumps(value) if not isinstance(value, str) else f'"{value}"',
                "updated_at": datetime.now().isoformat()
            }
            supabase.table("instellingen").upsert(record).execute()
        
        # Update cache
        if "_db_cache_instellingen" in st.session_state:
            st.session_state["_db_cache_instellingen"] = instellingen
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan instellingen: {e}")
        return False

# ============================================================
# BELONINGEN
# ============================================================

def laad_beloningen() -> dict:
    """Laad beloningen uit Supabase (met caching)"""
    cache_key = "_db_cache_beloningen"
    
    # Return cached versie als beschikbaar
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("beloningen").select("*").order("seizoen", desc=True).limit(1).execute()
        
        if response.data:
            row = response.data[0]
            result = {
                "seizoen": row.get("seizoen", "2024-2025"),
                "spelers": row.get("spelers", {})
            }
        else:
            result = {"seizoen": "2024-2025", "spelers": {}}
        
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.error(f"Fout bij laden beloningen: {e}")
        return st.session_state.get(cache_key, {"seizoen": "2024-2025", "spelers": {}})

def sla_beloningen_op(beloningen: dict) -> bool:
    """Sla beloningen op naar Supabase"""
    try:
        supabase = get_supabase_client()
        record = {
            "seizoen": beloningen.get("seizoen", "2024-2025"),
            "spelers": beloningen.get("spelers", {}),
            "updated_at": datetime.now().isoformat()
        }
        supabase.table("beloningen").upsert(record).execute()
        
        # Update cache
        if "_db_cache_beloningen" in st.session_state:
            st.session_state["_db_cache_beloningen"] = beloningen
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan beloningen: {e}")
        return False

# ============================================================
# BELONINGSINSTELLINGEN
# ============================================================

def laad_beloningsinstellingen() -> dict:
    """Laad beloningsinstellingen uit Supabase (met caching)"""
    cache_key = "_db_cache_beloningsinstellingen"
    
    # Default waarden
    defaults = {
        "punten_per_wedstrijd": 1,
        "punten_eigen_niveau": 2,
        "punten_2e_scheids": 1,
        "punten_bonus_niveau_hoger": 1,
        "punten_lastig_tijdstip": 1,
        "punten_inval_48u": 3,
        "punten_inval_24u": 5,
        "punten_voor_voucher": 15,
        "strikes_afmelden_48u": 1,
        "strikes_afmelden_24u": 2,
        "strikes_afmelding_48u": 1,
        "strikes_afmelding_24u": 2,
        "strikes_no_show": 5,
        "strikes_waarschuwing_bij": 2,
        "strikes_gesprek_bij": 3,
        "strike_reductie_extra_wedstrijd": 1,
        "strike_reductie_invallen": 2,
        "strikes_vervallen_einde_seizoen": False
    }
    
    # Return cached versie als beschikbaar
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("beloningsinstellingen").select("*").eq("id", 1).execute()
        
        if response.data:
            row = response.data[0]
            row.pop("id", None)
            row.pop("updated_at", None)
            # Voeg eventueel ontbrekende keys toe met defaults
            for key, val in defaults.items():
                if key not in row:
                    row[key] = val
            result = row
        else:
            result = defaults.copy()
        
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.error(f"Fout bij laden beloningsinstellingen: {e}")
        return st.session_state.get(cache_key, defaults.copy())

def sla_beloningsinstellingen_op(instellingen: dict) -> bool:
    """Sla beloningsinstellingen op naar Supabase"""
    try:
        supabase = get_supabase_client()
        record = {
            "id": 1,
            **instellingen,
            "updated_at": datetime.now().isoformat()
        }
        supabase.table("beloningsinstellingen").upsert(record).execute()
        
        # Update cache
        if "_db_cache_beloningsinstellingen" in st.session_state:
            st.session_state["_db_cache_beloningsinstellingen"] = instellingen
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan beloningsinstellingen: {e}")
        return False

# ============================================================
# BESCHIKBARE KLUSJES
# ============================================================

def laad_beschikbare_klusjes() -> list:
    """Laad beschikbare klusjes uit Supabase (met caching)"""
    cache_key = "_db_cache_beschikbare_klusjes"
    
    # Return cached versie als beschikbaar
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("beschikbare_klusjes").select("*").execute()
        
        result = []
        for row in response.data:
            row.pop("created_at", None)
            result.append(row)
        
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.error(f"Fout bij laden beschikbare klusjes: {e}")
        return st.session_state.get(cache_key, [])  # Return oude cache als fallback

def sla_beschikbare_klusjes_op(klusjes: list) -> bool:
    """Sla beschikbare klusjes op naar Supabase"""
    try:
        supabase = get_supabase_client()
        
        # Verwijder bestaande en voeg nieuwe toe
        supabase.table("beschikbare_klusjes").delete().neq("id", "").execute()
        
        for klusje in klusjes:
            record = {
                "id": klusje.get("id"),
                "naam": klusje.get("naam"),
                "omschrijving": klusje.get("omschrijving", ""),
                "strikes_waarde": klusje.get("strikes_waarde", 1)
            }
            supabase.table("beschikbare_klusjes").insert(record).execute()
        
        # Clear cache zodat wijzigingen zichtbaar zijn
        if "_db_cache_beschikbare_klusjes" in st.session_state:
            del st.session_state["_db_cache_beschikbare_klusjes"]
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan beschikbare klusjes: {e}")
        return False

# ============================================================
# KLUSJES (uitgevoerd)
# ============================================================

def laad_klusjes() -> dict:
    """Laad uitgevoerde klusjes uit Supabase (met caching)"""
    cache_key = "_db_cache_klusjes"
    
    # Return cached versie als beschikbaar
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("klusjes").select("*").execute()
        
        # Converteer naar dict met id als key (string)
        result = {}
        for row in response.data:
            klusje_id = str(row.pop("id"))
            row.pop("created_at", None)
            # Converteer datum naar string als nodig
            if row.get("datum"):
                row["datum"] = str(row["datum"])
            result[klusje_id] = row
        
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.error(f"Fout bij laden klusjes: {e}")
        return st.session_state.get(cache_key, {})  # Return oude cache als fallback

def sla_klusjes_op(klusjes: dict) -> bool:
    """Sla uitgevoerde klusjes op naar Supabase"""
    try:
        supabase = get_supabase_client()
        
        for klusje_id, data in klusjes.items():
            record = {
                "nbb_nummer": data.get("nbb_nummer"),
                "klusje_id": data.get("klusje_id"),
                "datum": data.get("datum"),
                "status": data.get("status", "pending"),
                "goedgekeurd_door": data.get("goedgekeurd_door")
            }
            # Als het een nieuw klusje is (geen numeriek id), insert
            if not klusje_id.isdigit():
                supabase.table("klusjes").insert(record).execute()
            else:
                record["id"] = int(klusje_id)
                supabase.table("klusjes").upsert(record).execute()
        
        # Update cache
        if "_db_cache_klusjes" in st.session_state:
            st.session_state["_db_cache_klusjes"] = klusjes
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan klusjes: {e}")
        return False

def voeg_klusje_toe(nbb_nummer: str, klusje_id: str) -> bool:
    """Voeg een nieuw uitgevoerd klusje toe"""
    try:
        supabase = get_supabase_client()
        record = {
            "nbb_nummer": nbb_nummer,
            "klusje_id": klusje_id,
            "datum": datetime.now().strftime("%Y-%m-%d"),
            "status": "pending"
        }
        supabase.table("klusjes").insert(record).execute()
        return True
    except Exception as e:
        st.error(f"Fout bij toevoegen klusje: {e}")
        return False

# ============================================================
# VERVANGINGSVERZOEKEN
# ============================================================

def laad_vervangingsverzoeken() -> dict:
    """Laad vervangingsverzoeken uit Supabase (met caching)"""
    cache_key = "_db_cache_vervangingsverzoeken"
    
    # Return cached versie als beschikbaar
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("vervangingsverzoeken").select("*").execute()
        
        result = {}
        for row in response.data:
            verzoek_id = str(row.pop("id"))
            row.pop("created_at", None)
            row.pop("updated_at", None)
            result[verzoek_id] = row
        
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.error(f"Fout bij laden vervangingsverzoeken: {e}")
        return st.session_state.get(cache_key, {})  # Return oude cache als fallback

def sla_vervangingsverzoeken_op(verzoeken: dict) -> bool:
    """Sla vervangingsverzoeken op naar Supabase"""
    try:
        supabase = get_supabase_client()
        
        for verzoek_id, data in verzoeken.items():
            record = {
                "wed_id": data.get("wed_id"),
                "aanvrager_nbb": data.get("aanvrager_nbb"),
                "vervanger_nbb": data.get("vervanger_nbb"),
                "positie": data.get("positie"),
                "status": data.get("status", "pending"),
                "updated_at": datetime.now().isoformat()
            }
            if verzoek_id.isdigit():
                record["id"] = int(verzoek_id)
            supabase.table("vervangingsverzoeken").upsert(record).execute()
        
        # Update cache
        if "_db_cache_vervangingsverzoeken" in st.session_state:
            st.session_state["_db_cache_vervangingsverzoeken"] = verzoeken
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan vervangingsverzoeken: {e}")
        return False

def voeg_vervangingsverzoek_toe(wed_id: str, aanvrager_nbb: str, vervanger_nbb: str, positie: str) -> bool:
    """Voeg een nieuw vervangingsverzoek toe"""
    try:
        supabase = get_supabase_client()
        record = {
            "wed_id": wed_id,
            "aanvrager_nbb": aanvrager_nbb,
            "vervanger_nbb": vervanger_nbb,
            "positie": positie,
            "status": "pending"
        }
        supabase.table("vervangingsverzoeken").insert(record).execute()
        return True
    except Exception as e:
        st.error(f"Fout bij toevoegen vervangingsverzoek: {e}")
        return False

# ============================================================
# BEGELEIDINGSUITNODIGINGEN
# ============================================================

def laad_begeleidingsuitnodigingen() -> dict:
    """Laad begeleidingsuitnodigingen uit Supabase (met caching)"""
    cache_key = "_db_cache_begeleidingsuitnodigingen"
    
    # Return cached versie als beschikbaar
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        supabase = get_supabase_client()
        response = supabase.table("begeleidingsuitnodigingen").select("*").execute()
        
        result = {}
        for row in response.data:
            uitnodiging_id = str(row.pop("id"))
            row.pop("created_at", None)
            row.pop("updated_at", None)
            result[uitnodiging_id] = row
        
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.error(f"Fout bij laden begeleidingsuitnodigingen: {e}")
        return st.session_state.get(cache_key, {})  # Return oude cache als fallback

def sla_begeleidingsuitnodigingen_op(uitnodigingen: dict) -> bool:
    """Sla begeleidingsuitnodigingen op naar Supabase"""
    try:
        supabase = get_supabase_client()
        
        for uitnodiging_id, data in uitnodigingen.items():
            record = {
                "wed_id": data.get("wed_id"),
                "mse_nbb": data.get("mse_nbb"),
                "speler_nbb": data.get("speler_nbb"),
                "status": data.get("status", "pending"),
                "updated_at": datetime.now().isoformat()
            }
            if uitnodiging_id.isdigit():
                record["id"] = int(uitnodiging_id)
            supabase.table("begeleidingsuitnodigingen").upsert(record).execute()
        
        # Update cache
        if "_db_cache_begeleidingsuitnodigingen" in st.session_state:
            st.session_state["_db_cache_begeleidingsuitnodigingen"] = uitnodigingen
        
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan begeleidingsuitnodigingen: {e}")
        return False

def voeg_begeleidingsuitnodiging_toe(wed_id: str, mse_nbb: str, speler_nbb: str) -> bool:
    """Voeg een nieuwe begeleidingsuitnodiging toe"""
    try:
        supabase = get_supabase_client()
        record = {
            "wed_id": wed_id,
            "mse_nbb": mse_nbb,
            "speler_nbb": speler_nbb,
            "status": "pending"
        }
        supabase.table("begeleidingsuitnodigingen").insert(record).execute()
        return True
    except Exception as e:
        st.error(f"Fout bij toevoegen begeleidingsuitnodiging: {e}")
        return False

# ============================================================
# BULK IMPORT FUNCTIES
# ============================================================

def import_scheidsrechters_bulk(scheidsrechters: dict) -> tuple[int, int]:
    """Importeer scheidsrechters in bulk. Returns (success_count, error_count)"""
    success = 0
    errors = 0
    supabase = get_supabase_client()
    
    for nbb_nummer, data in scheidsrechters.items():
        try:
            record = {
                "nbb_nummer": nbb_nummer,
                **data
            }
            supabase.table("scheidsrechters").upsert(record).execute()
            success += 1
        except Exception as e:
            errors += 1
            print(f"Fout bij importeren {nbb_nummer}: {e}")
    
    return success, errors

def import_wedstrijden_bulk(wedstrijden: dict) -> tuple[int, int]:
    """Importeer wedstrijden in bulk. Returns (success_count, error_count)"""
    success = 0
    errors = 0
    supabase = get_supabase_client()
    
    for wed_id, data in wedstrijden.items():
        try:
            # Converteer datum naar ISO formaat
            datum_str = data.get("datum", "")
            if datum_str:
                try:
                    dt = datetime.strptime(datum_str, "%Y-%m-%d %H:%M")
                    datum_iso = dt.isoformat()
                except:
                    datum_iso = datum_str
            else:
                datum_iso = None
            
            record = {
                "wed_id": wed_id,
                "datum": datum_iso,
                "thuisteam": data.get("thuisteam", ""),
                "uitteam": data.get("uitteam", ""),
                "niveau": data.get("niveau", 1),
                "vereist_bs2": data.get("vereist_bs2", False),
                "scheids_1": data.get("scheids_1"),
                "scheids_2": data.get("scheids_2"),
                "type": data.get("type", "thuis"),
                "reistijd_minuten": data.get("reistijd_minuten", 45),
                "geannuleerd": data.get("geannuleerd", False)
            }
            supabase.table("wedstrijden").upsert(record).execute()
            success += 1
        except Exception as e:
            errors += 1
            print(f"Fout bij importeren {wed_id}: {e}")
    
    return success, errors

# ============================================================
# BEGELEIDING FEEDBACK
# ============================================================

def laad_begeleiding_feedback() -> dict:
    """Laad alle begeleiding feedback uit Supabase (geen caching - altijd verse data)"""
    # Geen caching voor feedback - andere gebruikers kunnen feedback hebben gegeven
    try:
        supabase = get_supabase_client()
        response = supabase.table("begeleiding_feedback").select("*").execute()
        
        feedback_dict = {}
        for row in response.data:
            feedback_id = row.get("feedback_id")
            if feedback_id:
                feedback_dict[feedback_id] = {
                    "feedback_id": feedback_id,
                    "wed_id": row.get("wed_id"),
                    "speler_nbb": row.get("speler_nbb"),
                    "begeleider_nbb": row.get("begeleider_nbb"),
                    "status": row.get("status"),
                    "feedback_datum": row.get("feedback_datum"),
                    "opmerking": row.get("opmerking", "")
                }
        
        return feedback_dict
    except Exception as e:
        st.error(f"Fout bij laden feedback: {e}")
        return {}

def sla_begeleiding_feedback_op(feedback_id: str, data: dict) -> bool:
    """Sla een begeleiding feedback op"""
    try:
        supabase = get_supabase_client()
        
        record = {
            "feedback_id": feedback_id,
            "wed_id": data.get("wed_id"),
            "speler_nbb": data.get("speler_nbb"),
            "begeleider_nbb": data.get("begeleider_nbb"),
            "status": data.get("status"),
            "feedback_datum": data.get("feedback_datum", datetime.now().isoformat()),
            "opmerking": data.get("opmerking", ""),
            "updated_at": datetime.now().isoformat()
        }
        
        supabase.table("begeleiding_feedback").upsert(record).execute()
        return True
    except Exception as e:
        st.error(f"Fout bij opslaan feedback: {e}")
        return False

def verwijder_begeleiding_feedback(feedback_id: str) -> bool:
    """Verwijder een begeleiding feedback"""
    try:
        supabase = get_supabase_client()
        supabase.table("begeleiding_feedback").delete().eq("feedback_id", feedback_id).execute()
        return True
    except Exception as e:
        st.error(f"Fout bij verwijderen feedback: {e}")
        return False
