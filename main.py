import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLBACKEND', 'Agg')

import uuid
import time
import logging
import json 
import io
import random
import base64
import requests
import traceback
import subprocess
import sys
import threading

try:
    from pywebpush import webpush, WebPushException
    PUSH_ACTIF = True
except ImportError:
    PUSH_ACTIF = False
    logging.warning("[PUSH] pywebpush non installé — notifications désactivées")

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv
from functools import wraps

from auth_inscription import inscription_bp, init_supabase

import cloudinary
import cloudinary.uploader

MODE_IA_ACTIF = False

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "aura_2025_secret")
app.config['SESSION_PERMANENT'] = False

DB_CONNECTED = False
DB_ERROR_MSG = ""

app.register_blueprint(inscription_bp)

@app.template_filter('shuffle')
def filter_shuffle(seq):
    try:
        result = list(seq)
        random.shuffle(result)
        return result
    except:
        return seq

logging.basicConfig(level=logging.INFO)

try:
    print("\n" + "="*50)
    print("🛑 DEBUG INITIALISATION : Tentative de connexion Supabase...")
    print(f"URL ciblée : {os.getenv('SUPABASE_URL')}")
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ ERREUR CRITIQUE : Variables SUPABASE_URL ou SUPABASE_KEY manquantes !")
        DB_ERROR_MSG = "Variables d'environnement manquantes."
        supabase = None
    else:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        try:
            print("🔄 Test ping Supabase...")
            test_conn = supabase.table('profil').select('id').limit(1).execute()
            print("✅ Client Supabase créé et authentifié !")
            DB_CONNECTED = True
        except Exception as e_ping:
            print(f"⚠️ Client créé mais test échoué : {e_ping}")
            DB_ERROR_MSG = str(e_ping)
            DB_CONNECTED = False
        init_supabase(supabase)
    print("="*50 + "\n")
except Exception as e:
    print(f"⚠️ ERREUR CRITIQUE : {e}")
    traceback.print_exc()
    DB_ERROR_MSG = str(e)
    supabase = None

cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key    = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure     = True
)

class MoteurRechercheAura:
    def __init__(self):
        self.produits_map = []  

    def indexer_tout_le_catalogue(self):
        print("📊 [IA] Mode IA désactivé.")
        return

    def recherche_intelligente(self, query_text=None, query_image_file=None, top_k=20):
        return []

moteur_ia = MoteurRechercheAura()

# --- GITHUB CDN ---
def rendre_depot_public(user, token, repo_nom):
    try:
        url = f"https://api.github.com/repos/{user}/{repo_nom}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        requests.patch(url, json={"private": False}, headers=headers, timeout=10)
    except:
        pass

def trouver_nimporte_quel_depot(user, token):
    try:
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        res = requests.get(f"https://api.github.com/users/{user}/repos?per_page=100", headers=headers, timeout=10)
        if res.status_code == 200:
            repos = res.json()
            if not repos: return None
            for r in repos:
                nom = r['name'].lower()
                if any(mot in nom for mot in ['aura', 'storage', 'vids', 'video']):
                    return r['name']
            return repos[0]['name']
    except Exception as e:
        print(f"❌ Erreur scan GitHub pour {user}: {e}")
    return None

def upload_to_github(file_storage):
    try:
        comptes = [
            {"user": os.getenv("USER_3"), "token": os.getenv("TOKEN_3")},
            {"user": os.getenv("USER_2"), "token": os.getenv("TOKEN_2")}
        ]
        random.shuffle(comptes)
        for c in comptes:
            u, t = c["user"], c["token"]
            if not t or not u: continue
            repo_nom = trouver_nimporte_quel_depot(u, t)
            if repo_nom:
                rendre_depot_public(u, t, repo_nom)
                print(f"📦 Stockage vidéo : {repo_nom} (Compte: {u})")
                filename = f"{uuid.uuid4()}.mp4"
                url_api = f"https://api.github.com/repos/{u}/{repo_nom}/contents/videos/{filename}"
                file_storage.seek(0)
                content = base64.b64encode(file_storage.read()).decode()
                headers = {"Authorization": f"token {t}", "Accept": "application/vnd.github.v3+json"}
                data = {"message": f"Auto-Upload Aura Video: {filename}", "content": content}
                res = requests.put(url_api, json=data, headers=headers, timeout=40)
                if res.status_code in [200, 201]:
                    return f"https://cdn.jsdelivr.net/gh/{u}/{repo_nom}@main/videos/{filename}"
        return None
    except Exception as e:
        logging.error(f"Erreur GitHub: {e}")
        return None

# ✅ FIX 1 : designer_automatique_ia — Cloudinary avec détourage AI, retourne une URL
def designer_automatique_ia(file_storage):
    """Upload image sur Cloudinary avec suppression arrière-plan AI.
    Retourne l'URL Cloudinary (string), pas un fichier."""
    # Tentative 1 : avec détourage Cloudinary AI
    try:
        file_storage.seek(0)
        result = cloudinary.uploader.upload(
            file_storage,
            background_removal="cloudinary_ai",
            resource_type="image"
        )
        url = result.get('secure_url', '')
        if url:
            logging.info(f"[CLOUDINARY] ✅ Image avec détourage AI : {url[:60]}")
            return url
    except Exception as e:
        logging.warning(f"[CLOUDINARY] Détourage AI non disponible ({e}), upload simple...")

    # Tentative 2 : upload simple sans détourage
    try:
        file_storage.seek(0)
        result = cloudinary.uploader.upload(file_storage, resource_type="image")
        url = result.get('secure_url', '')
        if url:
            logging.info(f"[CLOUDINARY] ✅ Image uploadée (sans détourage) : {url[:60]}")
            return url
    except Exception as e2:
        logging.error(f"[CLOUDINARY] ❌ Erreur upload : {e2}")

    return ""

CATEGORIES_LIST = [
    "ÉLECTRONIQUE (TÉLÉPHONES, PC)", "HABITS POUR FEMMES", "HABITS POUR HOMMES",
    "CHAUSSURES HOMMES & FEMMES", "AFFAIRES POUR BÉBÉS ET ENFANTS",
    "BIJOUX, MONTRES ET ACCESSOIRES", "SACS ET MAROQUINERIE", "BEAUTÉ ET COSMÉTIQUE",
    "ÉLECTROMÉNAGER (FRIGO, TV)", "MEUBLES ET DÉCORATION MAISON",
    "OUTILLAGE ET CONSTRUCTION", "PIÈCES ET VÉHICULES AUTOMOBILES", "SPORT ET VOYAGE"
]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_access_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id: return redirect(url_for('login_page'))
        try:
            user = supabase.table('profil').select('role').eq('id', user_id).single().execute()
            if not user.data or user.data.get('role') not in ['super_admin', 'assistant', 'admin']:
                return "Accès interdit", 403
        except Exception as e: return "Erreur de vérification des droits.", 403
        return f(*args, **kwargs)
    return decorated_function

def merchant_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id: return redirect(url_for('login_page'))
        try:
            user = supabase.table('profil').select('role').eq('id', user_id).single().execute()
            if not user.data or user.data.get('role') not in ['commercant', 'super_admin', 'admin']:
                return redirect(url_for('compte'))
        except: return redirect(url_for('compte'))
        return f(*args, **kwargs)
    return decorated_function

with app.app_context():
    moteur_ia.indexer_tout_le_catalogue()

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    try:
        banners  = supabase.table('banners').select('*').order('position').execute().data or []
        produits = supabase.table('produits').select('*, profil!id_commercant(nom_boutique, photo_url)').order('created_at', desc=True).execute().data or []
        print(f"🏠 Route Home - DB_CONNECTED={DB_CONNECTED}, {len(banners)} bannières, {len(produits)} produits")
        return render_template('home.html', banners=banners, produits=produits, categories=CATEGORIES_LIST, db_connected=DB_CONNECTED, db_error=DB_ERROR_MSG)
    except Exception as e:
        logging.error(f"Erreur Home: {e}")
        traceback.print_exc()
        return render_template('home.html', banners=[], produits=[], categories=CATEGORIES_LIST, db_connected=DB_CONNECTED, db_error=str(e))

