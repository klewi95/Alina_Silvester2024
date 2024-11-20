# Neue Imports am Anfang der Datei
from streamlit_webrtc import webrtc_streamer
import cv2
from pyzbar.pyzbar import decode
import numpy as np
import requests

# Konstanten für die Getränke anpassen
DRINKS = {
    "Bier 🍺": {"alcohol_content": 0.05, "volume": 500},
    "Wein 🍷": {"alcohol_content": 0.12, "volume": 200},
    "Schnaps 🥃": {"alcohol_content": 0.40, "volume": 20},
    "Custom 🍾": {"alcohol_content": None, "volume": None}
}

# OpenFoodFacts API Funktion
def get_drink_info_from_barcode(barcode):
    """Ruft Getränkeinformationen von OpenFoodFacts API ab"""
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
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
    return None

# Barcode Scanner Callback
def handle_barcode_scan(frame):
    """Verarbeitet Webcam-Frames und erkennt Barcodes"""
    img = frame.to_ndarray(format="bgr24")
    barcodes = decode(img)
    
    for barcode in barcodes:
        # Zeichne Rechteck um erkannten Barcode
        points = barcode.polygon
        if len(points) == 4:
            pts = np.array(points, np.int32)
            pts = pts.reshape((-1, 1, 2))
            cv2.polylines(img, [pts], True, (0, 255, 0), 2)
        
        # Decodiere Barcode-Daten
        barcode_data = barcode.data.decode('utf-8')
        return img, barcode_data
    
    return img, None

# Angepasster Getränke-Tab-Code
if st.session_state.current_page == "Getränke":
    st.header("🍺 Getränke verwalten")
    
    if not st.session_state.participants:
        st.warning("Füge zuerst Teilnehmer hinzu!")
    else:
        tab1, tab2, tab3 = st.tabs(["Standard Getränk", "Custom Getränk", "Getränke verwalten"])
        
        with tab1:
            st.subheader("Standard Getränk hinzufügen")
            name = st.selectbox("Teilnehmer auswählen", 
                              list(st.session_state.participants.keys()),
                              key="add_standard_drink_participant")
            
            standard_drinks = {k: v for k, v in DRINKS.items() if k != "Custom 🍾"}
            drink_type = st.selectbox("Getränk auswählen", 
                                    list(standard_drinks.keys()))
            
            if st.button("Standard Getränk eintragen"):
                st.session_state.participants[name]['drinks'].append({
                    'type': drink_type,
                    'time': time.time(),
                    'custom': False,
                    'alcohol_content': DRINKS[drink_type]['alcohol_content'],
                    'volume': DRINKS[drink_type]['volume']
                })
                person = st.session_state.participants[name]
                current_bac = calculate_bac(person['weight'], person['gender'], person['drinks'])
                add_activity('drink', {
                    'person': name,
                    'drink': drink_type,
                    'bac': current_bac
                })
                check_party_milestones()
                save_data()
                st.success(f"Getränk wurde eingetragen! Aktueller Promillewert: {format_bac(current_bac)}‰ 🍻")
                st.balloons()

        with tab2:
            st.subheader("Custom Getränk hinzufügen")
            name = st.selectbox("Teilnehmer auswählen", 
                              list(st.session_state.participants.keys()),
                              key="add_custom_drink_participant")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("##### Option 1: Barcode scannen")
                # Barcode Scanner
                barcode_data = None
                if 'barcode_result' not in st.session_state:
                    st.session_state.barcode_result = None
                
                webrtc_ctx = webrtc_streamer(
                    key="drink-scanner",
                    video_processor_factory=handle_barcode_scan,
                    media_stream_constraints={"video": True, "audio": False},
                )
                
                if webrtc_ctx.video_processor:
                    if webrtc_ctx.video_processor.barcode_data:
                        barcode_data = webrtc_ctx.video_processor.barcode_data
                        drink_info = get_drink_info_from_barcode(barcode_data)
                        if drink_info:
                            st.session_state.barcode_result = drink_info
                            st.success(f"Getränk erkannt: {drink_info['name']}")
                            if drink_info['image_url']:
                                st.image(drink_info['image_url'], width=100)
            
            with col2:
                st.write("##### Option 2: Manuell eingeben")
                custom_name = st.text_input("Getränkename", 
                                          value=st.session_state.barcode_result['name'] if st.session_state.barcode_result else "")
                custom_volume = st.number_input("Menge (ml)", 
                                              min_value=1, 
                                              max_value=1000,
                                              value=st.session_state.barcode_result['volume'] if st.session_state.barcode_result and st.session_state.barcode_result['volume'] else 500)
                custom_alcohol = st.number_input("Alkoholgehalt (%)", 
                                               min_value=0.0, 
                                               max_value=99.9,
                                               value=st.session_state.barcode_result['alcohol_content']*100 if st.session_state.barcode_result and st.session_state.barcode_result['alcohol_content'] else 5.0,
                                               step=0.1)
            
            if st.button("Custom Getränk eintragen"):
                custom_drink_type = f"Custom: {custom_name}"
                st.session_state.participants[name]['drinks'].append({
                    'type': custom_drink_type,
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
                # Reset Barcode Result
                st.session_state.barcode_result = None