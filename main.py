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

# Vision par ordinateur : Hugging Face principal, Cloudinary en secours
MODE_IA_ACTIF = True

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
    """
    Moteur de recherche par image.
    Priorité 1 : Hugging Face API (Modèle ViT)
    Priorité 2 (Secours) : Cloudinary Auto-Tagging
    """

    # Correspondance couleurs HEX → noms français
    COULEURS = {
        'rouge':  ['#ff0000','#cc0000','#dc143c','#b22222','#8b0000','#ff4444'],
        'rose':   ['#ffc0cb','#ff69b4','#ff1493','#db7093','#ffb6c1'],
        'orange': ['#ffa500','#ff8c00','#ff4500','#ff6347'],
        'jaune':  ['#ffff00','#ffd700','#f0e68c','#ffffe0','#fffacd'],
        'vert':   ['#008000','#00ff00','#228b22','#006400','#32cd32','#90ee90'],
        'bleu':   ['#0000ff','#000080','#00008b','#4169e1','#1e90ff','#87ceeb'],
        'violet': ['#800080','#9400d3','#4b0082','#8a2be2','#ee82ee'],
        'marron': ['#a52a2a','#8b4513','#d2691e','#cd853f','#c4a35a'],
        'noir':   ['#000000','#1a1a1a','#2d2d2d','#333333'],
        'blanc':  ['#ffffff','#f5f5f5','#fffafa','#f8f8f8'],
        'gris':   ['#808080','#a9a9a9','#d3d3d3','#c0c0c0','#696969'],
        'beige':  ['#f5f5dc','#ffe4c4','#ffdead','#f5deb3'],
        'or':     ['#ffd700','#cfb53b','#b8860b'],
        'argent': ['#c0c0c0','#a8a9ad','#b0b0b0'],
    }

    def __init__(self):
        self.hf_token = os.getenv("HUGGINGFACE_API_KEY")
        self.hf_api_url = "https://api-inference.huggingface.co/models/google/vit-base-patch16-224"

    def indexer_tout_le_catalogue(self):
        hf_ok = "✅" if self.hf_token else "❌ manquant"
        print(f"🔍 [IA VISION] Clé Hugging Face : {hf_ok}")

    def recherche_intelligente(self, query_text=None, query_image_file=None, top_k=20):
        if query_image_file:
            return self._recherche_par_image(query_image_file, top_k)
        elif query_text:
            return self._recherche_par_texte(query_text, top_k)
        return []

    def _recherche_par_image(self, image_file, top_k=20):
        tous_mots = []
        image_file.seek(0)
        image_data = image_file.read()

        # --- OPTION 1 : Hugging Face ---
        if self.hf_token:
            try:
                logging.info("[HUGGING FACE] 🧠 Envoi de l'image...")
                headers = {"Authorization": f"Bearer {self.hf_token}"}
                response = requests.post(self.hf_api_url, headers=headers, data=image_data, timeout=15)
                
                if response.status_code == 200:
                    results = response.json()
                    # Correction : On s'assure d'extraire les labels proprement
                    if isinstance(results, list):
                        tous_mots = [res['label'].lower() for res in results if res.get('score', 0) >= 0.15]
                    logging.info(f"[HUGGING FACE] ✅ Mots détectés : {tous_mots}")
            except Exception as e:
                logging.error(f"[HUGGING FACE] ❌ Échec : {e}")

        # --- OPTION 2 : Cloudinary (Secours) ---
        if not tous_mots:
            try:
                logging.info("[CLOUDINARY SECOURS] 📤 Upload pour analyse...")
                image_file.seek(0)
                result = cloudinary.uploader.upload(
                    image_file,
                    categorization  = "google_tagging",
                    auto_tagging    = 0.5,
                    colors          = True,
                    resource_type   = "image"
                )

                tags_ia = result.get('tags', [])
                info = result.get('info', {})
                # Correction accès structure Cloudinary Google Tagging
                cat_data = info.get('categorization', {}).get('google_tagging', {}).get('data', [])
                tags_google = [c.get('tag', '') for c in cat_data if c.get('confidence', 0) >= 0.5]
                
                colors_raw = result.get('colors', [])
                noms_couleurs = self._hex_vers_noms(colors_raw)

                tous_mots = list(dict.fromkeys([t.lower() for t in tags_ia + tags_google] + noms_couleurs))
                logging.info(f"[CLOUDINARY SECOURS] ✅ Mots détectés : {tous_mots}")
            except Exception as e:
                logging.error(f"[CLOUDINARY SECOURS] ❌ Erreur : {e}")

        if tous_mots:
            ids = self._chercher_par_mots_cles(tous_mots, top_k)
            if ids: return ids

        # Fallback
        try:
            res = supabase.table('produits').select('id').order('created_at', desc=True).limit(top_k).execute()
            return [p['id'] for p in (res.data or [])]
        except:
            return []

    def _hex_vers_noms(self, colors_raw):
        noms = []
        for item in colors_raw[:4]:
            hex_color = (item[0] if isinstance(item, list) else str(item)).lower().strip()
            for nom, hexlist in self.COULEURS.items():
                if hex_color in hexlist:
                    noms.append(nom)
                    break
        return noms

    def _chercher_par_mots_cles(self, keywords, top_k=20):
        ids = set()
        for mot in keywords[:10]:
            if not mot or len(mot) < 2: continue
            try:
                res = supabase.table('produits').select('id').or_(
                    f"nom.ilike.%{mot}%,"
                    f"description.ilike.%{mot}%,"
                    f"categorie.ilike.%{mot}%"
                ).execute()
                for p in (res.data or []): ids.add(p['id'])
            except: continue
        return list(ids)[:top_k]

    def _recherche_par_texte(self, query_text, top_k=20):
        try:
            res = supabase.table('produits').select('id').or_(
                f"nom.ilike.%{query_text}%,"
                f"description.ilike.%{query_text}%,"
                f"categorie.ilike.%{query_text}%"
            ).execute()
            return [p['id'] for p in (res.data or [])][:top_k]
        except: return []

