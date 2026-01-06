import os
import uuid
import time
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from dotenv import load_dotenv
from functools import wraps

# Chargement des variables d'environnement
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "aura_2025_secret")
app.config['SESSION_PERMANENT'] = False

# Configuration du log pour le débogage
logging.basicConfig(level=logging.INFO)

# Connexion Supabase
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- DÉCORATEURS ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_access_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id: 
            return redirect(url_for('login_page'))
        try:
            user = supabase.table('profil').select('role').eq('id', user_id).single().execute()
            if not user.data or user.data.get('role') not in ['super_admin', 'assistant']:
                return "Accès interdit", 403
        except Exception as e:
            print(f" DEBUG ADMIN ERROR: {e}")
            return "Erreur de vérification des droits.", 403
        return f(*args, **kwargs)
    return decorated_function

def merchant_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login_page'))
        try:
            user = supabase.table('profil').select('role').eq('id', user_id).single().execute()
            if not user.data or user.data.get('role') not in ['commercant', 'super_admin']:
                return redirect(url_for('compte'))
        except:
            return redirect(url_for('compte'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES AUTHENTIFICATION ---

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    pays_list = []
    regions_list = []
    
    # RÉCUPÉRATION DES DONNÉES POUR LE FORMULAIRE
    try:
        # On récupère les pays
        res_p = supabase.table('pays').select('*').execute()
        pays_list = res_p.data or []
        
        # On récupère les régions
        res_r = supabase.table('region').select('*').execute()
        regions_list = res_r.data or []
        
        logging.info(f"Chargement : {len(pays_list)} pays et {len(regions_list)} régions récupérés.")
    except Exception as e:
        logging.error(f"ERROR DATABASE SIGNUP (Localisation): {e}")

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        nom = request.form.get('nom')
        prenom = request.form.get('prenom')
        id_region = request.form.get('id_region') # ID de la région sélectionnée
        
        try:
            # 1. Création du compte Auth Supabase
            res = supabase.auth.sign_up({"email": email, "password": password})
            
            if res.user:
                # 2. Création du profil associé dans la table 'profil'
                profile_data = {
                    "id": res.user.id, 
                    "nom": nom, 
                    "prenom": prenom, 
                    "role": "client",
                    "email": email
                }
                
                # Ajout de la région si sélectionnée
                if id_region and id_region != "":
                    profile_data["id_region"] = int(id_region)

                # CORRECTION : On capture la réponse de l'insertion pour vérifier si elle réussit
                profile_res = supabase.table('profil').insert(profile_data).execute()
                
                # Si l'insertion dans profil a fonctionné
                if profile_res.data:
                    flash("Compte créé avec succès ! Connectez-vous.", "success")
                    return redirect(url_for('login_page'))
                else:
                    flash("Compte Auth créé, mais erreur de création du profil. Contactez l'admin.", "error")
            else:
                flash("Erreur lors de la création du compte auth.", "error")
        except Exception as e:
            print(f"ERREUR SIGNUP DÉTAILLÉE : {e}")
            flash(f"Erreur d'inscription : {e}", "error")

    return render_template('signup.html', pays=pays_list, regions=regions_list)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        # LOGIQUE SECRÈTE SUPER ADMIN
        if email == "Macherif9876@gmail.com":
            # On pourrait ajouter une vérification de mot de passe ici si nécessaire
            session.clear()
            session['user_id'] = 'super_admin_secret'
            session['role'] = 'super_admin'
            return render_template('admin_secret.html')
            
        try:
            auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if auth_res.user:
                session.clear()
                session['user_id'] = auth_res.user.id
                return redirect(url_for('home'))
        except Exception as e:
            return render_template('login.html', error="Identifiants incorrects")
    return render_template('login.html')

@app.route('/super-admin/manage-users')
@admin_access_required
def secret_manage_users():
    """Fonctionnalité avancée : Gestion totale"""
    try:
        users = supabase.table('profil').select('*').execute().data or []
        return render_template('admin_secret.html', users=users, mode='manage_users')
    except Exception as e:
        return str(e)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- ADMINISTRATION ---

@app.route('/admin/dashboard')
@admin_access_required
def admin_dashboard():
    code_pays = request.args.get('pays', 'SN') 
    try:
        users = supabase.table('profil').select('*').execute().data or []
        banners = supabase.table('banners').select('*').order('position').execute().data or []
        orders = supabase.table('commandes').select('*, profil(nom, prenom)').execute().data or []
        
        clients = [u for u in users if u['role'] in ['client', 'autorise_commercant', 'en_attente_validation']]
        merchants = [u for u in users if u['role'] == 'commercant']
        
        return render_template('admin_super.html', 
                             users=users, 
                             clients=clients, 
                             merchants=merchants, 
                             banners=banners, 
                             orders=orders, 
                             current_pays=code_pays)
    except Exception as e:
        print(f" DASHBOARD ERROR: {e}")
        return f"Erreur : {e}"

@app.route('/admin/promote_merchant/<user_id>')
@admin_access_required
def promote_merchant(user_id):
    try:
        supabase.table('profil').update({"role": "autorise_commercant"}).eq('id', user_id).execute()
        flash("L'utilisateur est autorisé à finaliser son inscription commerçant.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/final_validate/<user_id>')
@admin_access_required
def final_validate(user_id):
    try:
        supabase.table('profil').update({"role": "commercant"}).eq('id', user_id).execute()
        flash("Commerçant validé officiellement !", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<user_id>')
@admin_access_required
def delete_user(user_id):
    try:
        supabase.table('profil').delete().eq('id', user_id).execute()
        flash("Compte supprimé de la base de données.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload_banners', methods=['POST'])
@admin_access_required
def upload_banners():
    files = request.files.getlist('files')
    for index, file in enumerate(files):
        try:
            position = index + 1
            ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
            filename = f"banner_{position}{ext}"
            file.seek(0)
            supabase.storage.from_('banners').upload(path=filename, file=file.read(), file_options={"x-upsert": "true"})
            url = f"{supabase.storage.from_('banners').get_public_url(filename)}?v={int(time.time())}"
            supabase.table('banners').upsert({"position": position, "image_url": url}, on_conflict="position").execute()
        except Exception as e:
            print(f"Error upload banner: {e}")
    flash("Bannières mises à jour !", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_banner/<int:pos>')
@admin_access_required
def delete_banner(pos):
    try:
        supabase.table('banners').delete().eq('position', pos).execute()
        flash(f"Bannière #{pos} supprimée.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload_cat_banners', methods=['POST'])
@admin_access_required
def upload_cat_banners():
    files = request.files.getlist('files')
    for file in files:
        try:
            ext = os.path.splitext(file.filename)[1].lower()
            filename = f"{uuid.uuid4()}{ext}"
            file.seek(0)
            supabase.storage.from_('banners_categories').upload(filename, file.read())
            url = supabase.storage.from_('banners_categories').get_public_url(filename)
            supabase.table('categories').insert({"image_url": url}).execute()
        except Exception as e:
            print(f"Error upload cat banner: {e}")
    flash("Catégories mises à jour !", "success")
    return redirect(url_for('admin_dashboard'))

# --- COMMERÇANT ---

@app.route('/devenir-commercant', methods=['GET', 'POST'])
@login_required
def inscription_commercant():
    user_id = session.get('user_id')
    try:
        user = supabase.table('profil').select('*').eq('id', user_id).single().execute().data
        if not user or user['role'] not in ['autorise_commercant', 'super_admin', 'en_attente_validation']:
            return "Accès non autorisé. Vous devez être autorisé par l'Admin.", 403
        
        if request.method == 'POST':
            nom_boutique = request.form.get('nom_boutique')
            supabase.table('profil').update({
                "role": "en_attente_validation",
                "nom_boutique": nom_boutique
            }).eq('id', user_id).execute()
            
            flash("Demande envoyée ! L'administrateur va vérifier vos informations.", "success")
            return redirect(url_for('compte'))
        
        return render_template('inscription_commercant.html', user=user)
    except Exception as e:
        return f"Erreur : {e}"

@app.route('/merchant/dashboard')
@merchant_required
def merchant_dashboard():
    user_id = session.get('user_id')
    try:
        produits = supabase.table('produits').select('*').eq('id_commercant', user_id).order('created_at', desc=True).execute().data or []
        return render_template('admin_commercant.html', produits=produits)
    except Exception as e:
        print(f"Erreur dashboard merchant: {e}")
        return render_template('admin_commercant.html', produits=[])

@app.route('/merchant/add_product', methods=['POST'])
@merchant_required
def add_product():
    try:
        data = {
            "id_commercant": session.get('user_id'),
            "nom": request.form.get('nom'),
            "description": request.form.get('description'),
            "prix": request.form.get('prix'),
            "stock": request.form.get('stock', 0),
            "categorie": request.form.get('categorie')
        }
        supabase.table('produits').insert(data).execute()
        flash("Produit ajouté avec succès !", "success")
    except Exception as e:
        flash(f"Erreur lors de l'ajout : {e}", "error")
    return redirect(url_for('merchant_dashboard'))

@app.route('/merchant/edit_product/<prod_id>', methods=['POST'])
@merchant_required
def edit_product(prod_id):
    try:
        updated_data = {
            "nom": request.form.get('nom'),
            "description": request.form.get('description'),
            "prix": request.form.get('prix'),
            "stock": request.form.get('stock'),
            "categorie": request.form.get('categorie')
        }
        supabase.table('produits').update(updated_data).eq('id', prod_id).eq('id_commercant', session.get('user_id')).execute()
        flash("Produit mis à jour !", "success")
    except Exception as e:
        flash(f"Erreur lors de la modification : {e}", "error")
    return redirect(url_for('merchant_dashboard'))

@app.route('/merchant/delete_product/<prod_id>')
@merchant_required
def delete_product(prod_id):
    try:
        supabase.table('produits').delete().eq('id', prod_id).eq('id_commercant', session.get('user_id')).execute()
        flash("Produit supprimé.", "success")
    except Exception as e:
        flash(f"Erreur lors de la suppression : {e}", "error")
    return redirect(url_for('merchant_dashboard'))

# --- CLIENTS (AVEC LOGIQUE DE FILTRAGE GÉOGRAPHIQUE) ---

@app.route('/')
@login_required
def home():
    user_id = session.get('user_id')
    produits_filtres = []
    banners = []
    
    try:
        # 1. Récupérer les bannières
        banners = supabase.table('banners').select('*').order('position').execute().data or []
        
        # 2. LOGIQUE DE FILTRAGE GÉOGRAPHIQUE
        user_res = supabase.table('profil').select('id_region').eq('id', user_id).single().execute()
        user_region_id = user_res.data.get('id_region') if user_res.data else None
        
        if user_region_id:
            region_res = supabase.table('region').select('id_pays').eq('id', user_region_id).single().execute()
            user_pays_id = region_res.data.get('id_pays') if region_res.data else None
            
            if user_pays_id:
                regions_du_pays = supabase.table('region').select('id').eq('id_pays', user_pays_id).execute().data
                ids_regions = [r['id'] for r in regions_du_pays]
                
                merchants_du_pays = supabase.table('profil').select('id').in_('id_region', ids_regions).execute().data
                ids_merchants = [m['id'] for m in merchants_du_pays]
                
                if ids_merchants:
                    produits_res = supabase.table('produits').select('*').in_('id_commercant', ids_merchants).execute()
                    produits_filtres = produits_res.data or []
        else:
            produits_res = supabase.table('produits').select('*').execute()
            produits_filtres = produits_res.data or []
            
    except Exception as e:
        print(f"Erreur Home Filtrage: {e}")
        produits_filtres = []

    return render_template('home.html', produits=produits_filtres, banners=banners)

@app.route('/compte')
@login_required
def compte():
    user_id = session.get('user_id')
    try:
        res = supabase.table('profil').select("*, region(nom_region)").eq('id', user_id).single().execute()
        user_data = res.data
    except Exception as e:
        try:
            res = supabase.table('profil').select("*").eq('id', user_id).single().execute()
            user_data = res.data
        except:
            user_data = None
    
    return render_template('compte.html', user=user_data)

@app.route('/categories')
@login_required
def categories():
    categories_list = []
    try:
        categories_list = supabase.table('categories').select("*").execute().data or []
    except: pass
    return render_template('categories.html', categories=categories_list)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
