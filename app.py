import streamlit as st
import pandas as pd
import sqlite3
import hashlib

# --- FONCTIONS DE SÉCURITÉ ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return hashed_text
    return False

# --- GESTION DE LA BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect('compta_ohada.db')
    c = conn.cursor()
    # Table des utilisateurs
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
    # Table des opérations
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, libelle TEXT, 
                  compte_treso TEXT, type TEXT, montant REAL)''')
    
    # CRÉATION DU COMPTE ADMIN PAR DÉFAUT (si n'existe pas)
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = make_hashes('admin123')
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", ('admin', hashed_pw, 'admin'))
    
    conn.commit()
    conn.close()

def login_user(username, password):
    conn = sqlite3.connect('compta_ohada.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username =?', (username,))
    data = c.fetchone()
    conn.close()
    if data and check_hashes(password, data[2]):
        return data
    return None

def add_user(new_user, new_password, role='user'):
    conn = sqlite3.connect('compta_ohada.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users(username, password, role) VALUES (?,?,?)', (new_user, make_hashes(new_password), role))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

# --- INTERFACE PRINCIPALE ---
def main():
    st.title("📊 Système Comptable SMT OHADA")
    init_db()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        # --- ÉCRAN DE CONNEXION ---
        st.sidebar.subheader("Connexion")
        username = st.sidebar.text_input("Nom d'utilisateur")
        password = st.sidebar.text_input("Mot de passe", type='password')
        
        if st.sidebar.button("Se connecter"):
            user_data = login_user(username, password)
            if user_data:
                st.session_state.logged_in = True
                st.session_state.user_id = user_data[0]
                st.session_state.username = user_data[1]
                st.session_state.role = user_data[3]
                st.success(f"Bienvenue {username}")
                st.rerun()
            else:
                st.error("Utilisateur ou mot de passe incorrect")
        
        st.info("Veuillez vous connecter pour accéder à votre comptabilité SMT.")
        st.image("https://via.placeholder.com/800x400.png?text=Comptabilite+SMT+Cameroun") # Optionnel

    else:
        # --- MENU APRÈS CONNEXION ---
        st.sidebar.success(f"Connecté en tant que : {st.session_state.username}")
        
        menu = ["Ma Saisie SMT", "Mes États Financiers"]
        if st.session_state.role == 'admin':
            menu.