moteur_ia = MoteurRechercheAura()

def trouver_nimporte_quel_depot(user, token):
    try:
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        res = requests.get(f"https://api.github.com/users/{user}/repos?per_page=100", headers=headers, timeout=10)
        if res.status_code == 200:
            repos = res.json()
            if not repos: return None
            for r in repos:
                nom = r['name'].lower()
                if any(mot in nom for mot in ['aura', 'storage', 'vids', 'video']): return r['name']
            return repos[0]['name']
    except: return None

def rendre_depot_public(user, token, repo_nom):
    try:
        url = f"https://api.github.com/repos/{user}/{repo_nom}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        requests.patch(url, json={"private": False}, headers=headers, timeout=10)
    except: pass

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
    except: return None

def designer_automatique_ia(file_storage):
    try:
        file_storage.seek(0)
        result = cloudinary.uploader.upload(file_storage, background_removal="cloudinary_ai", resource_type="image")
        url = result.get('secure_url', '')
        if url: return url
    except:
        try:
            file_storage.seek(0)
            result = cloudinary.uploader.upload(file_storage, resource_type="image")
            return result.get('secure_url', '')
        except: return ""
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
        except: return "Erreur de vérification des droits.", 403
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
    if 'user_id' not in session: return redirect(url_for('login_page'))
    try:
        banners  = supabase.table('banners').select('*').order('position').execute().data or []
        produits = supabase.table('produits').select('*, profil!id_commercant(nom_boutique, photo_url)').order('created_at', desc=True).execute().data or []
        return render_template('home.html', banners=banners, produits=produits, categories=CATEGORIES_LIST, db_connected=DB_CONNECTED, db_error=DB_ERROR_MSG)
    except Exception as e:
        return render_template('home.html', banners=[], produits=[], categories=CATEGORIES_LIST, db_connected=DB_CONNECTED, db_error=str(e))

