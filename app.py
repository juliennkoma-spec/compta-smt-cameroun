import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import io
from datetime import datetime

# --- CONFIGURATION ---
TVA_RATE = 0.1925 # Taux Cameroun

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# --- BASE DE DONNÉES ---
def get_connection():
    return sqlite3.connect('compta_smt_v3.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, libelle TEXT, 
                  compte_treso TEXT, type TEXT, montant_ht REAL, tva REAL, montant_ttc REAL, categorie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS invoices 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, num_facture TEXT, 
                  libelle TEXT, quantite REAL, prix_unitaire REAL, montant_ht REAL, 
                  tva REAL, montant_ttc REAL)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", ('admin', make_hashes('admin123'), 'admin'))
    conn.commit()
    conn.close()

# --- INTERFACE ---
def main():
    st.set_page_config(page_title="SMT OHADA PRO - Cameroun", layout="wide")
    init_db()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🛡️ Gestion SMT OHADA")
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
            else: st.error("Identifiants incorrects")
    
    else:
        st.sidebar.title(f"👤 {st.session_state.username}")
        menu = ["Saisie Trésorerie", "Saisie Factures", "Consultation & Modif", "États Financiers"]
        if st.session_state.role == 'admin': menu.append("Gestion Admin")
        choice = st.sidebar.selectbox("Navigation", menu)

        # 1. SAISIE TRÉSORERIE (SMT)
        if choice == "Saisie Trésorerie":
            st.header("💵 Nouvelle Opération de Trésorerie")
            with st.form("form_treso"):
                col1, col2 = st.columns(2)
                date = col1.date_input("Date")
                libelle = col2.text_input("Libellé de l'opération")
                moyen = col1.selectbox("Compte de Trésorerie", ["571 Caisse", "521 Banque", "55 Paiement Électronique"])
                flux = col2.selectbox("Flux", ["Entrée", "Sortie"])
                
                montant_base = col1.number_input("Montant de base (XAF)", min_value=0.0)
                cat = col2.selectbox("Catégorie SMT", ["Ventes", "Achats", "Loyer", "Salaires", "Impôts", "Prélèvements"])
                
                # OPTION TVA
                activer_tva = st.checkbox("Appliquer la TVA (19.25%) sur cette opération ?")
                
                if st.form_submit_button("Enregistrer"):
                    tva = montant_base * TVA_RATE if activer_tva else 0
                    ttc = montant_base + tva
                    
                    conn = get_connection()
                    conn.execute("INSERT INTO transactions (user_id, date, libelle, compte_treso, type, montant_ht, tva, montant_ttc, categorie) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user_id, str(date), libelle, moyen, flux, montant_base, tva, ttc, cat))
                    conn.commit()
                    st.success(f"Enregistré : HT={montant_base:,.0f} | TVA={tva:,.0f} | TTC={ttc:,.0f}")

        # 2. SAISIE FACTURES
        elif choice == "Saisie Factures":
            st.header("📄 Création de Facture")
            with st.form("form_inv"):
                col1, col2 = st.columns(2)
                date_f = col1.date_input("Date")
                num_f = col2.text_input("Numéro de Facture")
                lib_f = st.text_input("Libellé / Désignation des biens ou services")
                
                c1, c2, c3 = st.columns(3)
                qty = c1.number_input("Quantité", min_value=0.0, value=1.0)
                pu = c2.number_input("Prix Unitaire HT", min_value=0.0)
                activer_tva_f = c3.checkbox("Soumis à la TVA ?")
                
                ht = qty * pu
                tva = ht * TVA_RATE if activer_tva_f else 0
                ttc = ht + tva
                
                st.info(f"RÉCAPITULATIF : Total HT: {ht:,.0f} | TVA: {tva:,.0f} | Total TTC: {ttc:,.0f} XAF")
                
                if st.form_submit_button("Valider la facture"):
                    conn = get_connection()
                    conn.execute("INSERT INTO invoices (user_id, date, num_facture, libelle, quantite, prix_unitaire, montant_ht, tva, montant_ttc) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user_id, str(date_f), num_f, lib_f, qty, pu, ht, tva, ttc))
                    conn.commit()
                    st.success("Facture enregistrée !")

        # 3. CONSULTATION / SUPPRESSION
        elif choice == "Consultation & Modif":
            st.header("🔍 Historique et Corrections")
            t1, t2 = st.tabs(["Trésorerie", "Factures"])
            conn = get_connection()
            
            with t1:
                query = "SELECT * FROM transactions" if st.session_state.role == 'admin' else f"SELECT * FROM transactions WHERE user_id={st.session_state.user_id}"
                df_t = pd.read_sql(query, conn)
                st.dataframe(df_t)
                id_del = st.number_input("ID à supprimer (Tréso)", min_value=0, step=1)
                if st.button("Supprimer l'opération"):
                    conn.execute(f"DELETE FROM transactions WHERE id={id_del}")
                    conn.commit()
                    st.rerun()

            with t2:
                query_f = "SELECT * FROM invoices" if st.session_state.role == 'admin' else f"SELECT * FROM invoices WHERE user_id={st.session_state.user_id}"
                df_f = pd.read_sql(query_f, conn)
                st.dataframe(df_f)
                id_f_del = st.number_input("ID à supprimer (Facture)", min_value=0, step=1)
                if st.button("Supprimer la facture"):
                    conn.execute(f"DELETE FROM invoices WHERE id={id_f_del}")
                    conn.commit()
                    st.rerun()

        # 4. ÉTATS FINANCIERS
        elif choice == "États Financiers":
            st.header("📊 États Financiers Automatiques")
            conn = get_connection()
            df = pd.read_sql(f"SELECT * FROM transactions WHERE user_id={st.session_state.user_id}", conn)
            
            if not df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Balance SMT (Solde par compte)")
                    # Solde = Entrées (TTC) - Sorties (TTC)
                    df['flux_reel'] = df.apply(lambda x: x['montant_ttc'] if x['type']=='Entrée' else -x['montant_ttc'], axis=1)
                    balance = df.groupby('compte_treso')['flux_reel'].sum().reset_index()
                    st.table(balance)
                
                with col2:
                    st.subheader("Compte de Résultat")
                    recettes = df[df['type']=='Entrée']['montant_ht'].sum()
                    depenses = df[df['type']=='Sortie']['montant_ht'].sum()
                    st.metric("Résultat Net (Hors Taxes)", f"{recettes - depenses:,.0f} XAF")
                    st.write(f"Total TVA collectée/déductible : {df['tva'].sum():,.0f} XAF")

                # Export Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Journal_Treso')
                    pd.read_sql(f"SELECT * FROM invoices WHERE user_id={st.session_state.user_id}", conn).to_excel(writer, sheet_name='Factures')
                st.download_button("📥 Télécharger Excel SMT", output.getvalue(), "compta_ohada_cameroun.xlsx")

        # 5. GESTION ADMIN
elif choice == "Gestion Admin" and st.session_state.role == 'admin':
    st.header("⚙️ Administration des comptes")
    
    col_create, col_list = st.columns(2)
    
    with col_create:
        st.subheader("Créer un nouvel utilisateur")
        new_u = st.text_input("Nom d'utilisateur client")
        new_p = st.text_input("Mot de passe", type="password")
        if st.button("Créer le compte"):
            if new_u and new_p:
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", 
                                 (new_u, make_hashes(new_p), 'user'))
                    conn.commit()
                    st.success(f"Compte '{new_u}' créé avec succès !")
                except sqlite3.IntegrityError:
                    st.error("Le nom d'utilisateur existe déjà.")
            else:
                st.warning("Veuillez remplir tous les champs.")

    with col_list:
        st.subheader("Utilisateurs existants")
        conn = get_connection()
        df_users = pd.read_sql("SELECT id, username, role FROM users", conn)
        st.dataframe(df_users, use_container_width=True)
        
        user_to_del = st.number_input("ID de l'utilisateur à supprimer", min_value=1, step=1)
        if st.button("Supprimer l'utilisateur"):
            if user_to_del == st.session_state.user_id:
                st.error("Vous ne pouvez pas supprimer votre propre compte admin actuel !")
            else:
                conn.execute(f"DELETE FROM users WHERE id={user_to_del}")
                conn.commit()
                st.success("Utilisateur supprimé.")
                st.rerun()
