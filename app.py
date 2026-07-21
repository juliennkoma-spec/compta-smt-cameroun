import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import io
from datetime import datetime
import re

# --- CONFIGURATION ---
TVA_RATE = 0.1925  # Taux Cameroun

def make_hashes(password):
    """Hache un mot de passe"""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    """Vérifie un mot de passe haché"""
    return make_hashes(password) == hashed_text

def generate_password(length=12):
    """Génère un mot de passe aléatoire sécurisé"""
    import random
    import string
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(characters) for _ in range(length))

def validate_password(password):
    """Valide la complexité du mot de passe"""
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères"
    if not re.search(r"[A-Z]", password):
        return False, "Le mot de passe doit contenir au moins une majuscule"
    if not re.search(r"[a-z]", password):
        return False, "Le mot de passe doit contenir au moins une minuscule"
    if not re.search(r"\d", password):
        return False, "Le mot de passe doit contenir au moins un chiffre"
    if not re.search(r"[!@#$%^&*]", password):
        return False, "Le mot de passe doit contenir au moins un caractère spécial (!@#$%^&*)"
    return True, "Mot de passe valide"

# --- BASE DE DONNÉES ---
def get_connection():
    return sqlite3.connect('compta_smt_v3.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, created_at TEXT, last_login TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, libelle TEXT, 
                  compte_treso TEXT, type TEXT, montant_ht REAL, tva REAL, montant_ttc REAL, categorie TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS invoices 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, date TEXT, num_facture TEXT, 
                  libelle TEXT, quantite REAL, prix_unitaire REAL, montant_ht REAL, 
                  tva REAL, montant_ttc REAL, created_at TEXT)''')
    
    # Création du compte admin par défaut
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role, created_at) VALUES (?,?,?,?)", 
                  ('admin', make_hashes('admin123'), 'admin', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# --- INTERFACE ---
def main():
    st.set_page_config(page_title="SMT OHADA PRO - Cameroun", layout="wide")
    init_db()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'notification' not in st.session_state:
        st.session_state.notification = None

    # --- PAGE DE CONNEXION ---
    if not st.session_state.logged_in:
        st.title("🛡️ Gestion SMT OHADA")
        st.markdown("### Connexion à l'application")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            with st.container(border=True):
                user = st.text_input("👤 Nom d'utilisateur", placeholder="Entrez votre nom d'utilisateur")
                pw = st.text_input("🔑 Mot de passe", type='password', placeholder="Entrez votre mot de passe")
                
                if st.button("🔓 Se connecter", use_container_width=True):
                    if user and pw:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute('SELECT * FROM users WHERE username=?', (user,))
                        res = c.fetchone()
                        if res and check_hashes(pw, res[2]):
                            st.session_state.logged_in = True
                            st.session_state.user_id = res[0]
                            st.session_state.username = res[1]
                            st.session_state.role = res[3]
                            # Mise à jour de la dernière connexion
                            c.execute("UPDATE users SET last_login=? WHERE id=?", 
                                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), res[0]))
                            conn.commit()
                            conn.close()
                            st.success(f"✅ Bienvenue {res[1]} !")
                            st.rerun()
                        else:
                            st.error("❌ Identifiants incorrects")
                    else:
                        st.warning("⚠️ Veuillez remplir tous les champs")
    
    else:
        # --- BARRE LATÉRALE ---
        st.sidebar.title(f"👤 {st.session_state.username}")
        st.sidebar.caption(f"Rôle : {'🔑 Admin' if st.session_state.role == 'admin' else '👤 Utilisateur'}")
        st.sidebar.divider()
        
        # Menu principal
        menu = ["📊 Tableau de bord", "💵 Saisie Trésorerie", "📄 Saisie Factures", "🔍 Consultation", "📈 États Financiers"]
        if st.session_state.role == 'admin':
            menu.append("⚙️ Gestion Admin")
        choice = st.sidebar.selectbox("📋 Navigation", menu)
        
        # Bouton déconnexion
        if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
        
        st.sidebar.divider()
        st.sidebar.info("📅 Compta SMT Cameroun v3.0")

        # --- 0. TABLEAU DE BORD ---
        if choice == "📊 Tableau de bord":
            st.header("📊 Tableau de bord")
            
            conn = get_connection()
            # Statistiques
            col1, col2, col3, col4 = st.columns(4)
            
            # Nombre de transactions
            df_trans = pd.read_sql(f"SELECT COUNT(*) as nb FROM transactions WHERE user_id={st.session_state.user_id}", conn)
            col1.metric("📝 Transactions", df_trans['nb'].iloc[0] if not df_trans.empty else 0)
            
            # Nombre de factures
            df_inv = pd.read_sql(f"SELECT COUNT(*) as nb FROM invoices WHERE user_id={st.session_state.user_id}", conn)
            col2.metric("📄 Factures", df_inv['nb'].iloc[0] if not df_inv.empty else 0)
            
            # Total encaissé
            df_ca = pd.read_sql(f"SELECT SUM(montant_ttc) as total FROM transactions WHERE user_id={st.session_state.user_id} AND type='Entrée'", conn)
            total_ca = df_ca['total'].iloc[0] if not df_ca.empty and df_ca['total'].iloc[0] else 0
            col3.metric("💰 Total encaissé", f"{total_ca:,.0f} XAF")
            
            # Total dépensé
            df_dep = pd.read_sql(f"SELECT SUM(montant_ttc) as total FROM transactions WHERE user_id={st.session_state.user_id} AND type='Sortie'", conn)
            total_dep = df_dep['total'].iloc[0] if not df_dep.empty and df_dep['total'].iloc[0] else 0
            col4.metric("💳 Total dépensé", f"{total_dep:,.0f} XAF")
            
            # Dernières activités
            st.subheader("📋 Dernières activités")
            tab1, tab2 = st.tabs(["Dernières transactions", "Dernières factures"])
            
            with tab1:
                df_last = pd.read_sql(f"SELECT date, libelle, type, montant_ttc FROM transactions WHERE user_id={st.session_state.user_id} ORDER BY id DESC LIMIT 5", conn)
                if not df_last.empty:
                    st.dataframe(df_last, use_container_width=True, hide_index=True)
                else:
                    st.info("Aucune transaction enregistrée")
            
            with tab2:
                df_last_inv = pd.read_sql(f"SELECT date, num_facture, libelle, montant_ttc FROM invoices WHERE user_id={st.session_state.user_id} ORDER BY id DESC LIMIT 5", conn)
                if not df_last_inv.empty:
                    st.dataframe(df_last_inv, use_container_width=True, hide_index=True)
                else:
                    st.info("Aucune facture enregistrée")
            
            conn.close()

        # --- 1. SAISIE TRÉSORERIE ---
        elif choice == "💵 Saisie Trésorerie":
            st.header("💵 Nouvelle Opération de Trésorerie")
            with st.form("form_treso"):
                col1, col2 = st.columns(2)
                date = col1.date_input("📅 Date", datetime.now())
                libelle = col2.text_input("📝 Libellé de l'opération", placeholder="Ex: Paiement fournisseur")
                moyen = col1.selectbox("🏦 Compte de Trésorerie", ["571 Caisse", "521 Banque", "55 Paiement Électronique"])
                flux = col2.selectbox("🔄 Flux", ["Entrée", "Sortie"])
                
                montant_base = col1.number_input("💰 Montant de base (XAF)", min_value=0.0, step=1000.0)
                cat = col2.selectbox("📂 Catégorie SMT", ["Ventes", "Achats", "Loyer", "Salaires", "Impôts", "Prélèvements"])
                
                activer_tva = st.checkbox("🧾 Appliquer la TVA (19.25%) sur cette opération ?")
                
                if st.form_submit_button("💾 Enregistrer", use_container_width=True):
                    if montant_base <= 0:
                        st.error("❌ Le montant doit être supérieur à 0")
                    else:
                        tva = montant_base * TVA_RATE if activer_tva else 0
                        ttc = montant_base + tva
                        
                        conn = get_connection()
                        conn.execute("INSERT INTO transactions (user_id, date, libelle, compte_treso, type, montant_ht, tva, montant_ttc, categorie, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                     (st.session_state.user_id, str(date), libelle, moyen, flux, montant_base, tva, ttc, cat, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Enregistré : HT={montant_base:,.0f} | TVA={tva:,.0f} | TTC={ttc:,.0f} XAF")

        # --- 2. SAISIE FACTURES ---
        elif choice == "📄 Saisie Factures":
            st.header("📄 Création de Facture")
            with st.form("form_inv"):
                col1, col2 = st.columns(2)
                date_f = col1.date_input("📅 Date", datetime.now())
                num_f = col2.text_input("🔢 Numéro de Facture", placeholder="Ex: FAC-2024-001")
                lib_f = st.text_input("📝 Libellé / Désignation", placeholder="Décrivez le bien ou service")
                
                c1, c2, c3 = st.columns(3)
                qty = c1.number_input("📦 Quantité", min_value=0.0, value=1.0, step=1.0)
                pu = c2.number_input("💰 Prix Unitaire HT", min_value=0.0, step=100.0)
                activer_tva_f = c3.checkbox("🧾 Soumis à la TVA ?")
                
                ht = qty * pu
                tva = ht * TVA_RATE if activer_tva_f else 0
                ttc = ht + tva
                
                st.info(f"📊 RÉCAPITULATIF : Total HT: {ht:,.0f} | TVA: {tva:,.0f} | Total TTC: {ttc:,.0f} XAF")
                
                if st.form_submit_button("💾 Valider la facture", use_container_width=True):
                    if qty <= 0 or pu <= 0:
                        st.error("❌ La quantité et le prix unitaire doivent être supérieurs à 0")
                    else:
                        conn = get_connection()
                        conn.execute("INSERT INTO invoices (user_id, date, num_facture, libelle, quantite, prix_unitaire, montant_ht, tva, montant_ttc, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                     (st.session_state.user_id, str(date_f), num_f, lib_f, qty, pu, ht, tva, ttc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit()
                        conn.close()
                        st.success("✅ Facture enregistrée avec succès !")

        # --- 3. CONSULTATION ---
        elif choice == "🔍 Consultation":
            st.header("🔍 Historique et Corrections")
            t1, t2 = st.tabs(["💳 Trésorerie", "📄 Factures"])
            conn = get_connection()
            
            with t1:
                query = "SELECT * FROM transactions ORDER BY id DESC" if st.session_state.role == 'admin' else f"SELECT * FROM transactions WHERE user_id={st.session_state.user_id} ORDER BY id DESC"
                df_t = pd.read_sql(query, conn)
                st.dataframe(df_t, use_container_width=True, hide_index=True)
                
                if not df_t.empty:
                    id_del = st.number_input("🆔 ID à supprimer (Tréso)", min_value=0, step=1)
                    if st.button("🗑️ Supprimer l'opération"):
                        try:
                            conn.execute(f"DELETE FROM transactions WHERE id={id_del}")
                            conn.commit()
                            st.success("✅ Opération supprimée")
                            st.rerun()
                        except:
                            st.error("❌ Erreur lors de la suppression")

            with t2:
                query_f = "SELECT * FROM invoices ORDER BY id DESC" if st.session_state.role == 'admin' else f"SELECT * FROM invoices WHERE user_id={st.session_state.user_id} ORDER BY id DESC"
                df_f = pd.read_sql(query_f, conn)
                st.dataframe(df_f, use_container_width=True, hide_index=True)
                
                if not df_f.empty:
                    id_f_del = st.number_input("🆔 ID à supprimer (Facture)", min_value=0, step=1)
                    if st.button("🗑️ Supprimer la facture"):
                        try:
                            conn.execute(f"DELETE FROM invoices WHERE id={id_f_del}")
                            conn.commit()
                            st.success("✅ Facture supprimée")
                            st.rerun()
                        except:
                            st.error("❌ Erreur lors de la suppression")
            
            conn.close()

        # --- 4. ÉTATS FINANCIERS ---
        elif choice == "📈 États Financiers":
            st.header("📊 États Financiers Automatiques")
            conn = get_connection()
            df = pd.read_sql(f"SELECT * FROM transactions WHERE user_id={st.session_state.user_id}", conn)
            
            if not df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("🏦 Balance SMT (Solde par compte)")
                    df['flux_reel'] = df.apply(lambda x: x['montant_ttc'] if x['type']=='Entrée' else -x['montant_ttc'], axis=1)
                    balance = df.groupby('compte_treso')['flux_reel'].sum().reset_index()
                    st.dataframe(balance, use_container_width=True, hide_index=True)
                
                with col2:
                    st.subheader("📊 Compte de Résultat")
                    recettes = df[df['type']=='Entrée']['montant_ht'].sum()
                    depenses = df[df['type']=='Sortie']['montant_ht'].sum()
                    resultat = recettes - depenses
                    
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("💰 Recettes HT", f"{recettes:,.0f} XAF")
                    col_b.metric("💳 Dépenses HT", f"{depenses:,.0f} XAF")
                    col_c.metric("📈 Résultat Net HT", f"{resultat:,.0f} XAF", 
                                delta=f"{resultat:,.0f}" if resultat >= 0 else None,
                                delta_color="inverse")
                    
                    st.metric("🧾 Total TVA", f"{df['tva'].sum():,.0f} XAF")

                # Export Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Journal_Treso', index=False)
                    pd.read_sql(f"SELECT * FROM invoices WHERE user_id={st.session_state.user_id}", conn).to_excel(writer, sheet_name='Factures', index=False)
                    
                    # Ajout des stats
                    stats_df = pd.DataFrame({
                        'Indicateur': ['Total Recettes HT', 'Total Dépenses HT', 'Résultat Net HT', 'Total TVA'],
                        'Montant XAF': [recettes, depenses, resultat, df['tva'].sum()]
                    })
                    stats_df.to_excel(writer, sheet_name='Statistiques', index=False)
                
                st.download_button("📥 Télécharger Excel SMT", 
                                 output.getvalue(), 
                                 f"compta_smt_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                 use_container_width=True)
            else:
                st.info("📭 Aucune transaction à afficher")
            
            conn.close()

        # --- 5. GESTION ADMIN (AMÉLIORÉE) ---
        elif choice == "⚙️ Gestion Admin" and st.session_state.role == 'admin':
            st.header("⚙️ Administration des comptes")
            
            # Vérification du rôle
            if st.session_state.role != 'admin':
                st.error("⛔ Accès refusé. Vous devez être administrateur.")
            else:
                # Onglets Admin
                tab_create, tab_list, tab_export = st.tabs(["➕ Créer un utilisateur", "📋 Liste des utilisateurs", "📤 Exporter"])
                
                # --- ONGLET CRÉATION ---
                with tab_create:
                    st.subheader("➕ Créer un nouvel utilisateur")
                    
                    with st.form("create_user_form"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            new_u = st.text_input("👤 Nom d'utilisateur", placeholder="Entrez le nom d'utilisateur")
                            new_password = st.text_input("🔑 Mot de passe", type="password", placeholder="Laissez vide pour générer automatiquement")
                            new_role = st.selectbox("🎯 Rôle", ["user", "admin"], 
                                                   help="admin: accès complet, user: accès restreint")
                            
                            # Option de génération automatique
                            auto_gen = st.checkbox("🎲 Générer automatiquement un mot de passe sécurisé")
                            if auto_gen:
                                gen_pw = generate_password()
                                st.code(gen_pw, language="text")
                                st.caption("📋 Copiez ce mot de passe pour le donner à l'utilisateur")
                        
                        with col2:
                            st.subheader("📋 Récapitulatif")
                            if auto_gen:
                                final_pw = gen_pw
                            elif new_password:
                                final_pw = new_password
                                is_valid, msg = validate_password(new_password)
                                if is_valid:
                                    st.success("✅ Mot de passe valide")
                                else:
                                    st.warning(f"⚠️ {msg}")
                            else:
                                final_pw = None
                                st.info("💡 Entrez un mot de passe ou utilisez la génération automatique")
                        
                        submitted = st.form_submit_button("✅ Créer le compte", use_container_width=True)
                        
                        if submitted:
                            if not new_u:
                                st.error("❌ Le nom d'utilisateur est obligatoire")
                            elif not final_pw:
                                st.error("❌ Veuillez fournir un mot de passe ou activer la génération automatique")
                            else:
                                # Validation du mot de passe si non généré
                                if not auto_gen and not validate_password(final_pw)[0]:
                                    st.error(f"❌ {validate_password(final_pw)[1]}")
                                else:
                                    try:
                                        conn = get_connection()
                                        conn.execute("INSERT INTO users (username, password, role, created_at) VALUES (?,?,?,?)", 
                                                    (new_u, make_hashes(final_pw), new_role, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                                        conn.commit()
                                        conn.close()
                                        st.success(f"✅ Compte '{new_u}' créé avec succès !")
                                        
                                        # Affichage des identifiants
                                        if auto_gen:
                                            st.info(f"🔑 Identifiants de '{new_u}' :")
                                            st.code(f"Nom d'utilisateur : {new_u}\nMot de passe : {final_pw}")
                                            st.warning("⚠️ Assurez-vous de noter ces identifiants, ils ne seront plus affichés !")
                                        
                                        st.rerun()
                                    except sqlite3.IntegrityError:
                                        st.error("❌ Ce nom d'utilisateur existe déjà.")
                                    except Exception as e:
                                        st.error(f"❌ Erreur : {e}")
                
                # --- ONGLET LISTE ---
                with tab_list:
                    st.subheader("📋 Utilisateurs existants")
                    
                    conn = get_connection()
                    df_users = pd.read_sql("SELECT id, username, role, created_at, last_login FROM users ORDER BY id", conn)
                    conn.close()
                    
                    if not df_users.empty:
                        # Formatage des dates
                        df_users['created_at'] = pd.to_datetime(df_users['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                        df_users['last_login'] = pd.to_datetime(df_users['last_login']).dt.strftime('%d/%m/%Y %H:%M')
                        df_users['last_login'] = df_users['last_login'].fillna("Jamais")
                        
                        # Affichage avec mise en forme
                        def color_role(val):
                            if val == 'admin':
                                return 'color: #ff6b6b; font-weight: bold'
                            return 'color: #4ecdc4'
                        
                        st.dataframe(df_users, 
                                   use_container_width=True, 
                                   hide_index=True,
                                   column_config={
                                       "id": "🆔 ID",
                                       "username": "👤 Utilisateur",
                                       "role": "🎯 Rôle",
                                       "created_at": "📅 Créé le",
                                       "last_login": "🔑 Dernière connexion"
                                   })
                        
                        st.divider()
                        
                        # Section suppression
                        st.subheader("🗑️ Supprimer un utilisateur")
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            user_to_del = st.selectbox(
                                "Sélectionnez l'utilisateur à supprimer",
                                options=df_users['id'].tolist(),
                                format_func=lambda x: f"ID {x} - {df_users[df_users['id']==x]['username'].iloc[0]}"
                            )
                        
                        with col2:
                            st.write("")
                            st.write("")
                            if st.button("🗑️ Supprimer", use_container_width=True, type="primary"):
                                if user_to_del == st.session_state.user_id:
                                    st.error("⛔ Vous ne pouvez pas supprimer votre propre compte admin actuel !")
                                else:
                                    try:
                                        conn = get_connection()
                                        conn.execute("DELETE FROM users WHERE id=?", (user_to_del,))
                                        conn.commit()
                                        conn.close()
                                        st.success("✅ Utilisateur supprimé avec succès.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Erreur : {e}")
                    else:
                        st.info("📭 Aucun utilisateur enregistré")
                
                # --- ONGLET EXPORT ---
                with tab_export:
                    st.subheader("📤 Exporter la liste des utilisateurs")
                    
                    conn = get_connection()
                    df_export = pd.read_sql("SELECT id, username, role, created_at, last_login FROM users ORDER BY id", conn)
                    conn.close()
                    
                    if not df_export.empty:
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df_export.to_excel(writer, sheet_name='Utilisateurs', index=False)
                            
                            # Ajout de statistiques
                            stats = pd.DataFrame({
                                'Statistiques': ['Total utilisateurs', 'Admins', 'Utilisateurs standards'],
                                'Valeur': [len(df_export), 
                                          len(df_export[df_export['role']=='admin']),
                                          len(df_export[df_export['role']=='user'])]
                            })
                            stats.to_excel(writer, sheet_name='Statistiques', index=False)
                        
                        st.download_button("📥 Télécharger la liste des utilisateurs",
                                         output.getvalue(),
                                         f"utilisateurs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                         use_container_width=True)
                        
                        st.success(f"✅ {len(df_export)} utilisateurs prêts à être exportés")
                    else:
                        st.info("📭 Aucun utilisateur à exporter")

if __name__ == '__main__':
    main()