@app.route('/recherche', methods=['GET', 'POST'])
def recherche_page():
    query = request.args.get('q', '')
    produits_trouves = []
    erreur_image = None
    if request.method == 'POST':
        file = request.files.get('image_search')
        if file and file.filename != '':
            try:
                ids_trouves = moteur_ia.recherche_intelligente(query_image_file=file)
                if ids_trouves:
                    res = supabase.table('produits').select('*').in_('id', ids_trouves).execute()
                    produits_trouves = res.data or []
            except Exception as e:
                erreur_image = "Analyse impossible."
    elif query:
        ids_trouves = moteur_ia.recherche_intelligente(query_text=query)
        if ids_trouves:
            res = supabase.table('produits').select('*').in_('id', ids_trouves).execute()
            produits_trouves = res.data or []
    return render_template('recherche.html', produits=produits_trouves, query=query, categories=CATEGORIES_LIST, erreur_image=erreur_image)

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
        res_client = supabase.table('profil').select('nom, prenom, telephone, email').eq('id', user_id).single().execute()
        client_profil = res_client.data or {}
        res_panier = supabase.table('panier').select('id_panier').eq('id_user', user_id).eq('statut', 'actif').execute()
        if not res_panier.data: return render_template('panier.html', items=[], total_panier=0, client=client_profil)
        id_panier = res_panier.data[0]['id_panier']
        res_items = supabase.table('panier_items').select('*').eq('id_panier', id_panier).execute()
        items_bruts = res_items.data or []
        ids_produits = [item['id_produit'] for item in items_bruts if item.get('id_produit')]
        produits_map, marchands_map = {}, {}
        if ids_produits:
            res_prods = supabase.table('produits').select('*').in_('id', ids_produits).execute()
            for p in (res_prods.data or []): produits_map[p['id']] = p
            ids_marchands = list(set(p['id_commercant'] for p in produits_map.values() if p.get('id_commercant')))
            if ids_marchands:
                res_march = supabase.table('profil').select('id, nom_boutique, telephone, email, callmebot_key, photo_url').in_('id', ids_marchands).execute()
                for m in (res_march.data or []): marchands_map[m['id']] = m
        items = []
        for item in items_bruts:
            prod = produits_map.get(item.get('id_produit'), {})
            marchand_id = prod.get('id_commercant')
            prod['profil'] = marchands_map.get(marchand_id, {}) if marchand_id else {}
            item['produits'] = prod
            items.append(item)
        total_panier = sum(float(item.get('prix_unitaire_ajoute') or 0) * int(item.get('quantite') or 1) for item in items)
        return render_template('panier.html', items=items, total_panier=total_panier, client=client_profil)
    except: return render_template('panier.html', items=[], total_panier=0, client={})

@app.route('/api/ajouter_au_panier', methods=['POST'])
def api_ajouter_au_panier():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"error": "Non connecté"}), 401
    data = request.json
    try:
        res_panier = supabase.table('panier').select('id_panier').eq('id_user', user_id).eq('statut', 'actif').execute()
        if not res_panier.data:
            res_nouveau = supabase.table('panier').insert({"id_user": user_id}).execute()
            id_panier = res_nouveau.data[0]['id_panier']
        else: id_panier = res_panier.data[0]['id_panier']
        query = supabase.table('panier_items').select('*').eq('id_panier', id_panier).eq('id_produit', data.get('product_id'))
        if data.get('taille'): query = query.eq('taille', data.get('taille'))
        if data.get('couleur'): query = query.eq('couleur', data.get('couleur'))
        check_item = query.execute()
        if check_item.data:
            supabase.table('panier_items').update({"quantite": check_item.data[0]['quantite'] + 1}).eq('id_item', check_item.data[0]['id_item']).execute()
        else:
            supabase.table('panier_items').insert({"id_panier": id_panier, "id_produit": data.get('product_id'), "quantite": 1, "prix_unitaire_ajoute": data.get('prix'), "taille": data.get('taille'), "couleur": data.get('couleur')}).execute()
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/modifier_quantite', methods=['POST'])
def api_modifier_quantite():
    data = request.json
    try:
        res = supabase.table('panier_items').select('quantite').eq('id_item', data.get('id_item')).single().execute()
        new_qty = res.data['quantite'] + 1 if data.get('action') == 'plus' else res.data['quantite'] - 1
        if new_qty <= 0:
            supabase.table('panier_items').delete().eq('id_item', data.get('id_item')).execute()
            return jsonify({"status": "deleted"})
        supabase.table('panier_items').update({"quantite": new_qty}).eq('id_item', data.get('id_item')).execute()
        return jsonify({"status": "updated", "new_qty": new_qty})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/supprimer_item', methods=['POST'])
