"""
Database module voor Supabase connectie
Ref Planner - BV Waterdragers
"""

import os
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import json

# Supabase configuratie - eerst secrets proberen, dan environment variables, dan defaults
def get_supabase_config():
    """Haal Supabase configuratie op uit secrets of environment"""
    try:
        # Probeer Streamlit secrets
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
        if url and key:
            return url, key
    except:
        pass
    
    # Fallback naar environment variables of defaults
    url = os.environ.get("SUPABASE_URL", "https://xgtopzblkoyygcdnvtuv.supabase.co")
    key = os.environ.get("SUPABASE_KEY", "sb_publishable_CMPQ44NKT0G1bTVoXYSJgQ_pSkOfy4C")
    return url, key

SUPABASE_URL, SUPABASE_KEY = get_supabase_config()

@st.cache_resource
def get_supabase_client() -> Client:
    """Maak een Supabase client (cached)"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

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
