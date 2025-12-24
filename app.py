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
                "1": "U10, U12",
                "2": "U14, U16 recreatie", 
                "3": "U16 hogere divisie, U18",
                "4": "Senioren lager",
                "5": "Senioren hoger, MSE"
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
        # Check niveau
        if wed["niveau"] > max_niveau:
            continue
        
        # Check BS2 vereiste
        if wed.get("vereist_bs2", False) and not scheids.get("bs2_diploma", False):
            continue
        
        # Check eigen team
        if wed["thuisteam"] in scheids.get("eigen_teams", []) or \
           wed["uitteam"] in scheids.get("eigen_teams", []):
            continue
        
        # Check zondag
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        if scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6:
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
        
        # Check eigen team
        if wed["thuisteam"] in scheids.get("eigen_teams", []) or \
           wed["uitteam"] in scheids.get("eigen_teams", []):
            continue
        
        # Check zondag
        if scheids.get("niet_op_zondag", False) and wed_datum.weekday() == 6:
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
    
    # Filter opties
    col1, col2 = st.columns(2)
    with col1:
        filter_status = st.selectbox("Filter", ["Alle", "Nog in te vullen", "Compleet"])
    with col2:
        sorteer = st.selectbox("Sorteer op", ["Datum", "Niveau"])
    
    # Wedstrijden lijst
    wed_lijst = []
    for wed_id, wed in wedstrijden.items():
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
            "compleet": compleet
        })
    
    if sorteer == "Datum":
        wed_lijst.sort(key=lambda x: x["datum"])
    else:
        wed_lijst.sort(key=lambda x: (x["niveau"], x["datum"]))
    
    # Toon wedstrijden
    for wed in wed_lijst:
        wed_datum = datetime.strptime(wed["datum"], "%Y-%m-%d %H:%M")
        dag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][wed_datum.weekday()]
        niveau_tekst = instellingen["niveaus"].get(str(wed["niveau"]), "")
        
        status_icon = "✅" if wed["compleet"] else "⚠️"
        
        with st.expander(f"{status_icon} {dag} {wed_datum.strftime('%d-%m %H:%M')} | {wed['thuisteam']} - {wed['uitteam']} (Niv. {wed['niveau']})"):
            col1, col2 = st.columns(2)
            
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
    
    st.divider()
    
    # Nieuwe wedstrijd toevoegen
    st.subheader("➕ Nieuwe wedstrijd toevoegen")
    
    with st.form("nieuwe_wedstrijd"):
        col1, col2 = st.columns(2)
        with col1:
            datum = st.date_input("Datum")
            tijd = st.time_input("Tijd")
            thuisteam = st.text_input("Thuisteam")
        with col2:
            uitteam = st.text_input("Uitteam")
            niveau = st.selectbox("Niveau", [1, 2, 3, 4, 5])
            vereist_bs2 = st.checkbox("BS2 vereist")
        
        if st.form_submit_button("Toevoegen"):
            wed_id = f"wed_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            wedstrijden[wed_id] = {
                "datum": f"{datum} {tijd.strftime('%H:%M')}",
                "thuisteam": thuisteam,
                "uitteam": uitteam,
                "niveau": niveau,
                "vereist_bs2": vereist_bs2,
                "scheids_1": None,
                "scheids_2": None
            }
            sla_wedstrijden_op(wedstrijden)
            st.success("Wedstrijd toegevoegd!")
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
            st.code(f"/inschrijven/{nbb}")
    
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
            niveau_2e = st.selectbox("2e scheids t/m niveau", [1, 2, 3, 4, 5], index=2)
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

def toon_import_export():
    """Import/export functionaliteit."""
    st.subheader("Import / Export")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Import scheidsrechters (CSV)**")
        st.write("Verwacht formaat: nbb_nummer, naam, bs2_diploma, niveau_1e, niveau_2e, min, max, niet_zondag, eigen_teams")
        
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
    
    with col2:
        st.write("**Export planning (CSV)**")
        
        if st.button("Download planning"):
            wedstrijden = laad_wedstrijden()
            scheidsrechters = laad_scheidsrechters()
            
            output = "datum,tijd,thuisteam,uitteam,niveau,scheids_1,scheids_2\n"
            for wed_id, wed in sorted(wedstrijden.items(), key=lambda x: x[1]["datum"]):
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

# ============================================================
# MAIN ROUTING
# ============================================================

def main():
    st.set_page_config(
        page_title="Scheidsrechter Planning",
        page_icon="🏀",
        layout="wide"
    )
    
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