def api_supprimer_item():
    data = request.json
    try:
        supabase.table('panier_items').delete().eq('id_item', data.get('id_item')).execute()
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/panier_count')
def api_panier_count():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"count": 0})
    try:
        res_panier = supabase.table('panier').select('id_panier').eq('id_user', user_id).eq('statut', 'actif').execute()
        if not res_panier.data: return jsonify({"count": 0})
        res_items = supabase.table('panier_items').select('quantite').eq('id_panier', res_panier.data[0]['id_panier']).execute()
        total = sum(item['quantite'] for item in res_items.data) if res_items.data else 0
        return jsonify({"count": total})
    except: return jsonify({"count": 0})

@app.route('/compte')
@login_required
def compte():
    user_id = session.get('user_id')
    try:
        res = supabase.table('profil').select('*').eq('id', user_id).execute()
        if res.data:
            user = res.data[0]
            user['nom_region'] = 'Zone Aura'
            return render_template('compte.html', user=user)
        return render_template('compte.html', user={"id": user_id, "role": "client"})
    except: return render_template('compte.html', user={})

@app.route('/api/upload_photo_profil', methods=['POST'])
@login_required
def upload_photo_profil():
    user_id, file = session.get('user_id'), request.files.get('photo')
    if not file: return jsonify({"error": "Aucun fichier"}), 400
    try:
        file.seek(0)
        filename = f"avatar_{user_id}.jpg"
        upload_response = requests.post("https://upload.imagekit.io/api/v1/files/upload", auth=(os.getenv("IMAGEKIT_PRIVATE_KEY", ""), ""), files={"file": (filename, file.read(), file.content_type)}, data={"fileName": filename, "folder": "/avatars/"}, timeout=30)
        photo_url = upload_response.json().get("url")
        supabase.table('profil').update({"photo_url": photo_url}).eq('id', user_id).execute()
        return jsonify({"status": "success", "photo_url": photo_url})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/mes_commandes')
@login_required
def api_mes_commandes():
    try:
        res = supabase.table('commandes').select('*').eq('id_user', session.get('user_id')).order('created_at', desc=True).execute()
        return jsonify(res.data or [])
    except: return jsonify([])

@app.route('/api/mes_messages')
@login_required
def api_mes_messages():
    try:
        res = supabase.table('messages').select('*').eq('receiver_id', session.get('user_id')).order('created_at', desc=True).execute()
        return jsonify(res.data or [])
    except: return jsonify([])

@app.route('/api/messages/marquer_lu', methods=['POST'])
@login_required
def api_marquer_lu():
    msg_id = (request.json or {}).get('id')
    try:
        supabase.table('messages').update({"lu": True}).eq('id', msg_id).eq('receiver_id', session.get('user_id')).execute()
        return jsonify({"status": "ok"})
    except: return jsonify({"error": "err"}), 500

@app.route('/api/mes_favoris')
@login_required
def api_mes_favoris():
    try:
        res = supabase.table('favoris').select('produit_id, produits(id, nom, prix, image_url)').eq('user_id', session.get('user_id')).execute()
        return jsonify([r['produits'] for r in (res.data or []) if r.get('produits')])
    except: return jsonify([])

@app.route('/api/mon_parrainage')
@login_required
def api_mon_parrainage():
    user_id = session.get('user_id')
    try:
        res = supabase.table('parrainage').select('*').eq('user_id', user_id).execute()
        if res.data: return jsonify(res.data[0])
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        nouveau = {"user_id": user_id, "code": code, "nb_filleuls": 0, "gains": 0}
        supabase.table('parrainage').insert(nouveau).execute()
        return jsonify(nouveau)
    except: return jsonify({"code": "------"})

@app.route('/api/mes_bons')
@login_required
def api_mes_bons():
    try:
        res = supabase.table('bons').select('*').eq('user_id', session.get('user_id')).order('created_at', desc=True).execute()
        return jsonify(res.data or [])
    except: return jsonify([])

@app.route('/api/modifier_profil', methods=['POST'])
@login_required
def api_modifier_profil():
    data = request.json or {}
    try:
        supabase.table('profil').update({k: v for k, v in data.items() if k in ['nom', 'prenom', 'telephone']}).eq('id', session.get('user_id')).execute()
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/product/<prod_id>')
@login_required
def get_product_details(prod_id):
    try:
        res = supabase.table('produits').select('*, profil!id_commercant(nom_boutique, photo_url), images_details(*), variantes(*)').eq('id', prod_id).single().execute()
        return jsonify(res.data)
    except: return jsonify({"error": "non trouvé"}), 404