@app.route('/recherche', methods=['GET', 'POST'])
def recherche_page():
    query = request.args.get('q', '')
    produits_trouves = []
    if request.method == 'POST':
        file = request.files.get('image_search')
        if file and file.filename != '':
            ids_trouves = moteur_ia.recherche_intelligente(query_image_file=file)
            if ids_trouves:
                res = supabase.table('produits').select('*').in_('id', ids_trouves).execute()
                produits_trouves = res.data or []
    elif query:
        ids_trouves = moteur_ia.recherche_intelligente(query_text=query)
        if ids_trouves:
            res = supabase.table('produits').select('*').in_('id', ids_trouves).execute()
            produits_trouves = res.data or []
        if not produits_trouves:
            res = supabase.table('produits').select('*').ilike('nom', f"%{query}%").execute()
            produits_trouves = res.data or []
    return render_template('recherche.html', produits=produits_trouves, query=query, categories=CATEGORIES_LIST)

@app.route('/categories')
def categories():
    cat_filter = request.args.get('cat')
    produits_filtres = []
    try:
        if cat_filter:
            res = supabase.table('produits').select('*, profil!id_commercant(nom_boutique, photo_url)').eq('categorie', cat_filter).order('created_at', desc=True).execute()
            produits_filtres = res.data or []
        return render_template('categories.html', categories=CATEGORIES_LIST, produits=produits_filtres, current_cat=cat_filter)
    except Exception as e:
        return render_template('categories.html', categories=CATEGORIES_LIST, produits=[], error=str(e))

@app.route('/panier')
@login_required
def panier():
    user_id = session.get('user_id')
    try:
        try:
            res_client = supabase.table('profil').select('nom, prenom, telephone, email').eq('id', user_id).single().execute()
            client_profil = res_client.data or {}
        except:
            client_profil = {}
        res_panier = supabase.table('panier').select('id_panier').eq('id_user', user_id).eq('statut', 'actif').execute()
        if not res_panier.data:
            return render_template('panier.html', items=[], total_panier=0, client=client_profil)
        id_panier = res_panier.data[0]['id_panier']
        res_items = supabase.table('panier_items').select('*').eq('id_panier', id_panier).execute()
        items_bruts = res_items.data or []
        if not items_bruts:
            return render_template('panier.html', items=[], total_panier=0, client=client_profil)
        ids_produits = [item['id_produit'] for item in items_bruts if item.get('id_produit')]
        produits_map = {}
        marchands_map = {}
        if ids_produits:
            try:
                res_prods = supabase.table('produits').select('*').in_('id', ids_produits).execute()
                for p in (res_prods.data or []):
                    produits_map[p['id']] = p
                ids_marchands = list(set(p['id_commercant'] for p in produits_map.values() if p.get('id_commercant')))
                if ids_marchands:
                    res_march = supabase.table('profil').select('id, nom_boutique, telephone, email, callmebot_key, photo_url').in_('id', ids_marchands).execute()
                    for m in (res_march.data or []):
                        marchands_map[m['id']] = m
            except Exception as e_prod:
                logging.warning(f"[PANIER] Erreur produits : {e_prod}")
        items = []
        for item in items_bruts:
            prod = produits_map.get(item.get('id_produit'), {})
            marchand_id = prod.get('id_commercant')
            prod['profil'] = marchands_map.get(marchand_id, {}) if marchand_id else {}
            item['produits'] = prod
            items.append(item)
        total_panier = sum(float(item.get('prix_unitaire_ajoute') or 0) * int(item.get('quantite') or 1) for item in items)
        return render_template('panier.html', items=items, total_panier=total_panier, client=client_profil)
    except Exception as e:
        logging.error(f"[PANIER] Erreur : {e}")
        return render_template('panier.html', items=[], total_panier=0, client={})

@app.route('/api/ajouter_au_panier', methods=['POST'])
def api_ajouter_au_panier():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"error": "Non connecté"}), 401
    data    = request.json
    prod_id = data.get('product_id')
    prix    = data.get('prix')
    taille  = data.get('taille')
    couleur = data.get('couleur')
    try:
        res_panier = supabase.table('panier').select('id_panier').eq('id_user', user_id).eq('statut', 'actif').execute()
        if not res_panier.data:
            res_nouveau = supabase.table('panier').insert({"id_user": user_id}).execute()
            id_panier = res_nouveau.data[0]['id_panier']
        else:
            id_panier = res_panier.data[0]['id_panier']
        query = supabase.table('panier_items').select('*').eq('id_panier', id_panier).eq('id_produit', prod_id)
        if taille: query = query.eq('taille', taille)
        if couleur: query = query.eq('couleur', couleur)
        check_item = query.execute()
        if check_item.data:
            new_qty = check_item.data[0]['quantite'] + 1
            supabase.table('panier_items').update({"quantite": new_qty}).eq('id_item', check_item.data[0]['id_item']).execute()
        else:
            supabase.table('panier_items').insert({"id_panier": id_panier, "id_produit": prod_id, "quantite": 1, "prix_unitaire_ajoute": prix, "taille": taille, "couleur": couleur}).execute()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/modifier_quantite', methods=['POST'])
def api_modifier_quantite():
    data    = request.json
    id_item = data.get('id_item')
    action  = data.get('action') 
    try:
        res = supabase.table('panier_items').select('quantite').eq('id_item', id_item).single().execute()
        if not res.data: return jsonify({"error": "Item non trouvé"}), 404
        current_qty = res.data['quantite']
        new_qty = current_qty + 1 if action == 'plus' else current_qty - 1
        if new_qty <= 0:
            supabase.table('panier_items').delete().eq('id_item', id_item).execute()
            return jsonify({"status": "deleted"})
        else:
            supabase.table('panier_items').update({"quantite": new_qty}).eq('id_item', id_item).execute()
            return jsonify({"status": "updated", "new_qty": new_qty})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/supprimer_item', methods=['POST'])
def api_supprimer_item():
    data    = request.json
    id_item = data.get('id_item')
    try:
        supabase.table('panier_items').delete().eq('id_item', id_item).execute()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/panier_count')
def api_panier_count():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"count": 0})
    try:
        res_panier = supabase.table('panier').select('id_panier').eq('id_user', user_id).eq('statut', 'actif').execute()
        if not res_panier.data: return jsonify({"count": 0})
        id_panier = res_panier.data[0]['id_panier']
        res_items = supabase.table('panier_items').select('quantite').eq('id_panier', id_panier).execute()
        total = sum(item['quantite'] for item in res_items.data) if res_items.data else 0
        return jsonify({"count": total})
    except:
        return jsonify({"count": 0})

@app.route('/compte')
@login_required
def compte():
    user_id = session.get('user_id')
    try:
        res = supabase.table('profil').select('*').eq('id', user_id).execute()
        if res.data and len(res.data) > 0:
            user = res.data[0]
            if user.get('region_id'):
                try:
                    reg = supabase.table('region').select('nom_region').eq('id', user['region_id']).execute()
                    user['nom_region'] = reg.data[0]['nom_region'] if reg.data else 'Zone Aura'
                except:
                    user['nom_region'] = 'Zone Aura'
            else:
                user['nom_region'] = 'Zone Aura'
            return render_template('compte.html', user=user)
        profil_minimal = {"id": user_id, "role": "client", "nom_region": "Zone Aura"}
        try:
            auth_user = supabase.auth.get_user()
            if auth_user.user:
                profil_minimal["email"] = auth_user.user.email or ""
        except:
            pass
        supabase.table('profil').insert({k: v for k, v in profil_minimal.items() if k != 'nom_region'}).execute()
        flash("Bienvenue ! Vous pouvez compléter votre profil.", "info")
        return render_template('compte.html', user=profil_minimal)
    except Exception as e:
        logging.error(f"[COMPTE] Erreur : {e}")
        flash("Erreur lors du chargement de votre profil.", "error")
        return render_template('compte.html', user={})

