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

# Configuratie
DATA_DIR = Path(__file__).parent / "data"
BEHEERDER_WACHTWOORD = "waterdragers2025"  # Pas aan!

# Zorg dat data directory bestaat
DATA_DIR.mkdir(exist_ok=True)

# ============================================================
# DATA FUNCTIES
# ============================================================

def laad_json(bestand: str) -> dict | list:
    """Laad JSON bestand, retourneer lege dict/list als niet bestaat."""
    pad = DATA_DIR / bestand
    if pad.exists():
        with open(pad, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def sla_json_op(bestand: str, data: dict | list):
    """Sla data op als JSON."""
    pad = DATA_DIR / bestand
    with open(pad, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

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
        # Check of dit een wedstrijd is van een eigen team
        is_eigen_wed = False
        
        if wed.get("type") == "uit":
            # Bij uitwedstrijd: thuisteam is het eigen team dat uit speelt
            if wed["thuisteam"] in eigen_teams:
                is_eigen_wed = True
        else:
            # Bij thuiswedstrijd: check beide teams
            if wed["thuisteam"] in eigen_teams or wed["uitteam"] in eigen_teams:
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

def get_beschikbare_wedstrijden(nbb_nummer: str, als_eerste: bool) -> list:
    """
    Haal wedstrijden op waar deze scheidsrechter zich voor kan inschrijven.
    Filtert op niveau, eigen teams, zondag-restrictie, etc.
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
        
        # Check eigen team (thuiswedstrijd van eigen team)
        if wed["thuisteam"] in scheids.get("eigen_teams", []) or \
           wed["uitteam"] in scheids.get("eigen_teams", []):
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
    
    return sorted(beschikbaar, key=lambda x: x["datum"])

def tel_wedstrijden_scheidsrechter(nbb_nummer: str) -> int:
    """Tel aantal wedstrijden waar scheidsrechter is ingeschreven/toegewezen."""
    wedstrijden = laad_wedstrijden()
    inschrijvingen = laad_inschrijvingen()
    
    count = 0
    for wed_id, wed in wedstrijden.items():
        if wed.get("scheids_1") == nbb_nummer or wed.get("scheids_2") == nbb_nummer:
            count += 1
    
    return count

def get_kandidaten_voor_wedstrijd(wed_id: str, als_eerste: bool) -> list:
    """Haal geschikte kandidaten op voor een wedstrijd (voor beheerder)."""
    scheidsrechters = laad_scheidsrechters()
    wedstrijden = laad_wedstrijden()
    
    if wed_id not in wedstrijden:
        return []
    
    wed = wedstrijden[wed_id]
    wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
    
    kandidaten = []
    for nbb, scheids in scheidsrechters.items():
        max_niveau = scheids["niveau_1e_scheids"] if als_eerste else scheids["niveau_2e_scheids"]
        
        # Check niveau
        if wed["niveau"] > max_niveau:
            continue
        
        # Check BS2 vereiste
        if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
            continue
        
        # Check eigen team (thuiswedstrijd van eigen team)
        if wed["thuisteam"] in scheids.get("eigen_teams", []) or \
           wed["uitteam"] in scheids.get("eigen_teams", []):
            continue
        
        # Check zondag
        if scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6:
            continue
        
        # Check of scheidsrechter op dit tijdstip een eigen wedstrijd heeft
        if heeft_eigen_wedstrijd(nbb, wed_datum, wedstrijden, scheidsrechters):
            continue
        
        # Check maximum
        huidig_aantal = tel_wedstrijden_scheidsrechter(nbb)
        if huidig_aantal >= scheids.get("max_wedstrijden", 99):
            continue
        
        # Check of niet al andere positie bij deze wedstrijd
        andere_positie = "scheids_2" if als_eerste else "scheids_1"
        if wed.get(andere_positie) == nbb:
            continue
        
        # Bereken "urgentie" - wie moet nog het meest?
        min_wed = scheids.get("min_wedstrijden", 0)
        tekort = max(0, min_wed - huidig_aantal)
        
        kandidaten.append({
            "nbb_nummer": nbb,
            "naam": scheids["naam"],
            "huidig_aantal": huidig_aantal,
            "min_wedstrijden": min_wed,
            "max_wedstrijden": scheids.get("max_wedstrijden", 99),
            "tekort": tekort
        })
    
    # Sorteer: eerst wie tekort heeft, dan op minste wedstrijden
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
    
    # Status
    huidig_aantal = tel_wedstrijden_scheidsrechter(nbb_nummer)
    min_wed = scheids.get("min_wedstrijden", 0)
    max_wed = scheids.get("max_wedstrijden", 99)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Ingeschreven", huidig_aantal)
    with col2:
        st.metric("Minimum", min_wed)
    with col3:
        st.metric("Maximum", max_wed)
    
    if huidig_aantal < min_wed:
        st.warning(f"⚠️ Je moet nog minimaal {min_wed - huidig_aantal} wedstrijd(en) kiezen.")
    elif huidig_aantal >= max_wed:
        st.success("✅ Je hebt je maximum bereikt.")
    
    # Check deadline
    deadline = datetime.strptime(instellingen["inschrijf_deadline"], "%Y-%m-%d")
    dagen_over = (deadline - datetime.now()).days
    
    if dagen_over < 0:
        st.info(f"📅 De inschrijfperiode is gesloten. Je kunt je wedstrijden hieronder bekijken.")
        kan_inschrijven = False
    else:
        st.info(f"📅 Inschrijven kan nog {dagen_over} dagen (tot {deadline.strftime('%d-%m-%Y')})")
        kan_inschrijven = True
    
    st.divider()
    
    # Toon huidige inschrijvingen
    st.subheader("📋 Jouw wedstrijden")
    
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
            
            with st.container():
                col1, col2, col3 = st.columns([2, 3, 2])
                with col1:
                    st.write(f"**{dag} {wed_datum.strftime('%d-%m %H:%M')}**")
                with col2:
                    st.write(f"{wed['thuisteam']} - {wed['uitteam']}")
                with col3:
                    st.write(f"*{wed['rol']}*")
                
                # Afmelden alleen tijdens inschrijfperiode
                if kan_inschrijven:
                    if st.button("❌ Afmelden", key=f"afmeld_{wed['id']}"):
                        positie = "scheids_1" if wed["rol"] == "1e scheidsrechter" else "scheids_2"
                        wedstrijden[wed["id"]][positie] = None
                        sla_wedstrijden_op(wedstrijden)
                        st.rerun()
    else:
        st.write("*Nog geen wedstrijden.*")
    
    if not kan_inschrijven:
        return
    
    st.divider()
    
    # Beschikbare wedstrijden
    st.subheader("📝 Beschikbare wedstrijden")
    
    tab1, tab2 = st.tabs(["Als 1e scheidsrechter", "Als 2e scheidsrechter"])
    
    with tab1:
        beschikbaar_1e = get_beschikbare_wedstrijden(nbb_nummer, als_eerste=True)
        if beschikbaar_1e:
            for wed in beschikbaar_1e:
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
                niveau_tekst = instellingen["niveaus"].get(str(wed["niveau"]), "")
                
                with st.container():
                    col1, col2, col3 = st.columns([2, 3, 2])
                    with col1:
                        st.write(f"**{dag} {wed_datum.strftime('%d-%m %H:%M')}**")
                    with col2:
                        st.write(f"{wed['thuisteam']} - {wed['uitteam']}")
                        st.caption(f"Niveau {wed['niveau']} ({niveau_tekst})")
                    with col3:
                        if huidig_aantal < max_wed:
                            if st.button("✅ Inschrijven", key=f"1e_{wed['id']}"):
                                wedstrijden[wed["id"]]["scheids_1"] = nbb_nummer
                                sla_wedstrijden_op(wedstrijden)
                                st.rerun()
                        else:
                            st.write("*Maximum bereikt*")
        else:
            st.write("*Geen wedstrijden beschikbaar als 1e scheidsrechter.*")
    
    with tab2:
        beschikbaar_2e = get_beschikbare_wedstrijden(nbb_nummer, als_eerste=False)
        if beschikbaar_2e:
            for wed in beschikbaar_2e:
                wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
                dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
                niveau_tekst = instellingen["niveaus"].get(str(wed["niveau"]), "")
                
                with st.container():
                    col1, col2, col3 = st.columns([2, 3, 2])
                    with col1:
                        st.write(f"**{dag} {wed_datum.strftime('%d-%m %H:%M')}**")
                    with col2:
                        st.write(f"{wed['thuisteam']} - {wed['uitteam']}")
                        st.caption(f"Niveau {wed['niveau']} ({niveau_tekst})")
                    with col3:
                        if huidig_aantal < max_wed:
                            if st.button("✅ Inschrijven", key=f"2e_{wed['id']}"):
                                wedstrijden[wed["id"]]["scheids_2"] = nbb_nummer
                                sla_wedstrijden_op(wedstrijden)
                                st.rerun()
                        else:
                            st.write("*Maximum bereikt*")
        else:
            st.write("*Geen wedstrijden beschikbaar als 2e scheidsrechter.*")

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
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Wedstrijden", 
        "👥 Scheidsrechters", 
        "⚙️ Instellingen",
        "📊 Import/Export"
    ])
    
    with tab1:
        toon_wedstrijden_beheer()
    
    with tab2:
        toon_scheidsrechters_beheer()
    
    with tab3:
        toon_instellingen_beheer()
    
    with tab4:
        toon_import_export()

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
        
        if filter_status == "Nog in te vullen" and compleet:
            continue
        if filter_status == "Compleet" and not compleet:
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
            "reistijd": wed.get("reistijd_minuten", 0)
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
            status_icon = "✅" if wed["compleet"] else "⚠️"
            label = f"{status_icon} {dag} {wed_datum.strftime('%d-%m %H:%M')} | {wed['thuisteam']} - {wed['uitteam']} (Niv. {wed['niveau']})"
        else:
            label = f"🚗 {dag} {wed_datum.strftime('%d-%m %H:%M')} | {wed['thuisteam']} @ {wed['uitteam']} ({wed['reistijd']} min reistijd)"
        
        with st.expander(label):
            if type_filter == "thuis":
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
                    if st.button("🗑️ Verwijder", key=f"delwed_{wed['id']}"):
                        del wedstrijden[wed["id"]]
                        sla_wedstrijden_op(wedstrijden)
                        st.rerun()
            else:
                # Uitwedstrijd - alleen info en delete
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Team:** {wed['thuisteam']}")
                    st.write(f"**Reistijd:** {wed['reistijd']} minuten")
                with col2:
                    if st.button("🗑️ Verwijder", key=f"delwed_{wed['id']}"):
                        del wedstrijden[wed["id"]]
                        sla_wedstrijden_op(wedstrijden)
                        st.rerun()

def toon_scheidsrechters_beheer():
    """Beheer scheidsrechters."""
    scheidsrechters = laad_scheidsrechters()
    
    st.subheader("Scheidsrechtersoverzicht")
    
    # Statistieken
    for nbb, scheids in sorted(scheidsrechters.items(), key=lambda x: x[1]["naam"]):
        huidig = tel_wedstrijden_scheidsrechter(nbb)
        min_wed = scheids.get("min_wedstrijden", 0)
        max_wed = scheids.get("max_wedstrijden", 99)
        
        tekort = max(0, min_wed - huidig)
        status = "⚠️" if tekort > 0 else "✅"
        
        with st.expander(f"{status} {scheids['naam']} - {huidig}/{min_wed}-{max_wed} wedstrijden"):
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
                        nieuwe_naam = st.text_input("Naam", value=scheids.get("naam", ""), key=f"naam_{nbb}")
                        bs2_diploma = st.checkbox("BS2 diploma", value=scheids.get("bs2_diploma", False), key=f"bs2_{nbb}")
                        niet_op_zondag = st.checkbox("Niet op zondag", value=scheids.get("niet_op_zondag", False), key=f"zondag_{nbb}")
                    with col2:
                        niveau_1e = st.selectbox("1e scheids t/m niveau", [1, 2, 3, 4, 5], 
                                                  index=scheids.get("niveau_1e_scheids", 1) - 1, key=f"niv1_{nbb}")
                        niveau_2e = st.selectbox("2e scheids t/m niveau", [1, 2, 3, 4, 5], 
                                                  index=scheids.get("niveau_2e_scheids", 5) - 1, key=f"niv2_{nbb}")
                        min_w = st.number_input("Minimum wedstrijden", min_value=0, 
                                                value=scheids.get("min_wedstrijden", 2), key=f"min_{nbb}")
                        max_w = st.number_input("Maximum wedstrijden", min_value=1, 
                                                value=scheids.get("max_wedstrijden", 5), key=f"max_{nbb}")
                    
                    eigen_teams_str = ", ".join(scheids.get("eigen_teams", []))
                    eigen_teams = st.text_input("Eigen teams (komma-gescheiden)", value=eigen_teams_str, key=f"teams_{nbb}")
                    
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
                                "eigen_teams": [t.strip() for t in eigen_teams.split(",") if t.strip()]
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
        
        eigen_teams = st.text_input("Eigen teams (komma-gescheiden)")
        
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
                    "eigen_teams": [t.strip() for t in eigen_teams.split(",") if t.strip()]
                }
                sla_scheidsrechters_op(scheidsrechters)
                st.success("Scheidsrechter toegevoegd!")
                st.rerun()
            else:
                st.error("NBB-nummer en naam zijn verplicht")

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
    
    # Fallback op basis van leeftijdscategorie als team niet bekend is
    if "X10" in team or "X12" in team and "1" not in team:
        return 1
    elif "X12" in team or "V12" in team or "X14" in team:
        return 2
    elif "X14" in team or "M16" in team or "V16" in team:
        return 3
    elif "M18" in team or "V16-1" in team:
        return 4
    elif "M20" in team or "MSE" in team:
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
                        # Preview
                        st.dataframe(df_club[["Datum", "Tijd", "Thuisteam", "Uitteam", "Plaatsnaam"]].head(10))
                        
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
                                    wedstrijden[wed_id] = {
                                        "datum": f"{datum} {tijd}",
                                        "thuisteam": row["Thuisteam"],
                                        "uitteam": row["Uitteam"],
                                        "niveau": niveau,
                                        "type": "thuis",
                                        "vereist_bs2": vereist_bs2,
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
