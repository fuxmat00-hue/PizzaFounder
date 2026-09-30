import streamlit as st
import requests
import pandas as pd
import urllib.parse
import re
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Pizza Lead Finder", page_icon="🍕", layout="wide")

st.title("🍕 Pizzeria Lead Finder & Sales CRM")
st.write("Scandaglia il territorio per individuare pizzerie senza sito web, con menu in PDF o dipendenti da Glovo/JustEat.")

st.sidebar.header("🔍 Parametri di Ricerca")
citta = st.sidebar.text_input("Città da scandagliare", value="Padova")
avvia_scansione = st.sidebar.button("Avvia Scansione Lead")

def cerca_pizzerie_nominatim(nome_citta):
    headers = {
        'User-Agent': 'PizzaLeadFinderApp/4.0 (contact@leadfinder.it)',
        'Accept-Language': 'it-IT,it;q=0.9'
    }
    
    # Termini di ricerca per coprire ogni tipologia di pizzeria nella città
    query_list = [
        f"pizzeria {nome_citta}",
        f"pizzeria d'asporto {nome_citta}",
        f"ristorante pizzeria {nome_citta}"
    ]
    
    pizzerie = []
    ids_visti = set()
    nomi_visti = set()

    for q in query_list:
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': q,
                'format': 'json',
                'addressdetails': 1,
                'extratags': 1,
                'limit': 50
            }
            res = requests.get(url, params=params, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                for item in data:
                    osm_id = item.get('osm_id')
                    if osm_id in ids_visti:
                        continue
                    
                    display_name = item.get('display_name', '')
                    nome = item.get('name') or display_name.split(',')[0]
                    if not nome or nome.lower() in nomi_visti:
                        continue

                    extratags = item.get('extratags', {})
                    address = item.get('address', {})
                    
                    # Estrazione Sito e Telefono dai metadati OSM
                    sito = extratags.get('website') or extratags.get('contact:website') or extratags.get('url') or ''
                    telefono = extratags.get('phone') or extratags.get('contact:phone') or extratags.get('phone:mobile') or ''
                    
                    # Costruzione Indirizzo
                    strada = address.get('road', '')
                    civico = address.get('house_number', '')
                    indirizzo = f"{strada} {civico}".strip() if strada else address.get('suburb', address.get('city', nome_citta))

                    ids_visti.add(osm_id)
                    nomi_visti.add(nome.lower())
                    
                    pizzerie.append({
                        'Nome': nome,
                        'Sito_Web': sito,
                        'Telefono': telefono,
                        'Indirizzo': indirizzo
                    })
        except Exception:
            continue

    return pizzerie

def analizza_sito(url):
    if not url or pd.isna(url) or str(url).strip() == '':
        return "🔴 Nessun Sito Web", "Alta (Nessuna presenza proprietaria)", "Senza Sito"
    
    url_str = str(url).strip()
    url_lower = url_str.lower()
    
    if any(delivery in url_lower for delivery in ['glovoapp', 'just-eat', 'deliveroo', 'ubereats', 'takeaway']):
        return "🔵 Solo Delivery (Glovo/JustEat)", "Alta (Paga commissioni 20-30%)", "Delivery"
    if any(social in url_lower for social in ['facebook.com', 'instagram.com', 'fb.com']):
        return "🟠 Solo Profilo Social", "Media (Usa FB/IG al posto del sito)", "Social"
    if url_lower.endswith('.pdf') or 'pdf' in url_lower:
        return "🟡 Menu solo in PDF", "Alta (Menu illeggibile da smartphone)", "PDF"
        
    try:
        target_url = url_str if url_str.startswith(('http://', 'https://')) else f"http://{url_str}"
        response = requests.get(target_url, timeout=3, headers={'User-Agent': 'Mozilla/5.0'})
        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' in content_type:
            return "🟡 Menu solo in PDF", "Alta (Menu illeggibile da smartphone)", "PDF"
        return "🟢 Sito Proprietario Presente", "Bassa (Ha già un sito)", "OK"
    except:
        return "⚠️️ Sito Non Funzionante / Errore HTTP", "Alta (Sito non raggiungibile)", "Sito Rotto"

def pulisci_telefono(phone):
    if not phone or pd.isna(phone):
        return ""
    cleaned = re.sub(r'\D', '', str(phone))
    if not cleaned:
        return ""
    if cleaned.startswith('39'):
        return cleaned
    if cleaned.startswith('0'):
        return '39' + cleaned
    if len(cleaned) == 10 and cleaned.startswith('3'):
        return '39' + cleaned
    return cleaned

if avvia_scansione:
    with st.spinner(f"Scandagliamento veloce in corso per '{citta}'..."):
        risultati = cerca_pizzerie_nominatim(citta)
        
        if risultati:
            st.success(f"🎯 Trovate {len(risultati)} pizzerie a {citta}! Analisi dei siti in corso...")
            
            # Analisi dei siti in parallelo ultra-veloce
            with ThreadPoolExecutor(max_workers=10) as executor:
                siti = [p['Sito_Web'] for p in risultati]
                diagnostiche = list(executor.map(analizza_sito, siti))
            
            lead_data = []
            for i, p in enumerate(risultati):
                stato_sito, opportunita, codice_stato = diagnostiche[i]
                tel_clean = pulisci_telefono(p['Telefono'])
                
                # Messaggio Pitch personalizzato WhatsApp
                msg_pitch = f"Ciao! Ho visto la scheda di {p['Nome']} a {citta}. "
                if codice_stato == "Senza Sito":
                    msg_pitch += "Ho notato che non avete un sito web ufficiale per i vostri ordini. Realizziamo siti veloci per pizzerie per aumentare i clienti diretti. Posso inviarvi un esempio gratuito?"
                elif codice_stato == "PDF":
                    msg_pitch += "Ho visto che il vostro menu online è in formato PDF, difficile da consultare da cellulare. Creiamo menu digitali interattivi. Vi andrebbe di dare un'occhiata?"
                elif codice_stato == "Delivery":
                    msg_pitch += "Ho notato che il vostro link porta a piattaforme di delivery che trattengono commissioni alte. Vi aiutiamo a ricevere ordini diretti senza commissioni. Posso darvi due info?"
                else:
                    msg_pitch += "Ci occupiamo di sviluppo e restyling di siti per pizzerie. Vi andrebbe di valutare una proposta di restyling?"
                
                wa_link = f"https://wa.me/{tel_clean}?text={urllib.parse.quote(msg_pitch)}" if tel_clean else ""
                
                lead_data.append({
                    "Pizzeria": p['Nome'],
                    "Diagnostica Sito": stato_sito,
                    "Opportunità Commerciale": opportunita,
                    "Indirizzo": p['Indirizzo'],
                    "Telefono": p['Telefono'],
                    "Sito Attuale": p['Sito_Web'],
                    "Contatta su WhatsApp": wa_link
                })
            
            df = pd.DataFrame(lead_data)
            
            st.subheader("📊 Risultati Analisi Lead")
            filtro = st.multiselect("Filtra per stato del sito:", options=df["Diagnostica Sito"].unique(), default=df["Diagnostica Sito"].unique())
            df_filtrato = df[df["Diagnostica Sito"].isin(filtro)]
            
            st.dataframe(df_filtrato[["Pizzeria", "Diagnostica Sito", "Opportunità Commerciale", "Telefono", "Indirizzo", "Sito Attuale"]], use_container_width=True)
            
            st.subheader("📱 Azioni Rapide di Contatto")
            count_wa = 0
            for index, row in df_filtrato.iterrows():
                if row["Contatta su WhatsApp"]:
                    count_wa += 1
                    col1, col2, col3 = st.columns([2, 3, 2])
                    col1.write(f"**{row['Pizzeria']}**  \n`{row['Diagnostica Sito']}`")
                    col2.write(f"📍 {row['Indirizzo']}  \n📞 {row['Telefono']}")
                    col3.markdown(f"[💬 **Invia Messaggio WhatsApp**]({row['Contatta su WhatsApp']})", unsafe_allow_html=True)
                    st.divider()
            
            if count_wa == 0:
                st.info("I numeri telefonici trovati nelle schede non includono un contatto diretto WhatsApp formattato.")

            csv = df_filtrato.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Scarica Lista Lead in CSV / Excel", data=csv, file_name=f"lead_pizzerie_{citta}.csv", mime="text/csv")
        else:
            st.warning(f"Nessun risultato trovato per '{citta}'. Prova a scrivere il nome della città (es. 'Padova' o 'Verona').")
