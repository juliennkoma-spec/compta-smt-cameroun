import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import io
from datetime import datetime

# --- CONFIGURATION ---
TVA_RATE = 0.1925 # Taux en vigueur au Cameroun (19.25%)

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# --- BASE DE DONNÉES ---
def get_connection():
    return sqlite3.connect('compta_smt_v2.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Table Utilisateurs
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)')
    # Table Trésorerie (SMT)
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, libelle TEXT, 
                  compte_treso TEXT, type TEXT, montant REAL, categorie TEXT)''')
    # Table Factures
    c.execute('''CREATE TABLE IF NOT EXISTS invoices 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, num_facture TEXT, 
                  libelle TEXT, quantite REAL, prix_unitaire REAL, montant_ht REAL, 
                  tva REAL, montant_ttc REAL)''')
    
    # Admin par défaut
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", ('admin', make_hashes('admin123'), 'admin'))
    conn.commit()
    conn.close()

# --- LOGIQUE DE CALCUL ---
def calculate_invoice(qty, pu):
    ht = qty * pu
    tva = ht * TVA_RATE
    ttc = ht + tva
    return ht, tva, ttc

# --- INTERFACE ---
def main():
    st.set_page_config(page_title="SMT OHADA PRO", layout="wide")
    init_db()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🛡️ SMT OHADA - Cameroun")
        user = st.sidebar.text_input("Utilisateur")
        pw = st.sidebar.text_input("Mot de passe", type='password')
        if st.sidebar.button("Se connecter"):
            conn = get_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE username=?', (user,))
            res = c.fetchone()
            if res and check_hashes(pw, res[2]):
                st.session_state.logged_in, st.session_state.user_id, st.session_state.username, st.session_state.role = True, res[0], res[1], res[3]
                st.rerun()
            else: st.error("Échec de connexion")
    
    else:
        st.sidebar.title(f"👤 {st.session_state.username}")
        menu = ["Saisie Trésorerie", "Saisie Factures", "Consultation & Modif", "États Financiers"]
        if st.session_state.role == 'admin': menu.append("Gestion Admin")
        choice = st.sidebar.selectbox("Navigation", menu)

        # 1. SAISIE TRÉSORERIE
        if choice == "Saisie Trésorerie":
            st.header("💵 Nouvelle Opération de Trésorerie")
            with st.form("form_treso"):
                col1, col2 = st.columns(2)
                date = col1.date_input("Date")
                libelle = col2.text_input("Libellé")
                moyen = col1.selectbox("Compte", ["571 Caisse", "521 Banque", "55 Paiement Électronique"])
                flux = col2.selectbox("Type", ["Entrée", "Sortie"])
                montant = col1.number_input("Montant (XAF)", min_value=0.0)
                cat = col2.selectbox("Catégorie", ["Ventes", "Achats", "Loyer", "Salaires", "Impôts", "Divers"])
                if st.form_submit_button("Enregistrer"):
                    conn = get_connection()
                    conn.execute("INSERT INTO transactions (user_id, date, libelle, compte_treso, type, montant, categorie) VALUES (?,?,?,?,?,?,?)",
                                 (st.session_state.user_id, str(date), libelle, moyen, flux, montant, cat))
                    conn.commit()
                    st.success("Enregistré !")

        # 2. SAISIE FACTURES
        elif choice == "Saisie Factures":
            st.header("📄 Enregistrement de Facture (Achat/Vente)")
            with st.form("form_inv"):
                col1, col2, col3 = st.columns(3)
                date_f = col1.date_input("Date Facture")
                num_f = col2.text_input("N° Facture")
                lib_f = col3.text_input("Désignation")
                qty = col1.number_input("Quantité", min_value=0.0, value=1.0)
                pu = col2.number_input("Prix Unitaire (HT)", min_value=0.0)
                
                ht, tva, ttc = calculate_invoice(qty, pu)
                col3.metric("Total TTC à payer", f"{ttc:,.0f} XAF")
                
                if st.form_submit_button("Générer la facture"):
                    conn = get_connection()
                    conn.execute("INSERT INTO invoices (user_id, date, num_facture, libelle, quantite, prix_unitaire, montant_ht, tva, montant_ttc) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user_id, str(date_f), num_f, lib_f, qty, pu, ht, tva, ttc))
                    conn.commit()
                    st.success(f"Facture {num_f} enregistrée (TVA 19.25% incluse)")

        # 3. CONSULTATION, MODIFICATION ET SUPPRESSION
        elif choice == "Consultation & Modif":
            st.header("🔍 Gestion des écritures")
            tab1, tab2 = st.tabs(["Trésorerie", "Factures"])
            
            with tab1:
                conn = get_connection()
                query = "SELECT * FROM transactions" if st.session_state.role == 'admin' else f"SELECT * FROM transactions WHERE user_id={st.session_state.user_id}"
                df_t = pd.read_sql(query, conn)
                st.dataframe(df_t)
                
                st.subheader("🗑️ Supprimer une ligne de trésorerie")
                id_to_del = st.number_input("Entrez l'ID de la ligne à supprimer", min_value=0, step=1)
                if st.button("Confirmer la suppression Tréso"):
                    conn.execute(f"DELETE FROM transactions WHERE id={id_to_del}")
                    conn.commit()
                    st.warning(f"Ligne {id_to_del} supprimée")
                    st.rerun()

            with tab2:
                query_f = "SELECT * FROM invoices" if st.session_state.role == 'admin' else f"SELECT * FROM invoices WHERE user_id={st.session_state.user_id}"
                df_f = pd.read_sql(query_f, conn)
                st.dataframe(df_f)
                
                st.subheader("🗑️ Supprimer une facture")
                id_f_del = st.number_input("Entrez l'ID de la facture à supprimer", min_value=0, step=1)
                if st.button("Confirmer la suppression Facture"):
                    conn.execute(f"DELETE FROM invoices WHERE id={id_f_del}")
                    conn.commit()
                    st.warning(f"Facture {id_f_del} supprimée")
                    st.rerun()

        # 4. ÉTATS FINANCIERS
        elif choice == "États Financiers":
            st.header("📊 États Financiers SMT")
            conn = get_connection()
            df = pd.read_sql(f"SELECT * FROM transactions WHERE user_id={st.session_state.user_id}", conn)
            df_inv = pd.read_sql(f"SELECT * FROM invoices WHERE user_id={st.session_state.user_id}", conn)
            
            if not df.empty:
                col1, col2 = st.columns(2)
                # Bilan Simplifié (Balance Trésorerie)
                with col1:
                    st.subheader("Balance des comptes")
                    bal = df.groupby('compte_treso').apply(lambda x: x[x['type']=='Entrée']['montant'].sum() - x[x['type']=='Sortie']['montant'].sum()).reset_index()
                    bal.columns = ['Compte', 'Solde']
                    st.table(bal)
                
                # Résultat
                with col2:
                    st.subheader("Compte de Résultat")
                    recettes = df[df['type']=='Entrée']['montant'].sum()
                    depenses = df[df['type']=='Sortie']['montant'].sum()
                    st.metric("Résultat Net", f"{recettes - depenses:,.0f} XAF")

                # Export Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Tresorerie')
                    df_inv.to_excel(writer, sheet_name='Factures')
                st.download_button("📥 Télécharger les journaux (Excel)", output.getvalue(), "compta_smt_complet.xlsx")

        # 5. GESTION ADMIN
        elif choice == "Gestion Admin" and st.session_state.role == 'admin':
            st.header("⚙️ Administration")
            new_user = st.text_input("Nom du nouveau client")
            new_pass = st.text_input("Mot de passe", type="password")
            if st.button("Créer le compte client"):
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", (new_user, make_hashes(new_pass), 'user'))
                    conn.commit()
                    st.success(f"Compte pour {new_user} activé !")
                except: st.error("Erreur (nom déjà pris)")

        if st.sidebar.button("Déconnexion"):
            st.session_state.logged_in = False
            st.rerun()

if __name__ == '__main__':
    main()
