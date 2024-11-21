import streamlit as st
import time
from datetime import datetime
import pandas as pd
import json
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from pyzbar.pyzbar import decode
import numpy as np
import requests
# Neue Imports: Barcode Scanner
from PIL import Image

# Cloudinary Konfiguration
cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"]
)

# Initialize session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Dashboard"
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'activity_feed' not in st.session_state:
    st.session_state.activity_feed = []
if 'barcode_result' not in st.session_state:
    st.session_state.barcode_result = None
if 'last_scan_time' not in st.session_state:
    st.session_state.last_scan_time = 0

# Ranking Symbole
RANKING_SYMBOLS = {
    1: "👑",  # Gold-Krone für Platz 1
    2: "🥈",  # Silbermedaille
    3: "🥉"   # Bronzemedaille
}

# Konstanten für die Getränke
DRINKS = {
    "Bier 🍺": {"alcohol_content": 0.05, "volume": 500},
    "Wein 🍷": {"alcohol_content": 0.12, "volume": 200},
    "Schnaps 🥃": {"alcohol_content": 0.40, "volume": 20},
    "Custom 🍾": {"alcohol_content": None, "volume": None}
}

# Neue Konstante für Getränkekategorien
DRINK_CATEGORIES = {
    "Bier 🍺": ["Pils", "Weizen", "Craft Beer", "Radler", "Alkoholfrei"],
    "Wein 🍷": ["Rotwein", "Weißwein", "Rosé", "Sekt", "Prosecco", "Champagner"],
    "Schnaps 🥃": ["Vodka", "Whiskey", "Gin", "Rum", "Jägermeister", "Likör", "Shots"]
}

# Vorgeschlagene Getränke-Datenbank
SUGGESTED_DRINKS = {
    "Beck's Pils": {"alcohol_content": 0.049, "volume": 500},
    "Jägermeister": {"alcohol_content": 0.35, "volume": 40},
    "Absolut Vodka": {"alcohol_content": 0.40, "volume": 40},
    "Corona Extra": {"alcohol_content": 0.046, "volume": 355},
    "Paulaner Hefeweizen": {"alcohol_content": 0.055, "volume": 500},
    "Hugo": {"alcohol_content": 0.11, "volume": 200},
    "Aperol Spritz": {"alcohol_content": 0.11, "volume": 200},
    "Rotwein (durchschnittlich)": {"alcohol_content": 0.13, "volume": 200},
    "Weißwein (durchschnittlich)": {"alcohol_content": 0.12, "volume": 200},
    "Sekt": {"alcohol_content": 0.11, "volume": 100},
}

# Konstanten für Beziehungsstatus
STATUS_OPTIONS = ["Vergeben", "Single", "Unentschlossen"]

# Barcode Scanner für Mobile
def mobile_barcode_scanner():
    st.write("##### Option 1: Barcode scannen")
    
    # Status Info
    if 'scan_status' not in st.session_state:
        st.session_state.scan_status = "Scanner bereit..."
    
    # Kamera Input
    camera_input = st.camera_input("Barcode scannen")
    
    if camera_input:
        # Bild verarbeiten
        try:
            # Konvertiere zu PIL Image
            image = Image.open(camera_input)
            # Konvertiere zu Numpy Array
            img_array = np.array(image)
            
            # OpenCV Verarbeitung
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            # Kontrast erhöhen
            gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
            
            # Barcode suchen
            barcodes = decode(gray)
            
            if barcodes:
                for barcode in barcodes:
                    # Barcode gefunden
                    barcode_data = barcode.data.decode('utf-8')
                    st.success(f"Barcode gefunden: {barcode_data}")
                    
                    # Getränk in Datenbank suchen
                    with st.spinner("Suche Getränk..."):
                        drink_info = get_drink_info_from_barcode(barcode_data)
                        if drink_info:
                            st.session_state.barcode_result = drink_info
                            st.success(f"✅ Getränk erkannt: {drink_info['name']}")
                            if drink_info['image_url']:
                                st.image(drink_info['image_url'], width=100)
                        else:
                            st.error("❌ Getränk nicht in Datenbank gefunden")
            else:
                st.warning("Kein Barcode erkannt. Bitte erneut versuchen.")
                
        except Exception as e:
            st.error(f"Fehler beim Scannen: {str(e)}")