@app.route('/share/product/<prod_id>')
def share_product_page(prod_id):
    try:
        res = supabase.table('produits').select('*, profil(nom_boutique)').eq('id', prod_id).single().execute()
        return render_template('share_view.html', p=res.data)
    except: return "Erreur", 404

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if 'user_id' in session: return redirect(url_for('home'))
    if request.method == 'POST':
        try:
            auth_res = supabase.auth.sign_in_with_password({"email": request.form.get('email'), "password": request.form.get('password')})
            if auth_res.user:
                session['user_id'] = auth_res.user.id
                return redirect(url_for('home'))
        except: return render_template('login.html', error="Identifiants incorrects")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/admin/dashboard')
@admin_access_required
def admin_dashboard():
    try:
        users = supabase.table('profil').select('*').execute().data or []
        banners = supabase.table('banners').select('*').order('position').execute().data or []
        orders = supabase.table('commandes').select('*').order('created_at', desc=True).execute().data or []
        return render_template('admin_super.html', users=users, banners=banners, orders=orders)
    except: return "Erreur"

@app.route('/admin/promote_merchant/<user_id>')
@admin_access_required
def promote_merchant(user_id):
    supabase.table('profil').update({"role": "autorise_commercant"}).eq('id', user_id).execute()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/final_validate/<user_id>')
@admin_access_required
def final_validate(user_id):
    supabase.table('profil').update({"role": "commercant"}).eq('id', user_id).execute()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<user_id>')
@admin_access_required
def delete_user(user_id):
    supabase.table('profil').delete().eq('id', user_id).execute()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload_banners', methods=['POST'])
@admin_access_required
def upload_banners():
    for index, file in enumerate(request.files.getlist('files')):
        try:
            res = cloudinary.uploader.upload(file, folder="aura_banners", public_id=f"banner_{index+1}", overwrite=True)
            supabase.table('banners').upsert({"position": index+1, "image_url": res.get('secure_url')}, on_conflict="position").execute()
        except: continue
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_banner/<int:pos>')
@admin_access_required
def delete_banner(pos):
    supabase.table('banners').delete().eq('position', pos).execute()
    return redirect(url_for('admin_dashboard'))

@app.route('/devenir-commercant', methods=['GET', 'POST'])
@login_required
def inscription_commercant():
    user_id = session.get('user_id')
    if request.method == 'POST':
        def up(f): return cloudinary.uploader.upload(f, folder="aura_verifications").get('secure_url') if f else None
        supabase.table('profil').update({
            "role": "en_attente_validation", "nom_boutique": request.form.get('nom_boutique'),
            "telephone": request.form.get('telephone'), "url_cni_recto": up(request.files.get('cni_recto'))
        }).eq('id', user_id).execute()
        return redirect(url_for('compte'))
    return render_template('inscription_commercant.html')

@app.route('/merchant/dashboard')
@merchant_required
def merchant_dashboard():
    user_id = session.get('user_id')
    try:
        produits = supabase.table('produits').select('*').eq('id_commercant', user_id).order('created_at', desc=True).execute().data or []
        orders = supabase.table('commandes').select('*').eq('id_commercant', user_id).order('created_at', desc=True).execute().data or []
        return render_template('admin_commercant.html', produits=produits, orders=orders, categories=CATEGORIES_LIST)
    except: return "Erreur"

@app.route('/merchant/add_product', methods=['POST'])
@merchant_required
def add_product():
    try:
        img = designer_automatique_ia(request.files.get('image_produit'))
        vid = upload_to_github(request.files.get('video_produit'))
        data = {
            "id_commercant": session.get('user_id'), "nom": request.form.get('nom'),
            "prix": int(float(request.form.get('prix', 0))), "stock": int(request.form.get('stock', 0)),
            "categorie": request.form.get('categorie'), "image_url": img, "video_url": vid
        }
        res = supabase.table('produits').insert(data).execute()
        if res.data: moteur_ia.indexer_tout_le_catalogue()
        flash("Produit ajouté !")
    except Exception as e: flash(f"Erreur : {e}")
    return redirect(url_for('merchant_dashboard'))

