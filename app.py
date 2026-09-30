import streamlit as st
import requests
import pandas as pd
import urllib.parse
import re

st.set_page_config(page_title="Pizzeria Lead Finder", page_icon="🍕", layout="wide")

st.title("🍕 Pizzeria Lead Finder & Sales CRM")
st.write("Scandaglia il web per trovare pizzerie senza sito web, con menu PDF o dipendenti da Glovo/JustEat.")

st.sidebar.header("🔍 Parametri di Ricerca")
citta = st.sidebar.text_input("Città da scandagliare", value="Milano")
avvia_scansione = st.sidebar.button("Avvia Scansione Lead")

def cerca_pizzerie(nome_citta):
    url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:25];
    area[name="{nome_citta}"][admin_level=8]->.searchArea;
    (
      node["cuisine"="pizza"](area.searchArea);
      way["cuisine"="pizza"](area.searchArea);
      node["amenity"="restaurant"]["name"~"Pizzeria",i](area.searchArea);
      way["amenity"="restaurant"]["name"~"Pizzeria",i](area.searchArea);
    );
    out center tags;
    """
    try:
        res = requests.get(url, params={'data': query}, timeout=30)
        data = res.json()
        pizzerie = []
        for item in data.get('elements', []):
            tags = item.get('tags', {})
            nome = tags.get('name', 'Pizzeria senza nome')
            sito = tags.get('website', '')
            telefono = tags.get('phone', tags.get('contact:phone', ''))
            strada = tags.get('addr:street', '')
            civico = tags.get('addr:housenumber', '')
            indirizzo = f"{strada} {civico}".strip() or "Indirizzo non specificato"
            pizzerie.append({
                'Nome': nome,
                'Sito_Web': sito,
                'Telefono': telefono,
                'Indirizzo': indirizzo
            })
        return pizzerie
    except Exception as e:
        st.error(f"Errore durante il recupero dati: {e}")
        return []

def analizza_sito(url):
    if not url:
        return "🔴 Nessun Sito Web", "Alta (Nessuna presenza proprietaria)", "Senza Sito"
    url_lower = url.lower()
    if any(delivery in url_lower for delivery in ['glovoapp', 'just-eat', 'deliveroo', 'ubereats']):
        return "🔵 Solo Delivery (Glovo/JustEat)", "Alta (Paga altissime commissioni)", "Delivery"
    if any(social in url_lower for social in ['facebook.com', 'instagram.com']):
        return "🟠 Solo Profilo Social", "Media (Usa FB/IG al posto del sito)", "Social"
    if url_lower.endswith('.pdf') or 'pdf' in url_lower:
        return "🟡 Menu solo in PDF", "Alta (Menu illeggibile da smartphone)", "PDF"
    try:
        response = requests.get(url, timeout=4, headers={'User-Agent': 'Mozilla/5.0'})
        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' in content_type:
            return "🟡 Menu solo in PDF", "Alta (Menu illeggibile da smartphone)", "PDF"
        return "🟢 Sito Proprietario Presente", "Bassa (Ha già un sito)", "OK"
    except:
        return "⚠️ Sito Non Funzionante / Errore HTTP", "Alta (Sito rotto o non sicuro)", "Sito Rotto"

def pulisci_telefono(phone):
    cleaned = re.sub(r'\D', '', str(phone))
    if cleaned.startswith('0'):
        cleaned = '39' + cleaned
    elif not cleaned.startswith('39') and len(cleaned) == 10:
        cleaned = '39' + cleaned
    return cleaned

if avvia_scansione:
    with st.spinner(f"Scandagliamento in corso a {citta}..."):
        risultati = cerca_pizzerie(citta)
        if risultati:
            st.success(f"Trovate {len(risultati)} pizzerie! Analisi dei siti in corso...")
            lead_data = []
            progress_bar = st.progress(0)
            for i, p in enumerate(risultati):
                stato_sito, opportunita, codice_stato = analizza_sito(p['Sito_Web'])
                tel_clean = pulisci_telefono(p['Telefono'])
                msg_pitch = f"Ciao! Ho visto la scheda di {p['Nome']} a {citta}. "
                if codice_stato == "Senza Sito":
                    msg_pitch += "Ho notato che non avete un sito web ufficiale dove mostrare il vostro menu. Realizziamo siti web veloci per pizzerie per aumentare gli ordini diretti. Posso inviarvi un esempio gratuito?"
                elif codice_stato == "PDF":
                    msg_pitch += "Ho notato che il vostro menu online è in formato PDF, spesso difficile da leggere da telefono. Creiamo menu digitali interattivi e veloci. Vi andrebbe di dare un'occhiata?"
                elif codice_stato == "Delivery":
                    msg_pitch += "Ho notato che il vostro link porta a piattaforme di delivery che trattengono commissioni alte. Vi aiutiamo a ricevere ordini diretti senza commissioni di terzi. Posso darvi due info?"
                else:
                    msg_pitch += "Ci occupiamo di aggiornamento e restyling di siti web per pizzerie ed asporto. Vi andrebbe di valutare una proposta di restyling?"
                
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
                progress_bar.progress((i + 1) / len(risultati))
            
            df = pd.DataFrame(lead_data)
            st.subheader("📊 Risultati Analisi Lead")
            filtro = st.multiselect("Filtra per problema:", options=df["Diagnostica Sito"].unique(), default=df["Diagnostica Sito"].unique())
            df_filtrato = df[df["Diagnostica Sito"].isin(filtro)]
            st.dataframe(df_filtrato[["Pizzeria", "Diagnostica Sito", "Opportunità Commerciale", "Telefono", "Indirizzo", "Sito Attuale"]], use_container_width=True)
            
            st.subheader("📱 Azioni Rapide di Contatto")
            for index, row in df_filtrato.iterrows():
                if row["Contatta su WhatsApp"]:
                    col1, col2, col3 = st.columns([2, 3, 2])
                    col1.write(f"**{row['Pizzeria']}** ({row['Diagnostica Sito']})")
                    col2.write(f"📍 {row['Indirizzo']}")
                    col3.markdown(f"[💬 Invia Messaggio WhatsApp]({row['Contatta su WhatsApp']})", unsafe_allow_html=True)
                    st.divider()

            csv = df_filtrato.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Scarica Lead in CSV / Excel", data=csv, file_name=f"lead_pizzerie_{citta}.csv", mime="text/csv")
        else:
            st.warning("Nessuna pizzeria trovata in questa città.")