def get_drink_info_from_barcode(barcode):
    """Ruft Getränkeinformationen von OpenFoodFacts API ab"""
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 1:  # Produkt gefunden
                product = data['product']
                # Versuche Alkoholgehalt zu finden
                alcohol_content = None
                if 'alcohol_value' in product:
                    alcohol_content = float(product['alcohol_value']) / 100
                elif 'alcohol_100g' in product:
                    alcohol_content = float(product['alcohol_100g']) / 100
                
                # Versuche Volumen zu finden
                volume = None
                if 'quantity' in product:
                    # Extrahiere Zahl aus String wie "500ml" oder "0.5l"
                    vol_str = product['quantity'].lower()
                    if 'ml' in vol_str:
                        volume = float(vol_str.replace('ml', '').strip())
                    elif 'l' in vol_str:
                        volume = float(vol_str.replace('l', '').strip()) * 1000
                
                return {
                    'name': product.get('product_name', 'Unbekanntes Getränk'),
                    'alcohol_content': alcohol_content,
                    'volume': volume,
                    'image_url': product.get('image_url', None)
                }
    except Exception as e:
        st.error(f"Fehler beim Abrufen der Produktinformationen: {e}")
    return None

def save_data():
    """Speichert alle Daten in einer JSON-Datei"""
    data = {
        'participants': st.session_state.participants,
        'party_start_time': st.session_state.party_start_time
    }
    with open('party_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def load_data():
    """Lädt die Daten aus der JSON-Datei"""
    try:
        if os.path.exists('party_data.json'):
            with open('party_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.participants = data.get('participants', {})
                st.session_state.party_start_time = data.get('party_start_time', time.time())
        else:
            st.session_state.participants = {}
            st.session_state.party_start_time = time.time()
    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
        st.session_state.participants = {}
        st.session_state.party_start_time = time.time()

def add_activity(activity_type, details):
    """Fügt eine neue Aktivität zum Feed hinzu"""
    if 'activity_feed' not in st.session_state:
        st.session_state.activity_feed = []
    
    activity = {
        'type': activity_type,
        'details': details,
        'timestamp': time.time()
    }
    
    st.session_state.activity_feed.insert(0, activity)  # Neuste zuerst
    
    # Beschränke Feed auf die letzten 50 Aktivitäten
    if len(st.session_state.activity_feed) > 50:
        st.session_state.activity_feed.pop()

def get_activity_message(activity):
    """Generiert eine formatierte Nachricht für eine Aktivität"""
    timestamp = datetime.fromtimestamp(activity['timestamp']).strftime('%H:%M')
    
    if activity['type'] == 'drink':
        person = activity['details']['person']
        drink = activity['details']['drink']
        bac = activity['details']['bac']
        return f"🕒 {timestamp} | 🎉 {person} trinkt {drink}! (Aktuell: {format_bac(bac)}‰)"
    
    elif activity['type'] == 'join':
        person = activity['details']['person']
        return f"🕒 {timestamp} | 👋 {person} ist der Party beigetreten!"
    
    elif activity['type'] == 'milestone':
        return f"🕒 {timestamp} | 🏆 {activity['details']['message']}"
        
def show_activity_feed():
    """Zeigt den Activity Feed an"""
    st.markdown("### 🎯 Live Activity Feed")
    
    if 'activity_feed' not in st.session_state or not st.session_state.activity_feed:
        st.info("Noch keine Aktivitäten zu zeigen... Die Party kann beginnen! 🎉")
        return
    
    feed_container = st.container()
    with feed_container:
        for activity in st.session_state.activity_feed:
            message = get_activity_message(activity)
            if activity['type'] == 'milestone':
                st.success(message)
            elif activity['type'] == 'join':
                st.info(message)
            else:
                st.write(message)

def check_party_milestones():
    """Prüft und fügt Party-weite Meilensteine hinzu"""
    total_drinks = sum(len(p['drinks']) for p in st.session_state.participants.values())
    
    if total_drinks in [50, 100, 150, 200]:
        add_activity('milestone', {
            'message': f"🎊 Die Party hat {total_drinks} Getränke erreicht!"
        })

def remove_drink(participant_name, drink_index):
    """Entfernt ein Getränk von einem Teilnehmer"""
    if participant_name in st.session_state.participants:
        if 0 <= drink_index < len(st.session_state.participants[participant_name]['drinks']):
            st.session_state.participants[participant_name]['drinks'].pop(drink_index)
            save_data()
            return True
    return False

def upload_memory(file, title):
    """Lädt ein Bild oder Video zu Cloudinary hoch"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        public_id = f"party_memories/{timestamp}_{title}"
        
        result = cloudinary.uploader.upload(file,
            public_id=public_id,
            resource_type="auto"
        )
        return result['url']
    except Exception as e:
        st.error(f"Upload fehlgeschlagen: {e}")
        return None

def get_memories():
    """Holt alle gespeicherten Memories von Cloudinary"""
    try:
        result = cloudinary.api.resources(
            type="upload",
            prefix="party_memories/",
            max_results=500,
            resource_type="auto"
        )
        memories = []
        for resource in result['resources']:
            parts = resource['public_id'].split('/')[-1].split('_')
            timestamp = parts[0]
            title = '_'.join(parts[1:])
            
            memories.append({
                'url': resource['url'],
                'title': title,
                'timestamp': timestamp,
                'resource_type': resource['resource_type']
            })
        return sorted(memories, key=lambda x: x['timestamp'], reverse=True)
    except Exception as e:
        st.error(f"Abruf der Memories fehlgeschlagen: {e}")
        return []

def reset_party(password):
    """Reset der Party mit Passwortschutz"""
    RESET_PASSWORD = "Silvester2024"
    if password == RESET_PASSWORD:
        if os.path.exists('party_data.json'):
            os.remove('party_data.json')
        st.session_state.participants = {}
        st.session_state.party_start_time = time.time()
        st.session_state.data_loaded = False
        return True
    return False

def get_status_emoji(status, gender):
    """Gibt das passende Status-Emoji zurück"""
    if status == "Vergeben":
        return "🔴"
    elif status == "Single":
        return "🟢"
    else:  # Unentschlossen
        return "🤷‍♂️" if gender == "männlich" else "🤷‍♀️"

def format_bac(bac):
    """Formatiert den Promillewert im deutschen Format"""
    return f"{bac:.1f}".replace('.', ',')

def calculate_bac(weight, gender, drinks):
    """
    Berechnet den Blutalkoholspiegel (BAC) nach der Widmark-Formel
    """
    if not drinks:
        return 0.0
    
    current_time = time.time()
    total_alcohol = 0
    
    r = 0.7 if gender == 'männlich' else 0.6
    
    for drink in drinks:
        hours_passed = (current_time - drink['time']) / 3600
        
        if drink.get('custom', False):
            pure_alcohol = drink['volume'] * drink['alcohol_content'] * 0.789
        else:
            drink_info = DRINKS[drink['type']]
            pure_alcohol = drink_info['volume'] * drink_info['alcohol_content'] * 0.789
            
        total_alcohol += pure_alcohol

    bac = (total_alcohol * 0.8) / (weight * r)
    
    if drinks:
        hours_since_first_drink = (current_time - drinks[0]['time']) / 3600
        total_elimination = 0.15 * hours_since_first_drink
        final_bac = max(0, bac - total_elimination)
    else:
        final_bac = bac

    return round(final_bac, 3)

def get_participant_rankings():
    """Erstellt eine nach Promille sortierte Rangliste der Teilnehmer"""
    if not st.session_state.participants:
        return []
    
    participant_data = []
    for name, person in st.session_state.participants.items():
        bac = calculate_bac(person['weight'], person['gender'], person['drinks'])
        gender_icon = "🙋‍♂️" if person['gender'] == 'männlich' else "🙋‍♀️"
        status_icon = get_status_emoji(person['status'], person['gender'])
        
        participant_data.append({
            'name': name,
            'bac': bac,
            'drinks': len(person['drinks']),
            'gender_icon': gender_icon,
            'status_icon': status_icon,
            'instagram': person.get('instagram', '')
        })
    
    return sorted(participant_data, key=lambda x: x['bac'], reverse=True)

# Cache leeren
st.cache_data.clear()

# Load data if not already loaded
if not st.session_state.data_loaded:
    load_data()
    st.session_state.data_loaded = True

# Hauptnavigation am Anfang der App
st.title("🎉 Silvester Party 2024")

# Navigation als Buttons
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("📊", key="nav_dashboard", help="Dashboard"):
        st.session_state.current_page = "Dashboard"
with col2:
    if st.button("👥", key="nav_participants", help="Teilnehmer"):
        st.session_state.current_page = "Teilnehmer"
with col3:
    if st.button("🍺", key="nav_drinks", help="Getränke"):
        st.session_state.current_page = "Getränke"
with col4:
    if st.button("📸", key="nav_memories", help="Memories"):
        st.session_state.current_page = "Memories"

st.divider()

# Seiteninhalt basierend auf Auswahl
if st.session_state.current_page == "Dashboard":
    main_col, feed_col = st.columns([2, 1])
    
    with main_col:
        st.header("Dashboard")
        
        # Party Statistiken
        col1, col2, col3, col4 = st.columns(4)
        
        duration_mins = int((time.time() - st.session_state.party_start_time) / 60)
        if duration_mins < 60:
            duration = f"{duration_mins} Minuten"
        else:
            hours = duration_mins // 60
            minutes = duration_mins % 60
            duration = f"{hours}h {minutes}min"

        with col1:
            st.metric("Party Dauer", duration)
        
        total_drinks = sum(len(p.get('drinks', [])) for p in st.session_state.participants.values())
        with col2:
            st.metric("Getränke gesamt", total_drinks)
        
        genders = {'männlich': 0, 'weiblich': 0}
        for p in st.session_state.participants.values():
            genders[p['gender']] += 1
        gender_stats = f"🙋‍♀️ {genders['weiblich']}, 🙋‍♂️ {genders['männlich']}"
        with col3:
            st.metric("Geschlechter", gender_stats)

        if st.session_state.participants:
            total_bac = sum(calculate_bac(p['weight'], p['gender'], p['drinks']) 
                           for p in st.session_state.participants.values())
            avg_bac = total_bac / len(st.session_state.participants)
        else:
            avg_bac = 0
        with col4:
            st.metric("Ø Promille", f"{format_bac(avg_bac)}‰")

        # Rankings
        st.subheader("🏆 Party Rankings")
        
        rankings = get_participant_rankings()
        
        if rankings:
            st.write("### 🔝 Party Champions")
            for idx, participant in enumerate(rankings[:3], 1):
                symbol = RANKING_SYMBOLS.get(idx, "")
                col1, col2 = st.columns([3, 1])
                with col1:
                    title = f"{symbol} {participant['name']} {participant['gender_icon']} {participant['status_icon']}"
                    if participant['instagram']:
                        title += f" [📸]({participant['instagram']})"
                    st.metric(
                        title,
                        f"{format_bac(participant['bac'])}‰",
                        f"↑ {participant['drinks']} Drinks"
                    )
            
            st.write("### 📊 Komplette Rangliste")
            for participant in rankings:
                with st.expander(
                    f"{participant['name']} - {format_bac(participant['bac'])}‰ "
                    f"({participant['drinks']} Drinks)"
                ):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"Status: {participant['gender_icon']} {participant['status_icon']}")
                    with col2:
                        if participant['instagram']:
                            st.write(f"Instagram: [Zum Profil]({participant['instagram']})")
        else:
            st.info("Noch keine Teilnehmer auf der Party.")
    
    with feed_col:
        show_activity_feed()
        with st.expander("Feed Einstellungen"):
            if st.checkbox("Auto-Refresh", value=True):
                time.sleep(30)
                st.rerun()

elif st.session_state.current_page == "Teilnehmer":
    st.header("👥 Teilnehmer hinzufügen")
    
    with st.form(key="new_participant_form"):
        name = st.text_input("Name")
        instagram = st.text_input("Instagram Profil URL (optional)")
        col1, col2 = st.columns(2)
        with col1:
            weight = st.number_input("Gewicht (kg)", 
                                   min_value=40, 
                                   max_value=200, 
                                   value=70)
            gender = st.selectbox("Geschlecht", 
                                ["männlich", "weiblich"])
        with col2:
            status = st.selectbox("Beziehungsstatus", STATUS_OPTIONS)
        
        if st.form_submit_button("Teilnehmer hinzufügen 👋"):
            if name.strip() == "":
                st.error("Bitte gib einen Namen ein!")
            elif name in st.session_state.participants:
                st.error("Teilnehmer existiert bereits!")
            else:
                st.session_state.participants[name] = {
                    'weight': weight,
                    'gender': gender,
                    'status': status,
                    'instagram': instagram,
                    'drinks': []
                }
                add_activity('join', {
                    'person': name
                })
                save_data()
                st.success(f"Willkommen auf der Party, {name}! 🎉")
                st.balloons()

    if st.session_state.participants:
        st.header("Teilnehmerliste")
        for name, data in st.session_state.participants.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                gender_icon = "🙋‍♂️" if data['gender'] == 'männlich' else "🙋‍♀️"
                status_icon = get_status_emoji(data['status'], data['gender'])
                display_text = f"{name} {gender_icon} {status_icon}"
                if data['instagram']:
                    display_text += f" [📸]({data['instagram']})"
                st.write(display_text)
            with col2:
                if st.button("❌", key=f"remove_{name}"):
                    del st.session_state.participants[name]
                    save_data()
                    st.success(f"{name} wurde von der Party entfernt.")
                    st.rerun()

# Im Getränke-Tab den alten Scanner-Code ersetzen:
elif st.session_state.current_page == "Getränke":
    st.header("🍺 Getränke verwalten")
    
    if not st.session_state.participants:
        st.warning("Füge zuerst Teilnehmer hinzu!")
    else:
        tab1, tab2, tab3 = st.tabs(["Standard Getränk", "Custom Getränk", "Getränke verwalten"])
        
        # Änderung im Getränke-Tab, im "Standard Getränk" Tab:
        with tab1:
            st.subheader("Standard Getränk hinzufügen")
            name = st.selectbox("Teilnehmer auswählen", 
                            list(st.session_state.participants.keys()),
                            key="add_standard_drink_participant")
            
            # Getränkeauswahl mit Tooltip
            col1, col2 = st.columns([3,1])
            with col1:
                drink_type = st.selectbox("Getränk auswählen", 
                                        list(DRINKS.keys())[:-1])  # Ohne Custom Option
            with col2:
                drink_info = DRINKS[drink_type]
                st.info(f"""
                ℹ️ **Standard Werte:**
                - Menge: {drink_info['volume']}ml
                - Alkohol: {drink_info['alcohol_content']*100:.1f}%
                """)

        with tab2:
            st.subheader("Custom Getränk hinzufügen")
            name = st.selectbox("Teilnehmer auswählen", 
                              list(st.session_state.participants.keys()),
                              key="add_custom_drink_participant")
            
            col1, col2 = st.columns(2)
            
            with col1:
                mobile_barcode_scanner()  # Neue Scanner-Funktion
                
            with col2:
                st.write("##### Option 2: Aus Vorschlägen wählen")
                suggested_drink = st.selectbox(
                    "Beliebte Getränke",
                    ["Bitte wählen..."] + list(SUGGESTED_DRINKS.keys())
                )
                
                if suggested_drink != "Bitte wählen...":
                    drink_info = SUGGESTED_DRINKS[suggested_drink]
                    st.info(f"""
                    **{suggested_drink}**
                    - Alkoholgehalt: {drink_info['alcohol_content']*100:.1f}%
                    - Menge: {drink_info['volume']}ml
                    """)
            
            # Im Custom Getränk Tab, vor den Details des Getränks:
            st.write("##### Getränkekategorie")
            drink_category = st.selectbox(
                "Kategorie",
                list(DRINK_CATEGORIES.keys()),
                key="drink_category"
            )
            drink_subcategory = st.selectbox(
                "Art",
                DRINK_CATEGORIES[drink_category],
                key="drink_subcategory"
            )

            # Vorschlagswerte basierend auf Kategorie
            if drink_category == "Bier 🍺":
                suggested_volume = 500
                suggested_alcohol = 5.0
            elif drink_category == "Wein 🍷":
                suggested_volume = 200
                suggested_alcohol = 12.0
            else:  # Schnaps
                suggested_volume = 40
                suggested_alcohol = 40.0

            st.write("##### Details des Getränks")
            col3, col4 = st.columns(2)
            with col3:
                if st.session_state.barcode_result:
                    default_name = st.session_state.barcode_result['name']
                    default_volume = st.session_state.barcode_result['volume'] or 500
                    default_alcohol = (st.session_state.barcode_result['alcohol_content'] or 0.05) * 100
                elif suggested_drink != "Bitte wählen...":
                    default_name = suggested_drink
                    default_volume = SUGGESTED_DRINKS[suggested_drink]['volume']
                    default_alcohol = SUGGESTED_DRINKS[suggested_drink]['alcohol_content'] * 100
                else:
                    default_name = ""
                    default_volume = 500
                    default_alcohol = 5.0
                
                custom_name = st.text_input(
                    "Name des Getränks", 
                    value=f"{drink_subcategory}: {default_name}" if default_name else drink_subcategory
                )
                custom_volume = st.number_input(
                    "Menge (ml)", 
                    min_value=1, 
                    max_value=1000,
                    value=int(default_volume or suggested_volume)
                )
            with col4:
                custom_alcohol = st.number_input("Alkoholgehalt (%)", 
                                               min_value=0.0, 
                                               max_value=99.9,
                                               value=float(default_alcohol or suggested_alcohol),
                                               step=0.1
                )
                
            if st.button("Custom Getränk eintragen"):
                if not custom_name:
                    st.error("Bitte gib einen Namen für das Getränk ein!")
                else:
                    custom_drink_type = f"{drink_category} - {custom_name}"
                    st.session_state.participants[name]['drinks'].append({
                        'type': custom_drink_type,
                        'category': drink_category,
                        'subcategory': drink_subcategory,
                        'time': time.time(),
                        'custom': True,
                        'alcohol_content': custom_alcohol / 100,
                        'volume': custom_volume
                    })
                    person = st.session_state.participants[name]
                    current_bac = calculate_bac(person['weight'], person['gender'], person['drinks'])
                    add_activity('drink', {
                        'person': name,
                        'drink': custom_drink_type,
                        'bac': current_bac
                    })
                    check_party_milestones()
                    save_data()
                    st.success(f"Custom Getränk wurde eingetragen! Aktueller Promillewert: {format_bac(current_bac)}‰ 🍻")
                    st.balloons()
                    st.session_state.barcode_result = None

        with tab3:
            st.subheader("Getränke verwalten")
            selected_participant = st.selectbox(
                "Teilnehmer auswählen",
                list(st.session_state.participants.keys()),
                key="manage_drinks_participant"
            )
            
            if selected_participant:
                person = st.session_state.participants[selected_participant]
                drinks = person['drinks']
                
                # In der Getränkeverwaltung (tab3)
                if drinks:
                    current_bac = calculate_bac(person['weight'], person['gender'], drinks)
                    st.info(f"Aktueller Promillewert: {format_bac(current_bac)}‰")
                    
                    # Gruppiere Getränke nach Kategorie
                    drinks_by_category = {}
                    for idx, drink in enumerate(drinks):
                        category = drink.get('category', "Standard Getränke")
                        if category not in drinks_by_category:
                            drinks_by_category[category] = []
                        drinks_by_category[category].append((idx, drink))
                    
                    # Zeige Getränke nach Kategorie gruppiert
                    for category, category_drinks in drinks_by_category.items():
                        with st.expander(f"{category} ({len(category_drinks)} Getränke)"):
                            for idx, drink in category_drinks:
                                col1, col2, col3, col4 = st.columns([2, 1, 2, 1])
                                with col1:
                                    st.write(f"{drink['type']}")
                                with col2:
                                    if 'subcategory' in drink:
                                        st.caption(drink['subcategory'])
                                with col3:
                                    drink_time = datetime.fromtimestamp(drink['time'])
                                    st.write(f"🕒 {drink_time.strftime('%H:%M Uhr')}")
                                with col4:
                                    if st.button("❌", key=f"remove_drink_{idx}"):
                                        if remove_drink(selected_participant, idx):
                                            st.success("Getränk wurde entfernt!")
                                            updated_bac = calculate_bac(
                                                person['weight'], 
                                                person['gender'], 
                                                person['drinks']
                                            )
                                            st.info(f"Neuer Promillewert: {format_bac(updated_bac)}‰")
                                            st.rerun()
                else:
                    st.info("Noch keine Getränke eingetragen.")

elif st.session_state.current_page == "Memories":
    st.header("📸 Party Memories")
    
    with st.expander("➕ Neue Erinnerung hochladen", expanded=False):
        uploaded_file = st.file_uploader(
            "Wähle ein Foto oder Video", 
            type=['png', 'jpg', 'jpeg', 'mp4', 'gif']
        )
        
        if uploaded_file:
            memory_title = st.text_input("Titel für die Erinnerung")
            
            if st.button("Speichern 💾"):
                if memory_title:
                    if upload_memory(uploaded_file, memory_title):
                        st.success("Erinnerung gespeichert! 🎉")
                        st.balloons()
                else:
                    st.error("Bitte gib einen Titel ein!")

    st.subheader("🖼️ Party Galerie")
    
    memories = get_memories()
    if memories:
        cols = st.columns(3)
        for idx, memory in enumerate(memories):
            with cols[idx % 3]:
                if memory['resource_type'] == 'video':
                    st.video(memory['url'])
                else:
                    st.image(memory['url'])
                st.caption(f"📍 {memory['title']}")
    else:
        st.info("Noch keine Erinnerungen hochgeladen!")

# Admin-Bereich mit Passwortschutz
st.markdown("---")
with st.expander("🔑 Admin-Bereich"):
    st.warning("⚠️ Dieser Bereich ist nur für Administratoren!")
    reset_password = st.text_input("Admin-Passwort:", type="password")
    if st.button("🔄 Party zurücksetzen", key="reset_button"):
        if reset_password:
            if reset_party(reset_password):
                st.session_state.activity_feed = []
                st.success("Party wurde erfolgreich zurückgesetzt!")
                with st.spinner("Neustart..."):
                    time.sleep(2)
                st.rerun()
            else:
                st.error("Zugriff verweigert: Falsches Passwort!")
        else:
            st.error("Bitte gib das Admin-Passwort ein!")
            
# Sicherheitshinweis am Ende jeder Seite
st.markdown("---")
st.warning("""
⚠️ **Wichtiger Hinweis:**
- Diese App dient nur der Unterhaltung und liefert keine medizinisch genauen Werte.
- Fahre nie unter Alkoholeinfluss - auch nicht am nächsten Morgen ohne Überprüfung.
- Trinke verantwortungsvoll und kenne deine Grenzen.

🚨 **Im Notfall: Notruf 112** - Zögere nicht, Hilfe zu holen! 🚨
""")