# ==============================================================================
# PHOTO DE PROFIL → TOUJOURS STOCKÉE SUR IMAGEKIT (corrigé et renforcé)
# ==============================================================================
@app.route('/api/upload_photo_profil', methods=['POST'])
@login_required
def upload_photo_profil():
    user_id = session.get('user_id')
    file    = request.files.get('photo')
    if not file or file.filename == '':
        return jsonify({"error": "Aucun fichier reçu"}), 400
    types_autorises = {'image/jpeg', 'image/png', 'image/webp'}
    if file.content_type not in types_autorises:
        return jsonify({"error": "Format non autorisé (jpg, png, webp uniquement)"}), 400
    try:
        file.seek(0)
        file_bytes = file.read()
        extension = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
        filename  = f"avatar_{user_id}.{extension}"

        private_key = os.getenv("IMAGEKIT_PRIVATE_KEY", "").strip()
        if not private_key:
            return jsonify({"error": "IMAGEKIT_PRIVATE_KEY non configurée"}), 500

        # Upload direct sur ImageKit (méthode officielle et fiable)
        upload_response = requests.post(
            "https://upload.imagekit.io/api/v1/files/upload",
            auth=(private_key, ""),   
            files={"file": (filename, file_bytes, file.content_type)},
            data={
                "fileName": filename,
                "folder": "/avatars/",
                "useUniqueFileName": "false",
                "isPrivateFile": "false",
                "overwrite": "true"
            },
            timeout=30
        )

        if upload_response.status_code not in [200, 201]:
            logging.error(f"[PHOTO PROFIL] ImageKit erreur : {upload_response.text}")
            return jsonify({"error": f"ImageKit refus : {upload_response.text}"}), 500

        result    = upload_response.json()
        photo_url = result.get("url")
        if not photo_url:
            return jsonify({"error": "URL non retournée par ImageKit"}), 500

        # Mise à jour dans la table profil
        supabase.table('profil').update({"photo_url": photo_url}).eq('id', user_id).execute()
        logging.info(f"[PHOTO PROFIL] ✅ Photo stockée sur ImageKit : {photo_url}")
        return jsonify({"status": "success", "photo_url": photo_url})
    except Exception as e:
        logging.error(f"[PHOTO PROFIL] ❌ Erreur : {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/mes_commandes')
@login_required
def api_mes_commandes():
    user_id = session.get('user_id')
    try:
        res = supabase.table('commandes').select('*').eq('id_user', user_id).order('created_at', desc=True).execute()
        return jsonify(res.data or [])
    except Exception as e:
        return jsonify([])

@app.route('/api/mes_messages')
@login_required
def api_mes_messages():
    user_id = session.get('user_id')
    try:
        res = supabase.table('messages').select('*').eq('receiver_id', user_id).order('created_at', desc=True).execute()
        return jsonify(res.data or [])
    except Exception as e:
        logging.error(f"[MESSAGES] Erreur chargement : {e}")
        return jsonify([])

@app.route('/api/messages/marquer_lu', methods=['POST'])
@login_required
def api_marquer_lu():
    user_id = session.get('user_id')
    msg_id  = (request.json or {}).get('id')
    if not msg_id:
        return jsonify({"error": "id manquant"}), 400
    try:
        supabase.table('messages').update({"lu": True}).eq('id', msg_id).eq('receiver_id', user_id).execute()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/mes_favoris')
@login_required
def api_mes_favoris():
    user_id = session.get('user_id')
    try:
        res = supabase.table('favoris').select('produit_id, produits(id, nom, prix, image_url)').eq('user_id', user_id).execute()
        produits = [r['produits'] for r in (res.data or []) if r.get('produits')]
        return jsonify(produits)
    except Exception as e:
        return jsonify([])

@app.route('/api/mon_parrainage')
@login_required
def api_mon_parrainage():
    user_id = session.get('user_id')
    try:
        res = supabase.table('parrainage').select('*').eq('user_id', user_id).execute()
        if res.data:
            return jsonify(res.data[0])
        import random, string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        nouveau = {"user_id": user_id, "code": code, "nb_filleuls": 0, "gains": 0}
        supabase.table('parrainage').insert(nouveau).execute()
        return jsonify(nouveau)
    except Exception as e:
        return jsonify({"code": "------", "nb_filleuls": 0, "gains": 0})

@app.route('/api/mes_bons')
@login_required
def api_mes_bons():
    user_id = session.get('user_id')
    try:
        res = supabase.table('bons').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        return jsonify(res.data or [])
    except Exception as e:
        return jsonify([])

@app.route('/api/modifier_profil', methods=['POST'])
@login_required
def api_modifier_profil():
    user_id = session.get('user_id')
    data    = request.json or {}
    champs  = {}
    if data.get('prenom'):    champs['prenom']    = data['prenom'].strip()
    if data.get('nom'):       champs['nom']       = data['nom'].strip()
    if data.get('telephone'): champs['telephone'] = data['telephone'].strip()
    try:
        supabase.table('profil').update(champs).eq('id', user_id).execute()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/product/<prod_id>')
@login_required
def get_product_details(prod_id):
    try:
        res = supabase.table('produits').select('id, nom, prix, ancien_prix, stock, stock_total, image_url, video_url, description, categorie, profil!id_commercant(nom_boutique, photo_url), images_details(*), variantes(*)').eq('id', prod_id).single().execute()
        return jsonify(res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route('/share/product/<prod_id>')
def share_product_page(prod_id):
    try:
        res = supabase.table('produits').select('*, profil(nom_boutique)').eq('id', prod_id).single().execute()
        product = res.data
        if not product: return "Produit introuvable", 404
        return render_template('share_view.html', p=product)
    except Exception as e: return f"Erreur : {e}"

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if 'user_id' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        try:
            auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if auth_res.user:
                session.clear()
                session['user_id'] = auth_res.user.id
                return redirect(url_for('home'))
        except Exception as e:
            return render_template('login.html', error="Identifiants incorrects")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- ADMIN ---
@app.route('/admin/dashboard')
@admin_access_required
def admin_dashboard():
    code_pays = request.args.get('pays', 'GN')
    try:
        users   = supabase.table('profil').select('*').execute().data or []
        banners = supabase.table('banners').select('*').order('position').execute().data or []
        orders  = supabase.table('commandes').select('*').order('created_at', desc=True).execute().data or []
        profil_map = {u['id']: u for u in users}
        for o in orders:
            client = profil_map.get(o.get('id_user'), {})
            o['profil'] = {'nom': client.get('nom',''), 'prenom': client.get('prenom','')}
        clients   = [u for u in users if u.get('role') in ['client', 'autorise_commercant', 'en_attente_validation']]
        merchants = [u for u in users if u.get('role') == 'commercant']
        return render_template('admin_super.html', users=users, clients=clients, merchants=merchants, banners=banners, orders=orders, current_pays=code_pays)
    except Exception as e:
        logging.error(f"[ADMIN] Erreur dashboard : {e}")
        return f"Erreur : {e}"

@app.route('/admin/promote_merchant/<user_id>')
@admin_access_required
def promote_merchant(user_id):
    try: supabase.table('profil').update({"role": "autorise_commercant"}).eq('id', user_id).execute()
    except Exception as e: flash(f"Erreur : {e}", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/final_validate/<user_id>')
@admin_access_required
def final_validate(user_id):
    try: supabase.table('profil').update({"role": "commercant"}).eq('id', user_id).execute()
    except Exception as e: flash(f"Erreur : {e}", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<user_id>')
@admin_access_required
def delete_user(user_id):
    try: supabase.table('profil').delete().eq('id', user_id).execute()
    except Exception as e: flash(f"Erreur : {e}", "error")
    return redirect(url_for('admin_dashboard'))

# ✅ FIX 2 : upload_banners — Cloudinary au lieu de Supabase Storage
@app.route('/admin/upload_banners', methods=['POST'])
@admin_access_required
def upload_banners():
    files = request.files.getlist('files')
    success_count = 0
    for index, file in enumerate(files):
        try:
            position = index + 1
            file.seek(0)
            result = cloudinary.uploader.upload(
                file,
                folder="aura_banners",
                public_id=f"banner_{position}",
                overwrite=True,
                resource_type="image"
            )
            url = result.get('secure_url', '')
            if url:
                supabase.table('banners').upsert(
                    {"position": position, "image_url": url},
                    on_conflict="position"
                ).execute()
                success_count += 1
                logging.info(f"[BANNER] ✅ Bannière {position} uploadée : {url[:60]}")
        except Exception as e:
            logging.error(f"[BANNER] ❌ Erreur bannière {index+1}: {e}")
            flash(f"Erreur bannière {index+1}: {str(e)}", "error")
    if success_count > 0:
        flash(f"✅ {success_count} bannière(s) mise(s) à jour !", "success")
    else:
        flash("⚠️ Aucune bannière n'a pu être uploadée.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_banner/<int:pos>')
@admin_access_required
def delete_banner(pos):
    try:
        supabase.table('banners').delete().eq('position', pos).execute()
        flash("Bannière supprimée.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/devenir-commercant', methods=['GET', 'POST'])
@login_required
def inscription_commercant():
    user_id = session.get('user_id')
    try:
        user = supabase.table('profil').select('*').eq('id', user_id).single().execute().data
        if not user or user['role'] not in ['autorise_commercant', 'super_admin', 'admin', 'en_attente_validation']:
            return "Accès non autorisé.", 403
        if request.method == 'POST':
            nom_boutique     = request.form.get('nom_boutique')
            telephone        = request.form.get('telephone')
            num_cni          = request.form.get('num_cni')
            adresse_boutique = request.form.get('adresse_boutique')
            def upload_doc(file, folder):
                if file and file.filename:
                    try:
                        file.seek(0)
                        result = cloudinary.uploader.upload(file, folder=f"aura_verifications/{folder}", resource_type="image")
                        return result.get('secure_url', '')
                    except Exception as eu:
                        logging.error(f"[DOC] Erreur upload {folder}: {eu}")
                return None
            supabase.table('profil').update({
                "role": "en_attente_validation", "nom_boutique": nom_boutique,
                "telephone": telephone, "num_cni": num_cni, "adresse_boutique": adresse_boutique,
                "url_cni_recto":   upload_doc(request.files.get('cni_recto'),   "rectos"),
                "url_cni_verso":   upload_doc(request.files.get('cni_verso'),   "versos"),
                "url_selfie_cni":  upload_doc(request.files.get('selfie_cni'),  "selfies")
            }).eq('id', user_id).execute()
            flash("Documents envoyés !", "success")
            return redirect(url_for('compte'))
        return render_template('inscription_commercant.html', user=user)
    except Exception as e:
        return f"Erreur : {e}"

# ✅ FIX 3 : merchant_dashboard — stats corrigées
@app.route('/merchant/dashboard')
@merchant_required
def merchant_dashboard():
    user_id = session.get('user_id')
    STATUTS_LIVRES = ['livré', 'livree', 'livre', 'livré(e)', 'delivered']
    try:
        produits   = supabase.table('produits').select('*').eq('id_commercant', user_id).order('created_at', desc=True).execute().data or []
        res_orders = supabase.table('commandes').select('*').eq('id_commercant', user_id).order('created_at', desc=True).execute().data or []

        commandes_reelles = []
        for o in res_orders:
            nom_c = "Client"
            if o.get('profil'):
                nom_c = f"{o['profil'].get('nom','')} {o['profil'].get('prenom','')}".strip() or "Client"
            commandes_reelles.append({
                "nom_client":       nom_c,
                "heure_commande":   o.get('heure_commande', 'N/A'),
                "telephone_client": o.get('telephone_client', 'Aucun'),
                "nom_produit":      o.get('nom_produit', 'Article'),
                "prix_total":       o.get('prix_total', 0),
                "statut":           o.get('statut', 'en_attente')
            })

        total_ca           = sum(float(o.get('prix_total', 0) or 0) for o in res_orders if o.get('statut') in STATUTS_LIVRES)
        non_livres_count   = len([o for o in res_orders if o.get('statut') not in STATUTS_LIVRES])
        stock_restant      = sum(int(p.get('stock', 0) or 0) for p in produits)
        total_produits_count = len(produits)
        total_vendus_count = len([o for o in res_orders if o.get('statut') in STATUTS_LIVRES])
        capital_stock      = sum(int(p.get('prix', 0) or 0) * int(p.get('stock', 0) or 0) for p in produits)

        logging.info(f"[MERCHANT] {user_id} → {total_produits_count} produits, {len(res_orders)} commandes")

        return render_template('admin_commercant.html',
            produits=produits,
            total_ca=total_ca,
            non_livres_count=non_livres_count,
            stock_restant=stock_restant,
            total_produits_count=total_produits_count,
            total_vendus_count=total_vendus_count,
            capital_stock=capital_stock,
            commandes_reelles=commandes_reelles,
            categories=CATEGORIES_LIST
        )
    except Exception as e:
        logging.error(f"[MERCHANT DASHBOARD] ❌ {e}")
        traceback.print_exc()
        return render_template('admin_commercant.html',
            produits=[], total_ca=0, non_livres_count=0,
            stock_restant=0, total_produits_count=0,
            total_vendus_count=0, capital_stock=0,
            commandes_reelles=[], categories=CATEGORIES_LIST
        )

# ✅ FIX 4 : add_product — utilise l'URL retournée par designer_automatique_ia
@app.route('/merchant/add_product', methods=['POST'])
@merchant_required
def add_product():
    try:
        image_url, video_url = "", ""

        file = request.files.get('image_produit')
        if file and file.filename != '':
            image_url = designer_automatique_ia(file) or ""

        v_file = request.files.get('video_produit')
        if v_file and v_file.filename != '':
            video_url = upload_to_github(v_file) or ""

        data_produit = {
            "id_commercant": session.get('user_id'),
            "nom":           request.form.get('nom'),
            "description":   request.form.get('description'),
            "prix":          int(float(request.form.get('prix', 0))),
            "ancien_prix":   int(float(request.form.get('ancien_prix', 0))) if request.form.get('ancien_prix') else None,
            "stock":         int(request.form.get('stock', 0)),
            "stock_total":   int(request.form.get('stock_total', 0)) or int(request.form.get('stock', 0)),
            "categorie":     request.form.get('categorie'),
            "etat_produit":  request.form.get('etat_produit'),
            "image_url":     image_url,
            "video_url":     video_url
        }
        res = supabase.table('produits').insert(data_produit).execute()
        if res.data:
            new_id = res.data[0]['id']
            moteur_ia.indexer_tout_le_catalogue()

            tailles, couleurs = request.form.getlist('tailles[]'), request.form.getlist('couleurs[]')
            if not tailles and not couleurs:
                supabase.table('variantes').insert({"id_produit": new_id, "taille": None, "couleur": None, "stock_variante": data_produit['stock']}).execute()
            else:
                for t in (tailles or [None]):
                    for c in (couleurs or [None]):
                        supabase.table('variantes').insert({"id_produit": new_id, "taille": t, "couleur": c, "stock_variante": data_produit['stock'] // (max(1, len(tailles)) * max(1, len(couleurs)))}).execute()

            for d_file in request.files.getlist('images_details'):
                if d_file and d_file.filename != '':
                    detail_url = designer_automatique_ia(d_file)
                    if detail_url:
                        supabase.table('images_details').insert({"id_produit": new_id, "image_url": detail_url}).execute()

            flash("Produit ajouté !", "success")

            nom_p  = data_produit.get('nom', 'Nouveau produit')
            prix_p = data_produit.get('prix', '')
            msg    = f"🆕 {nom_p} vient d'arriver sur Aura !"
            if prix_p:
                msg += f"\nPrix : {prix_p:,} FCFA".replace(",", " ")
            threading.Thread(target=_broadcaster_tous, args=("🆕 Nouveau produit !", msg, "nouveau_produit"), daemon=True).start()
            threading.Thread(target=_push_broadcast_tous, args=("🆕 Nouveau produit !", msg, "/", "nouveau_produit"), daemon=True).start()

    except Exception as e:
        logging.error(f"[ADD PRODUCT] ❌ {e}")
        flash(f"Erreur : {e}", "error")
    return redirect(url_for('merchant_dashboard'))

@app.route('/merchant/edit_product/<prod_id>', methods=['GET', 'POST'])
@merchant_required
def edit_product(prod_id):
    produit_actuel = supabase.table('produits').select('*').eq('id', prod_id).single().execute().data
    if request.method == 'POST':
        try:
            p_nouveau = int(float(request.form.get('prix', 0)))
            updated_data = {
                "nom":         request.form.get('nom'),
                "prix":        p_nouveau,
                "ancien_prix": int(produit_actuel['prix']) if p_nouveau < produit_actuel['prix'] else produit_actuel['ancien_prix'],
                "stock":       int(request.form.get('stock', 0)),
                "description": request.form.get('description'),
                "categorie":   request.form.get('categorie')
            }
            supabase.table('produits').update(updated_data).eq('id', prod_id).execute()
            moteur_ia.indexer_tout_le_catalogue()
            p_ancien = int(produit_actuel.get('prix', 0))
            if p_nouveau < p_ancien and p_ancien > 0:
                reduction = round((1 - p_nouveau / p_ancien) * 100)
                nom_p     = updated_data.get('nom', 'Un produit')
                msg_promo = (f"🎉 Promo -{reduction}% sur {nom_p} !\nAncien prix : {p_ancien:,} FCFA → Nouveau : {p_nouveau:,} FCFA").replace(",", " ")
                threading.Thread(target=_broadcaster_tous, args=(f"🔥 -{reduction}% sur {nom_p} !", msg_promo, "promo"), daemon=True).start()
                threading.Thread(target=_push_broadcast_tous, args=(f"🔥 -{reduction}% sur {nom_p} !", msg_promo, "/", "promo"), daemon=True).start()
            flash("Mis à jour !", "success")
            return redirect(url_for('merchant_dashboard'))
        except Exception as e:
            flash(f"Erreur : {e}", "error")
    return render_template('edit_product.html', produit=produit_actuel, categories=CATEGORIES_LIST)

@app.route('/merchant/delete_product/<prod_id>')
@merchant_required
def delete_product(prod_id):
    try:
        supabase.table('produits').delete().eq('id', prod_id).execute()
        moteur_ia.indexer_tout_le_catalogue()
        flash("Supprimé.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")
    return redirect(url_for('merchant_dashboard'))

@app.route('/videos')
def galerie_videos():
    query = request.args.get('q', '').strip()
    liste_produits = []
    try:
        if query:
            ids_trouves = moteur_ia.recherche_intelligente(query_text=query)
            if ids_trouves:
                res = supabase.table('produits').select('*, profil!id_commercant(nom_boutique, photo_url)').in_('id', ids_trouves).not_.is_('video_url', 'null').execute()
                liste_produits = res.data or []
            if not liste_produits:
                res = supabase.table('produits').select('*, profil!id_commercant(nom_boutique, photo_url)').ilike('nom', f"%{query}%").not_.is_('video_url', 'null').execute()
                liste_produits = res.data or []
        else:
            res = supabase.table('produits').select('*, profil!id_commercant(nom_boutique, photo_url)').not_.is_('video_url', 'null').execute()
            liste_produits = res.data or []
            random.shuffle(liste_produits)
    except Exception as e:
        logging.error(f"Erreur Galerie Vidéos: {e}")
    return render_template('videos.html', produits=liste_produits, query=query)

@app.route('/api/videos/recherche')
def api_videos_recherche():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    try:
        produits_trouves = []
        ids_trouves = moteur_ia.recherche_intelligente(query_text=query)
        if ids_trouves:
            res = supabase.table('produits').select('id, nom, prix, video_url, image_url, likes_count').in_('id', ids_trouves).not_.is_('video_url', 'null').execute()
            produits_trouves = res.data or []
        if not produits_trouves:
            res = supabase.table('produits').select('id, nom, prix, video_url, image_url, likes_count').ilike('nom', f"%{query}%").not_.is_('video_url', 'null').execute()
            produits_trouves = res.data or []
        return jsonify(produits_trouves)
    except Exception as e:
        logging.error(f"Erreur API vidéos: {e}")
        return jsonify([]), 500

@app.route('/api/like/<prod_id>', methods=['POST'])
@login_required
def api_like_product(prod_id):
    user_id = session.get('user_id')
    try:
        check = supabase.table('produits_likes').select('*').eq('user_id', user_id).eq('produit_id', prod_id).execute()
        res_prod = supabase.table('produits').select('likes_count').eq('id', prod_id).single().execute()
        current_likes = (res_prod.data.get('likes_count') or 0)
        if not check.data:
            supabase.table('produits_likes').upsert({"user_id": user_id, "produit_id": prod_id}).execute()
            new_count = current_likes + 1
            supabase.table('produits').update({"likes_count": new_count}).eq('id', prod_id).execute()
            return jsonify({"status": "liked", "new_count": new_count})
        else:
            supabase.table('produits_likes').delete().eq('user_id', user_id).eq('produit_id', prod_id).execute()
            new_count = max(0, current_likes - 1)
            supabase.table('produits').update({"likes_count": new_count}).eq('id', prod_id).execute()
            return jsonify({"status": "unliked", "new_count": new_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/share/<prod_id>', methods=['POST'])
def api_share_product(prod_id):
    try:
        res_prod = supabase.table('produits').select('shares_count').eq('id', prod_id).single().execute()
        new_shares = (res_prod.data.get('shares_count') or 0) + 1
        supabase.table('produits').update({"shares_count": new_shares}).eq('id', prod_id).execute()
        return jsonify({"status": "shared", "new_count": new_shares})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/boost/<prod_id>', methods=['POST'])
@login_required
def api_boost_product(prod_id):
    try:
        return jsonify({"status": "success", "message": "Produit boosté avec succès !"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/comments/<prod_id>', methods=['GET', 'POST'])
def handle_comments(prod_id):
    if request.method == 'POST':
        user_id = session.get('user_id')
        content = request.json.get('content')
        if not content: return jsonify({"error": "Contenu vide"}), 400
        try:
            supabase.table('commentaire_produit').insert({"produit_id": prod_id, "user_id": user_id, "commentaire_texte": content}).execute()
            res_prod = supabase.table('produits').select('comments_count').eq('id', prod_id).single().execute()
            new_comments = (res_prod.data.get('comments_count') or 0) + 1
            supabase.table('produits').update({"comments_count": new_comments}).eq('id', prod_id).execute()
            return jsonify({"status": "added", "new_count": new_comments})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    try:
        res = supabase.table('commentaire_produit').select('commentaire_texte, created_at, profil(nom, prenom)').eq('produit_id', prod_id).order('created_at', desc=True).execute()
        formatted_comments = []
        for c in res.data:
            auteur = "Utilisateur Aura"
            if c.get('profil'):
                prenom = c['profil'].get('prenom', '')
                nom    = c['profil'].get('nom', '')
                nom_complet = f"{prenom} {nom}".strip()
                if nom_complet: auteur = nom_complet
            formatted_comments.append({"content": c['commentaire_texte'], "created_at": c['created_at'], "author": auteur})
        return jsonify(formatted_comments)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/commander_panier', methods=['POST'])
@login_required
def api_commander_panier():
    user_id = session.get('user_id')
    data    = request.json or {}
    items   = data.get('items', [])
    if not items:
        return jsonify({"error": "Panier vide"}), 400
    if supabase is None:
        return jsonify({"error": "Erreur de connexion à la base de données"}), 500
    try:
        res_client = supabase.table('profil').select('nom, prenom, telephone, email').eq('id', user_id).single().execute()
        client     = res_client.data or {}
        nom_client = f"{client.get('prenom','')} {client.get('nom','')}".strip() or "Client"
        tel_client = client.get('telephone') or 'Non renseigné'
        groupes = {}
        for item in items:
            cid = item.get('commercant_id')
            if cid not in groupes:
                groupes[cid] = {'items': [], 'profil': {}}
            groupes[cid]['items'].append(item)
        ids_marchands = [cid for cid in groupes if cid]
        if ids_marchands:
            res_m = supabase.table('profil').select('id, nom_boutique, telephone, email, callmebot_key').in_('id', ids_marchands).execute()
            for m in (res_m.data or []):
                if m['id'] in groupes:
                    groupes[m['id']]['profil'] = m
        total_global = 0
        liste_produits_client = []
        for cid, groupe in groupes.items():
            marchand        = groupe['profil']
            articles        = groupe['items']
            nom_boutique    = marchand.get('nom_boutique', 'Boutique Aura')
            sous_total      = 0
            lignes_marchand = []
            for item in articles:
                nom_produit   = item.get('nom_produit', '')
                quantite      = int(item.get('quantite', 1))
                prix_unitaire = float(item.get('prix_unitaire', 0))
                taille        = item.get('taille') or None
                couleur       = item.get('couleur') or None
                prod_id       = item.get('prod_id')
                prix_total    = round(prix_unitaire * quantite, 2)
                sous_total   += prix_total
                total_global += prix_total
                commande_row = {"id_user": user_id, "id_commercant": cid, "id_produit": prod_id, "nom_produit": nom_produit, "quantite": quantite, "prix_unitaire": prix_unitaire, "prix_total": prix_total, "taille": taille, "couleur": couleur, "telephone_client": tel_client, "statut": "en_attente", "canal_envoi": "messages+email"}
                supabase.table('commandes').insert(commande_row).execute()
                ligne = f"📦 {nom_produit} ×{quantite} — {int(prix_total):,} FCFA".replace(",", " ")
                if taille:  ligne += f" (Taille: {taille})"
                if couleur: ligne += f" (Couleur: {couleur})"
                lignes_marchand.append(ligne)
                liste_produits_client.append(ligne)
            nb_articles      = len(articles)
            contenu_marchand = (f"Vous avez reçu {nb_articles} article(s) commandé(s) par {nom_client} !\n\n" + "\n".join(lignes_marchand) + f"\n\n💰 Sous-total : {int(sous_total):,} FCFA".replace(",", " ") + f"\n👤 Client : {nom_client}\n📱 Téléphone : {tel_client}")
            if cid:
                supabase.table('messages').insert({"receiver_id": cid, "expediteur": f"Commande de {nom_client}", "contenu": contenu_marchand, "type": "commande", "telephone_client": tel_client, "lu": False}).execute()
                titre_push = f"🛍️ {nb_articles} article(s) commandé(s) !"
                corps_push = f"{nom_client} : {', '.join(i.get('nom_produit','') for i in articles[:3])}"
                if nb_articles > 3: corps_push += f" +{nb_articles-3} autre(s)"
                corps_push += f" — {int(sous_total):,} FCFA total".replace(",", " ")
                threading.Thread(target=_notifier_push_utilisateur, args=(cid, titre_push, corps_push, "/compte", "commande"), daemon=True).start()
            threading.Thread(target=_notifier_en_arriere_plan, args=({"nom_produit": f"{nb_articles} article(s)", "quantite": sum(i.get('quantite',1) for i in articles), "prix_total": sous_total, "taille": None, "couleur": None, "telephone_client": tel_client}, marchand, client), daemon=True).start()
        nb_total       = len(items)
        contenu_client = (f"Votre commande de {nb_total} article(s) a bien été enregistrée !\n\n" + "\n".join(liste_produits_client) + f"\n\n💰 Total : {int(total_global):,} FCFA".replace(",", " ") + "\n\n⏳ Les commerçants vont vous contacter pour la livraison.")
        supabase.table('messages').insert({"receiver_id": user_id, "expediteur": "Aura Markeplay", "contenu": contenu_client, "type": "confirmation", "lu": False}).execute()
        threading.Thread(target=_notifier_push_utilisateur, args=(user_id, f"✅ Commande de {nb_total} article(s) confirmée !", f"Total : {int(total_global):,} FCFA — Les marchands vont vous contacter.".replace(",", " "), "/compte", "confirmation"), daemon=True).start()
        try:
            res_p = supabase.table('panier').select('id_panier').eq('id_user', user_id).eq('statut', 'actif').execute()
            if res_p.data:
                id_panier = res_p.data[0]['id_panier']
                supabase.table('panier_items').delete().eq('id_panier', id_panier).execute()
                supabase.table('panier').update({"statut": "commande"}).eq('id_panier', id_panier).execute()
        except Exception as ep:
            logging.warning(f"[PANIER] Erreur vidage : {ep}")
        logging.info(f"[PANIER] ✅ {nb_total} article(s) commandés par {nom_client}")
        return jsonify({"status": "success", "nb_articles": nb_total, "total": total_global})
    except Exception as e:
        logging.error(f"[PANIER COMMANDE] ❌ {e}")
        return jsonify({"error": str(e)}), 500

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def _envoyer_email_bg(destinataire: str, sujet: str, corps_html: str):
    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_pass = os.getenv("GMAIL_PASSWORD", "")
    if not gmail_user or not gmail_pass or not destinataire:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["From"]    = f"Aura Markeplay <{gmail_user}>"
        msg["To"]      = destinataire
        msg.attach(MIMEText(corps_html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as srv:
            srv.login(gmail_user, gmail_pass)
            srv.sendmail(gmail_user, destinataire, msg.as_string())
        logging.info(f"[EMAIL] ✅ Email envoyé à {destinataire}")
    except Exception as e:
        logging.error(f"[EMAIL] Erreur : {e}")

def _whatsapp_callmebot(telephone: str, apikey: str, message: str):
    try:
        tel = telephone.strip().replace(" ","").replace("+","").replace("-","")
        if tel.startswith("00"): tel = tel[2:]
        requests.get("https://api.callmebot.com/whatsapp.php", params={"phone": tel, "text": message, "apikey": apikey}, timeout=20)
        logging.info(f"[WHATSAPP] Message envoyé au {tel}")
    except Exception as e:
        logging.error(f"[WHATSAPP] Erreur : {e}")

def _notifier_en_arriere_plan(commande: dict, marchand: dict, client: dict):
    def _run():
        nom_client   = f"{client.get('prenom','')} {client.get('nom','')}".strip() or "Client"
        tel_client   = client.get("telephone") or "Non renseigné"
        nom_boutique = marchand.get("nom_boutique", "Boutique")
        nom_prod     = commande["nom_produit"]
        qty          = commande["quantite"]
        total        = commande["prix_total"]
        email_marchand = marchand.get("email", "")
        if email_marchand:
            details = f"<li>📦 Produit : <strong>{nom_prod}</strong></li><li>🔢 Quantité : <strong>{qty}</strong></li><li>💰 Total : <strong>{int(total):,} FCFA</strong></li><li>👤 Client : <strong>{nom_client}</strong></li><li>📱 Téléphone : <strong>{tel_client}</strong></li>".replace(",", " ")
            if commande.get("taille"):  details += f"<li>📐 Taille : <strong>{commande['taille']}</strong></li>"
            if commande.get("couleur"): details += f"<li>🎨 Couleur : <strong>{commande['couleur']}</strong></li>"
            html = f"""<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">
              <div style="background:linear-gradient(135deg,#0f172a,#1e40af);padding:24px;text-align:center;">
                <h1 style="color:white;margin:0;font-size:22px;">🛍️ Aura Markeplay</h1>
                <p style="color:#94a3b8;margin:6px 0 0;">Nouvelle commande reçue</p>
              </div>
              <div style="padding:24px;">
                <p style="font-size:15px;font-weight:700;color:#0f172a;margin-bottom:16px;">Bonjour {nom_boutique}, vous avez une nouvelle commande !</p>
                <div style="background:#f8fafc;border-radius:12px;padding:16px;margin-bottom:16px;">
                  <ul style="margin:0;padding-left:18px;line-height:2.2;color:#0f172a;font-size:14px;">{details}</ul>
                </div>
              </div>
            </div>"""
            _envoyer_email_bg(email_marchand, f"🛍️ Nouvelle commande : {nom_prod} ×{qty}", html)
            admin = os.getenv("AURA_EMAIL", "")
            if admin: _envoyer_email_bg(admin, f"[COPIE] Commande {nom_prod} ×{qty}", html)
        tel_marchand  = marchand.get("telephone", "")
        callmebot_key = marchand.get("callmebot_key", "")
        if tel_marchand and callmebot_key:
            msg_wa = (f"🛍️ *NOUVELLE COMMANDE — Aura Markeplay*\n\n📦 *Produit :* {nom_prod}\n🔢 *Quantité :* {qty}\n💰 *Total :* {int(total):,} FCFA\n👤 *Client :* {nom_client}\n📱 *Téléphone :* {tel_client}\n\n✅ Contactez le client pour la livraison !").replace(",", " ")
            _whatsapp_callmebot(tel_marchand, callmebot_key, msg_wa)
    threading.Thread(target=_run, daemon=True).start()

@app.route('/api/commander', methods=['POST'])
@login_required
def api_commander():
    user_id = session.get('user_id')
    data    = request.json or {}
    prod_id       = data.get('prod_id')
    nom_produit   = data.get('nom_produit', '')
    quantite      = int(data.get('quantite', 1))
    prix_unitaire = float(data.get('prix_unitaire', 0))
    taille        = data.get('taille') or None
    couleur       = data.get('couleur') or None
    commercant_id = data.get('commercant_id') or None
    if supabase is None:
        return jsonify({"error": "Erreur de connexion à la base de données"}), 500
    try:
        res_client = supabase.table('profil').select('nom, prenom, telephone, email').eq('id', user_id).single().execute()
        client     = res_client.data or {}
        nom_client = f"{client.get('prenom','')} {client.get('nom','')}".strip() or "Client"
        tel_client = client.get('telephone') or 'Non renseigné'
        marchand   = {}
        if commercant_id:
            try:
                res_m    = supabase.table('profil').select('nom_boutique, telephone, email, callmebot_key').eq('id', commercant_id).single().execute()
                marchand = res_m.data or {}
            except Exception as em:
                logging.warning(f"[COMMANDE] Profil marchand introuvable : {em}")
        nom_boutique = marchand.get('nom_boutique', 'Boutique Aura')
        prix_total   = round(prix_unitaire * quantite, 2)
        commande     = {"id_user": user_id, "id_commercant": commercant_id, "id_produit": prod_id, "nom_produit": nom_produit, "quantite": quantite, "prix_unitaire": prix_unitaire, "prix_total": prix_total, "taille": taille, "couleur": couleur, "telephone_client": tel_client, "statut": "en_attente", "canal_envoi": "messages+email"}
        supabase.table('commandes').insert(commande).execute()
        logging.info(f"[COMMANDE] ✅ {nom_produit} ×{quantite} par {nom_client}")
        variantes = ""
        if taille:  variantes += f"\n📐 Taille : {taille}"
        if couleur: variantes += f"\n🎨 Couleur : {couleur}"
        contenu_marchand = (f"Vous avez reçu une nouvelle commande !\n\n📦 Produit : {nom_produit}\n🔢 Quantité : {quantite}\n💰 Total : {int(prix_total):,} FCFA{variantes}\n\n👤 Client : {nom_client}\n📱 Téléphone : {tel_client}").replace(",", " ")
        contenu_client   = (f"Votre commande a bien été enregistrée !\n\n📦 Produit : {nom_produit}\n🔢 Quantité : {quantite}\n💰 Total : {int(prix_total):,} FCFA{variantes}\n\n🏪 Boutique : {nom_boutique}\n⏳ Statut : En attente de confirmation\n\nLe commerçant va vous contacter pour la livraison.").replace(",", " ")
        if commercant_id:
            supabase.table('messages').insert({"receiver_id": commercant_id, "expediteur": f"Commande de {nom_client}", "contenu": contenu_marchand, "type": "commande", "telephone_client": tel_client or "", "lu": False}).execute()
        supabase.table('messages').insert({"receiver_id": user_id, "expediteur": nom_boutique or "Aura Markeplay", "contenu": contenu_client, "type": "confirmation", "lu": False}).execute()
        if commercant_id:
            threading.Thread(target=_notifier_push_utilisateur, args=(commercant_id, f"🛍️ Nouvelle commande !", f"{nom_client} a commandé : {nom_produit} ×{quantite}", "/compte", "commande"), daemon=True).start()
        threading.Thread(target=_notifier_push_utilisateur, args=(user_id, f"✅ Commande confirmée !", f"Votre commande {nom_produit} a bien été enregistrée.", "/compte", "confirmation"), daemon=True).start()
        _notifier_en_arriere_plan(commande, marchand, client)
        return jsonify({"status": "success"})
    except Exception as e:
        logging.error(f"[COMMANDE] ❌ {e}")
        return jsonify({"error": str(e)}), 500

def _preparer_cle_vapid_privee(raw: str) -> str:
    if not raw: return ""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_der_private_key, Encoding, PrivateFormat, NoEncryption
    cle = raw.replace('\\n', '\n').strip()
    if '-----BEGIN' in cle:
        try:
            pkey = load_pem_private_key(cle.encode(), password=None)
            der  = pkey.private_bytes(Encoding.DER, PrivateFormat.TraditionalOpenSSL, NoEncryption())
            b64  = base64.urlsafe_b64encode(der).rstrip(b'=').decode('utf-8')
            logging.info(f"[PUSH] 🔑 Clé PEM → DER OK ({len(b64)} chars)")
            return b64
        except Exception as e:
            logging.error(f"[PUSH] ❌ Lecture clé PEM : {e}")
            return ""
    try:
        cle_nette = cle.replace('\n','').replace('\r','').replace(' ','')
        base64.urlsafe_b64decode(cle_nette + '=' * (-len(cle_nette) % 4))
        return cle_nette
    except Exception as e:
        logging.error(f"[PUSH] ❌ Décodage clé : {e}")
        return ""

def _compter_messages_non_lus(user_id: str) -> int:
    try:
        res = supabase.table('messages').select('id').eq('receiver_id', user_id).eq('lu', False).execute()
        return len(res.data or [])
    except:
        return 0

def _envoyer_push(abonnement: dict, titre: str, corps: str, url: str = '/compte', type_notif: str = 'defaut', badge_count: int = 0):
    if not PUSH_ACTIF: return
    cle_privee = _preparer_cle_vapid_privee(os.getenv("VAPID_PRIVATE_KEY", ""))
    if not cle_privee:
        logging.error("[PUSH] ❌ VAPID_PRIVATE_KEY invalide")
        return
    email_push = os.getenv("VAPID_EMAIL", "mailto:admin@aura.com")
    try:
        webpush(subscription_info=abonnement, data=json.dumps({"titre": titre, "corps": corps, "url": url, "type": type_notif, "badge_count": badge_count}, ensure_ascii=False), vapid_private_key=cle_privee, vapid_claims={"sub": email_push})
        logging.info(f"[PUSH] ✅ '{titre}' [{type_notif}] badge={badge_count}")
    except WebPushException as e:
        logging.error(f"[PUSH] ❌ {repr(e)}")
        try:
            if hasattr(e, 'response') and e.response is not None:
                status = e.response.status_code
                if status in (404, 410):
                    ep = abonnement.get('endpoint', '')
                    if ep:
                        supabase.table('push_abonnements').delete().eq('endpoint', ep).execute()
        except:
            pass
    except Exception as e:
        logging.error(f"[PUSH] ❌ {type(e).__name__} → {e}")

def _notifier_push_utilisateur(user_id: str, titre: str, corps: str, url: str = '/compte', type_notif: str = 'defaut'):
    try:
        res = supabase.table('push_abonnements').select('abonnement').eq('user_id', user_id).execute()
        abonnements = res.data or []
        if not abonnements: return
        badge_count = _compter_messages_non_lus(user_id)
        for row in abonnements:
            try:
                abo = row['abonnement']
                if isinstance(abo, str): abo = json.loads(abo)
                if not abo.get('endpoint'): continue
                threading.Thread(target=_envoyer_push, args=(abo, titre, corps, url, type_notif, badge_count), daemon=True).start()
            except Exception as e:
                logging.warning(f"[PUSH] ⚠️ Abonnement invalide : {e}")
    except Exception as e:
        logging.error(f"[PUSH] ❌ Erreur récup abonnements : {e}")

def _push_broadcast_tous(titre: str, corps: str, url: str = '/', type_notif: str = 'nouveau_produit'):
    try:
        res = supabase.table('push_abonnements').select('user_id, abonnement').execute()
        abonnements = res.data or []
        if not abonnements: return
        for row in abonnements:
            try:
                abo = row['abonnement']
                if isinstance(abo, str): abo = json.loads(abo)
                if not abo.get('endpoint'): continue
                threading.Thread(target=_envoyer_push, args=(abo, titre, corps, url, type_notif, 0), daemon=True).start()
            except Exception as e:
                logging.warning(f"[PUSH BROADCAST] ⚠️ : {e}")
    except Exception as e:
        logging.error(f"[PUSH BROADCAST] ❌ {e}")

def _broadcaster_tous(titre: str, contenu: str, type_msg: str = "info"):
    try:
        res = supabase.table('profil').select('id').execute()
        users = res.data or []
        if not users: return 0
        messages = [{"receiver_id": u['id'], "expediteur": titre, "contenu": contenu, "lu": False} for u in users]
        supabase.table('messages').insert(messages).execute()
        logging.info(f"[BROADCAST] ✅ Message envoyé à {len(users)} utilisateurs")
        return len(users)
    except Exception as e:
        logging.error(f"[BROADCAST] Erreur : {e}")
        return 0

@app.route('/api/push/cle_publique')
def api_push_cle_publique():
    cle = os.getenv("VAPID_PUBLIC_KEY", "").strip()
    return jsonify({"cle_publique": cle})

@app.route('/api/push/abonner', methods=['POST'])
@login_required
def api_push_abonner():
    user_id    = session.get('user_id')
    abonnement = request.json
    if not abonnement:
        return jsonify({"error": "Abonnement vide"}), 400
    try:
        endpoint = abonnement.get('endpoint', '')
        res = supabase.table('push_abonnements').select('id').eq('user_id', user_id).eq('endpoint', endpoint).execute()
        if not res.data:
            supabase.table('push_abonnements').insert({"user_id": user_id, "abonnement": json.dumps(abonnement), "endpoint": endpoint}).execute()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/push/debug_son')
@login_required
def api_push_debug_son():
    user_id  = session.get('user_id')
    cle_pub  = os.getenv("VAPID_PUBLIC_KEY",  "").strip()
    cle_priv = os.getenv("VAPID_PRIVATE_KEY", "").strip()
    try:
        res  = supabase.table('push_abonnements').select('id, abonnement').eq('user_id', user_id).execute()
        abos = res.data or []
    except:
        abos = []
    resultats = []
    resultats.append(("pywebpush installé",   PUSH_ACTIF, "OK" if PUSH_ACTIF else "❌ pip install pywebpush"))
    resultats.append(("VAPID_PUBLIC_KEY",      bool(cle_pub),  f"{len(cle_pub)} chars" if cle_pub else "❌ ABSENT"))
    resultats.append(("VAPID_PRIVATE_KEY",     bool(cle_priv), f"{len(cle_priv)} chars" if cle_priv else "❌ ABSENT"))
    resultats.append(("Abonnements push",      len(abos) > 0,  f"{len(abos)} appareil(s)" if abos else "❌ 0"))
    sw_path = os.path.join(os.path.dirname(__file__), 'static', 'sw.js')
    sw_ok   = os.path.exists(sw_path)
    resultats.append(("static/sw.js présent",  sw_ok, f"{os.path.getsize(sw_path)} octets" if sw_ok else "❌ MANQUANT"))
    envoi_ok, envoi_msg = False, "Non testé"
    if PUSH_ACTIF and cle_pub and cle_priv and abos:
        try:
            abo = abos[0]['abonnement']
            if isinstance(abo, str): abo = json.loads(abo)
            _envoyer_push(abo, "🔊 Test Son — Aura", "Si tu entends ce son, ça fonctionne !", "/compte", "commande", 1)
            envoi_ok  = True
            envoi_msg = "✅ Notification envoyée !"
        except Exception as e:
            envoi_msg = f"❌ Erreur : {e}"
    resultats.append(("Envoi test", envoi_ok, envoi_msg))
    lignes     = "".join(f'<tr><td>{n}</td><td style="color:{"#4ade80" if ok else "#f87171"}">{"✅" if ok else "❌"}</td><td>{d}</td></tr>' for n,ok,d in resultats)
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>🔊 Debug Son — Aura</title><style>body{{font-family:monospace;background:#0f172a;color:#e2e8f0;padding:20px;margin:0;font-size:13px}}table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden;margin-bottom:16px}}th{{background:#334155;padding:10px;text-align:left}}td{{padding:10px;border-bottom:1px solid #334155}}.btn{{display:inline-block;margin:12px 4px 0;padding:12px 20px;border-radius:10px;color:white;text-decoration:none;font-weight:bold;font-size:12px}}</style></head>
<body><h1 style="color:#D4AF37">🔊 Debug Notifications — Aura</h1><table><tr><th>Test</th><th>Statut</th><th>Détail</th></tr>{lignes}</table>
<a href="/api/push/debug_son" class="btn" style="background:#2563eb">🔄 Retester</a>
<a href="/compte" class="btn" style="background:#16a34a">← Compte</a></body></html>"""

@app.route('/api/push/badge')
@login_required
def api_push_badge():
    user_id = session.get('user_id')
    nb = _compter_messages_non_lus(user_id)
    return jsonify({"count": nb})

@app.route('/api/admin/notifier_tous', methods=['GET', 'POST'])
@login_required
def api_admin_notifier_tous():
    user_id = session.get('user_id')
    try:
        res  = supabase.table('profil').select('role').eq('id', user_id).execute()
        role = (res.data or [{}])[0].get('role', '')
        if role not in ('admin', 'super_admin', 'commercant'):
            return jsonify({"error": "Accès refusé"}), 403
    except:
        pass
    if request.method == 'POST':
        data    = request.json or {}
        titre   = data.get('titre',   'Aura Markeplay')
        contenu = data.get('contenu', '')
        type_m  = data.get('type',    'info')
        if not contenu:
            return jsonify({"error": "Contenu vide"}), 400
        nb = _broadcaster_tous(titre, contenu, type_m)
        return jsonify({"status": "ok", "envoye_a": nb})
    return """<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>📢 Notifier tous</title>
<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:20px;margin:0;max-width:500px;margin:0 auto;}h1{color:#D4AF37;font-size:18px;margin-bottom:24px}label{display:block;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#94a3b8;margin-bottom:6px}input,textarea,select{width:100%;padding:12px;border-radius:10px;background:#1e293b;border:1px solid #334155;color:white;font-size:14px;margin-bottom:16px;box-sizing:border-box}textarea{height:120px;resize:vertical}.btn{width:100%;padding:14px;border-radius:12px;background:#2563eb;color:white;border:none;font-size:14px;font-weight:900;cursor:pointer}#resultat{margin-top:16px;padding:14px;border-radius:10px;background:#1e293b;display:none}.ok{color:#4ade80}.err{color:#f87171}</style></head>
<body><h1>📢 Envoyer à TOUS les utilisateurs</h1>
<label>Type</label><select id="type"><option value="info">📢 Information</option><option value="promo">🎉 Promotion</option><option value="nouveau_produit">🆕 Nouveau produit</option><option value="confirmation">✅ Confirmation</option></select>
<label>Titre</label><input id="titre" placeholder="Ex: 🔥 Soldes !" value="Aura Markeplay">
<label>Message</label><textarea id="contenu" placeholder="Votre message..."></textarea>
<button class="btn" onclick="envoyer()">📤 Envoyer à tous</button><div id="resultat"></div>
<script>async function envoyer(){const titre=document.getElementById('titre').value.trim(),contenu=document.getElementById('contenu').value.trim(),type=document.getElementById('type').value,res_el=document.getElementById('resultat');if(!contenu){alert('Écris un message !');return;}res_el.style.display='block';res_el.innerHTML='<p>⏳ Envoi...</p>';try{const res=await fetch('/api/admin/notifier_tous',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({titre,contenu,type})});const data=await res.json();res_el.innerHTML=data.status==='ok'?'<p class="ok">✅ Envoyé à '+data.envoye_a+' utilisateurs !</p>':'<p class="err">❌ '+( data.error||'?')+'</p>';}catch(e){res_el.innerHTML='<p class="err">❌ Erreur réseau</p>';}}</script></body></html>"""

if __name__ == '__main__':
    PORT = int(os.getenv("PORT", 3000))
    app.run(host='0.0.0.0', port=PORT, debug=True)