@app.route('/merchant/edit_product/<prod_id>', methods=['GET', 'POST'])
@merchant_required
def edit_product(prod_id):
    if request.method == 'POST':
        supabase.table('produits').update({"nom": request.form.get('nom'), "prix": int(float(request.form.get('prix', 0)))}).eq('id', prod_id).execute()
        moteur_ia.indexer_tout_le_catalogue()
        return redirect(url_for('merchant_dashboard'))
    p = supabase.table('produits').select('*').eq('id', prod_id).single().execute().data
    return render_template('edit_product.html', produit=p, categories=CATEGORIES_LIST)

@app.route('/merchant/delete_product/<prod_id>')
@merchant_required
def delete_product(prod_id):
    supabase.table('produits').delete().eq('id', prod_id).execute()
    moteur_ia.indexer_tout_le_catalogue()
    return redirect(url_for('merchant_dashboard'))

@app.route('/videos')
def galerie_videos():
    res = supabase.table('produits').select('*, profil!id_commercant(nom_boutique)').not_.is_('video_url', 'null').execute()
    return render_template('videos.html', produits=res.data or [])

@app.route('/api/videos/recherche')
def api_videos_recherche():
    ids = moteur_ia.recherche_intelligente(query_text=request.args.get('q', ''))
    res = supabase.table('produits').select('id, nom, prix, video_url').in_('id', ids).not_.is_('video_url', 'null').execute()
    return jsonify(res.data or [])

@app.route('/api/like/<prod_id>', methods=['POST'])
@login_required
def api_like_product(prod_id):
    uid = session.get('user_id')
    supabase.table('produits_likes').upsert({"user_id": uid, "produit_id": prod_id}).execute()
    return jsonify({"status": "liked"})

@app.route('/api/share/<prod_id>', methods=['POST'])
def api_share_product(prod_id):
    return jsonify({"status": "shared"})

@app.route('/api/boost/<prod_id>', methods=['POST'])
@login_required
def api_boost_product(prod_id):
    return jsonify({"status": "success"})

@app.route('/api/comments/<prod_id>', methods=['GET', 'POST'])
def handle_comments(prod_id):
    if request.method == 'POST':
        supabase.table('commentaire_produit').insert({"produit_id": prod_id, "user_id": session.get('user_id'), "commentaire_texte": request.json.get('content')}).execute()
        return jsonify({"status": "added"})
    res = supabase.table('commentaire_produit').select('*, profil(nom, prenom)').eq('produit_id', prod_id).execute()
    return jsonify(res.data or [])

@app.route('/api/commander_panier', methods=['POST'])
@login_required
def api_commander_panier():
    return jsonify({"status": "success"})

def _envoyer_email_bg(dest, sujet, html):
    pass

def _whatsapp_callmebot(tel, key, msg):
    pass

def _notifier_en_arriere_plan(cmd, march, client):
    pass

@app.route('/api/commander', methods=['POST'])
@login_required
def api_commander():
    return jsonify({"status": "success"})

def _preparer_cle_vapid_privee(raw):
    return raw.strip()

def _compter_messages_non_lus(uid):
    return 0

def _envoyer_push(abo, tit, cor, url='/', typ='def', b=0):
    pass

def _notifier_push_utilisateur(uid, tit, cor, url='/', typ='def'):
    pass

def _push_broadcast_tous(tit, cor, url='/', typ='nouveau'):
    pass

def _broadcaster_tous(tit, con, typ="info"):
    return 0

@app.route('/api/push/cle_publique')
def api_push_cle_publique():
    return jsonify({"cle_publique": os.getenv("VAPID_PUBLIC_KEY", "")})

@app.route('/api/push/abonner', methods=['POST'])
@login_required
def api_push_abonner():
    return jsonify({"status": "ok"})

@app.route('/api/push/debug_son')
@login_required
def api_push_debug_son():
    return "Debug"

@app.route('/api/push/badge')
@login_required
def api_push_badge():
    return jsonify({"count": 0})

@app.route('/api/admin/notifier_tous', methods=['GET', 'POST'])
@login_required
def api_admin_notifier_tous():
    return "Notifier"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 3000)), debug=True)
