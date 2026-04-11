import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io

# --- CONFIGURATION ET BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect('compta_ohada.db')
    c = conn.cursor()
    # Table Utilisateurs
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT)''')
    # Table Opérations
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, libelle TEXT, 
                  compte_treso TEXT, type TEXT, montant REAL, categorie TEXT)''')
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect('compta_ohada.db')

# --- LOGIQUE COMPTABLE SMT ---
def generate_etats(user_id):
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM transactions WHERE user_id={user_id}", conn)
    conn.close()
    
    if df.empty:
        return None, None, None

    # Balance des comptes
    balance = df.groupby('compte_treso')['montant'].sum().reset_index()
    
    # Livre des entrées / sorties
    livre_entrees = df[df['type'] == 'Entrée']
    livre_sorties = df[df['type'] == 'Sortie']
    
    # Compte de Résultat simplifié (Recettes - Dépenses)
    recettes = df[df['type'] == 'Entrée']['montant'].sum()
    depenses = df[df['type'] == 'Sortie']['montant'].sum()
    resultat = recettes - depenses
    
    return balance, livre_entrees, livre_sorties, resultat

# --- INTERFACE UTILISATEUR ---
def main():
    st.set_page_config(page_title="Compta SMT OHADA", layout="wide")
    init_db()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    # --- SÉCURITÉ / LOGIN ---
    if not st.session_state.logged_in:
        st.title("🔐 Connexion SMT OHADA")
        user = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type='password')
        col1, col2 = st.columns(2)
        if col1.button("Se connecter"):
            # Simulation de vérification (À remplacer par une requête DB réelle)
            st.session_state.logged_in = True
            st.session_state.username = user
            st.session_state.user_id = 1 # Exemple
            st.session_state.role = "admin" if user == "admin" else "user"
            st.rerun()
        if col2.button("Créer un compte"):
            st.info("Contactez l'administrateur pour l'accès.")
    else:
        # --- MENU PRINCIPAL ---
        st.sidebar.title(f"👤 {st.session_state.username}")
        menu = ["Saisie d'Opération", "Livres Comptables", "États Financiers (Bilan/Résultat)", "Gestion Admin"]
        choice = st.sidebar.selectbox("Navigation", menu)

        if choice == "Saisie d'Opération":
            st.header("📥 Nouvelle Opération de Trésorerie")
            with st.form("form_op"):
                date_op = st.date_input("Date", datetime.now())
                libelle = st.text_input("Libellé de l'opération")
                type_op = st.selectbox("Type", ["Entrée", "Sortie"])
                compte = st.selectbox("Mode de Paiement", ["571 (Caisse)", "521 (Banque)", "55 (Paiement Électronique)"])
                montant = st.number_input("Montant (XAF)", min_value=0.0)
                submit = st.form_submit_button("Enregistrer")
                
                if submit:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("INSERT INTO transactions (user_id, date, libelle, compte_treso, type, montant) VALUES (?,?,?,?,?,?)",
                              (st.session_state.user_id, date_op, libelle, compte, type_op, montant))
                    conn.commit()
                    st.success("Opération enregistrée !")

        elif choice == "Livres Comptables":
            st.header("📖 Livres des Entrées et Sorties")
            balance, l_entrees, l_sorties, res = generate_etats(st.session_state.user_id)
            
            st.subheader("Entrées")
            st.dataframe(l_entrees)
            
            st.subheader("Sorties")
            st.dataframe(l_sorties)

            # Export Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                if l_entrees is not None: l_entrees.to_excel(writer, sheet_name='Entrées')
                if l_sorties is not None: l_sorties.to_excel(writer, sheet_name='Sorties')
            
            st.download_button(label="📥 Télécharger les Livres (Excel)", data=buffer, file_name="livres_SMT.xlsx")

        elif choice == "États Financiers (Bilan/Résultat)":
            st.header("📊 États Financiers SMT")
            balance, l_entrees, l_sorties, res = generate_etats(st.session_state.user_id)
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Balance des Comptes")
                st.table(balance)
            with col2:
                st.subheader("Résultat Net")
                st.metric("Bénéfice/Perte", f"{res} XAF")

        elif choice == "Gestion Admin":
            if st.session_state.role == "admin":
                st.header("🛠 Interface Administrateur")
                conn = get_connection()
                all_data = pd.read_sql("SELECT * FROM transactions", conn)
                st.write("Toutes les opérations des utilisateurs :")
                st.dataframe(all_data)
                # Option de modification ici
            else:
                st.error("Accès réservé à l'administrateur.")

        if st.sidebar.button("Déconnexion"):
            st.session_state.logged_in = False
            st.rerun()

if __name__ == '__main__':
    main()