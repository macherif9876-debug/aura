# ==============================================================================
# 📋 AUTH INSCRIPTION — LOGIQUE D'INSCRIPTION + CONNEXION GOOGLE
# Application : Aura Markeplay
# ==============================================================================

import os
import logging
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, jsonify, session
)

# --- CRÉATION DU BLUEPRINT ---
inscription_bp = Blueprint('inscription', __name__)

# --- CLIENT SUPABASE (injecté par main.py) ---
_supabase = None

def init_supabase(client):
    global _supabase
    _supabase = client
    logging.info("[INSCRIPTION] ✅ Client Supabase injecté.")


# ==============================================================================
# 🔧 VALIDATION DES DONNÉES DU FORMULAIRE
# ==============================================================================
def valider_donnees_inscription(form_data):
    nom       = form_data.get('nom', '').strip()
    prenom    = form_data.get('prenom', '').strip()
    email     = form_data.get('email', '').strip()
    password  = form_data.get('password', '')
    confirm   = form_data.get('confirm_password', '')
    indicatif = form_data.get('indicatif', '').strip()
    telephone = form_data.get('telephone', '').strip()

    if not nom:
        return False, "Le nom est obligatoire."
    if not prenom:
        return False, "Le prénom est obligatoire."
    if not email or '@' not in email:
        return False, "Adresse email invalide."
    if len(password) < 6:
        return False, "Le mot de passe doit contenir au moins 6 caractères."
    if password != confirm:
        return False, "Les mots de passe ne correspondent pas."
    if not indicatif:
        return False, "Veuillez sélectionner l'indicatif téléphonique."
    if not telephone:
        return False, "Le numéro de téléphone est obligatoire."

    return True, None


# ==============================================================================
# 📄 ROUTE INSCRIPTION : GET /signup  et  POST /signup
# ==============================================================================
@inscription_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if _supabase is None:
        logging.error("[INSCRIPTION] ERREUR CRITIQUE : Supabase non initialisé.")
        flash("Erreur serveur. Contactez l'administrateur.", "error")
        return render_template('signup.html', pays=[], form_data={})

    pays_list = []
    try:
        pays_list = (
            _supabase.table('pays')
            .select('id, nom_pays, code_pays, indicatif')
            .order('nom_pays')
            .execute()
            .data or []
        )
        logging.info(f"[INSCRIPTION] {len(pays_list)} pays chargés.")
    except Exception as e:
        logging.error(f"[INSCRIPTION] Erreur chargement pays : {e}")
        flash("Impossible de charger la liste des pays. Réessayez.", "error")

    if request.method == 'POST':
        nom       = request.form.get('nom', '').strip()
        prenom    = request.form.get('prenom', '').strip()
        email     = request.form.get('email', '').strip().lower()
        password  = request.form.get('password', '')
        indicatif = request.form.get('indicatif', '').strip()
        telephone = request.form.get('telephone', '').strip()
        pays_id   = request.form.get('id_pays', '').strip()
        region_id = request.form.get('id_region', '').strip()

        telephone_complet = f"{indicatif}{telephone}" if indicatif and telephone else None

        valide, erreur = valider_donnees_inscription(request.form)
        if not valide:
            flash(erreur, "error")
            return render_template('signup.html', pays=pays_list, form_data=request.form)

        try:
            auth_res = _supabase.auth.sign_up({"email": email, "password": password})

            if not auth_res.user:
                flash("Impossible de créer le compte. Cet email est peut-être déjà utilisé.", "error")
                return render_template('signup.html', pays=pays_list, form_data=request.form)

            user_id = auth_res.user.id

            profile_data = {
                "id":        user_id,
                "nom":       nom,
                "prenom":    prenom,
                "email":     email,
                "telephone": telephone_complet,
                "role":      "client"
            }
            if pays_id:
                profile_data["pays_id"] = pays_id
            if region_id:
                profile_data["region_id"] = region_id

            _supabase.table('profil').insert(profile_data).execute()

            session.clear()
            session['user_id'] = user_id

            logging.info(f"[INSCRIPTION] ✅ Compte créé : {email} (ID: {user_id})")
            flash(f"Bienvenue {prenom} ! Votre compte a été créé avec succès.", "success")
            return redirect(url_for('home'))

        except Exception as e:
            logging.error(f"[INSCRIPTION] Erreur création compte : {e}")
            err_str = str(e).lower()
            if "already registered" in err_str or "already exists" in err_str:
                flash("Cette adresse email est déjà utilisée.", "error")
            elif "password" in err_str:
                flash("Mot de passe trop faible. Utilisez au moins 6 caractères.", "error")
            else:
                flash(f"Erreur lors de l'inscription : {str(e)}", "error")

    return render_template('signup.html', pays=pays_list, form_data={})


# ==============================================================================
# 🔄 API JSON — Régions par pays
# ==============================================================================
@inscription_bp.route('/api/regions/<string:pays_id>')
def api_get_regions_by_pays(pays_id):
    if _supabase is None:
        return jsonify({"error": "Serveur non initialisé"}), 500
    try:
        res = (
            _supabase.table('region')
            .select('id, nom_region')
            .eq('pays_id', pays_id)
            .order('nom_region')
            .execute()
        )
        regions = res.data or []
        logging.info(f"[API REGIONS] ✅ {len(regions)} régions pour pays_id={pays_id}")
        return jsonify(regions)
    except Exception as e:
        logging.error(f"[API REGIONS] ❌ Erreur : {e}")
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# 🔵 GOOGLE OAUTH — ÉTAPE 1 : Lancer la connexion Google via Supabase
# URL : GET /auth/google
# ==============================================================================
@inscription_bp.route('/auth/google')
def auth_google():
    if _supabase is None:
        flash("Erreur serveur.", "error")
        return redirect(url_for('login_page'))

    try:
        # L'URL de callback doit correspondre exactement à ce que tu configures
        # dans Supabase → Authentication → URL Configuration → Redirect URLs
        base_url = os.getenv("APP_URL", "").rstrip("/")
        redirect_to = f"{base_url}/auth/callback" if base_url else None

        options = {"redirect_to": redirect_to} if redirect_to else {}

        res = _supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": options
        })

        if res and hasattr(res, 'url') and res.url:
            logging.info(f"[GOOGLE AUTH] Redirection vers Google OAuth...")
            return redirect(res.url)
        else:
            flash("Impossible de lancer la connexion Google.", "error")
            return redirect(url_for('login_page'))

    except Exception as e:
        logging.error(f"[GOOGLE AUTH] Erreur : {e}")
        flash(f"Erreur Google OAuth : {str(e)}", "error")
        return redirect(url_for('login_page'))


# ==============================================================================
# 🔵 GOOGLE OAUTH — ÉTAPE 2 : Page intermédiaire (template JS)
# URL : GET /auth/callback
# Cette page lit le token dans l'URL #fragment via JavaScript
# ==============================================================================
@inscription_bp.route('/auth/callback')
def auth_callback():
    return render_template('auth_callback.html')


# ==============================================================================
# 🔵 GOOGLE OAUTH — ÉTAPE 3 : Traitement du token (appelé par JS)
# URL : POST /auth/callback/process
# ==============================================================================
@inscription_bp.route('/auth/callback/process', methods=['POST'])
def auth_callback_process():
    if _supabase is None:
        return jsonify({"status": "error", "error": "Serveur non initialisé"}), 500

    try:
        data         = request.json or {}
        access_token = data.get('access_token', '')
        refresh_token = data.get('refresh_token', '')

        if not access_token:
            return jsonify({"status": "error", "error": "Token manquant"}), 400

        # Récupérer les infos de l'utilisateur via le token
        user_res = _supabase.auth.get_user(access_token)

        if not user_res or not user_res.user:
            return jsonify({"status": "error", "error": "Utilisateur non trouvé"}), 401

        user    = user_res.user
        user_id = user.id
        email   = user.email or ""

        # Vérifier si le profil existe déjà, sinon le créer
        try:
            profil_res = _supabase.table('profil').select('id').eq('id', user_id).execute()
            if not profil_res.data:
                # Nouveau profil pour utilisateur Google
                meta = user.user_metadata or {}
                nom    = meta.get('family_name') or meta.get('full_name', '').split()[-1] if meta.get('full_name') else ''
                prenom = meta.get('given_name')  or meta.get('full_name', '').split()[0]  if meta.get('full_name') else ''

                _supabase.table('profil').insert({
                    "id":       user_id,
                    "email":    email,
                    "nom":      nom,
                    "prenom":   prenom,
                    "role":     "client",
                    "photo_url": meta.get('avatar_url', '') or meta.get('picture', '')
                }).execute()
                logging.info(f"[GOOGLE AUTH] ✅ Nouveau profil créé pour {email}")
            else:
                logging.info(f"[GOOGLE AUTH] ✅ Profil existant trouvé pour {email}")
        except Exception as e_profil:
            logging.warning(f"[GOOGLE AUTH] Erreur création/vérification profil : {e_profil}")

        # Mettre en session
        session.clear()
        session['user_id'] = user_id
        session['access_token'] = access_token

        logging.info(f"[GOOGLE AUTH] ✅ Connexion Google réussie : {email}")
        return jsonify({"status": "ok"})

    except Exception as e:
        logging.error(f"[GOOGLE AUTH PROCESS] ❌ {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


# ==============================================================================
# 🔵 GOOGLE OAUTH — Route alternative : code flow (certains cas Supabase)
# URL : GET /auth/callback/code?code=xxx
# ==============================================================================
@inscription_bp.route('/auth/callback/code')
def auth_callback_code():
    if _supabase is None:
        return redirect(url_for('login_page'))
    try:
        code = request.args.get('code', '')
        if not code:
            return redirect(url_for('login_page'))

        res = _supabase.auth.exchange_code_for_session({"auth_code": code})

        if res and res.user:
            user_id = res.user.id
            email   = res.user.email or ""

            try:
                profil_res = _supabase.table('profil').select('id').eq('id', user_id).execute()
                if not profil_res.data:
                    meta = res.user.user_metadata or {}
                    _supabase.table('profil').insert({
                        "id":       user_id,
                        "email":    email,
                        "nom":      meta.get('family_name', ''),
                        "prenom":   meta.get('given_name', ''),
                        "role":     "client",
                        "photo_url": meta.get('avatar_url', '') or meta.get('picture', '')
                    }).execute()
            except Exception as ep:
                logging.warning(f"[GOOGLE CODE] Profil : {ep}")

            session.clear()
            session['user_id'] = user_id
            return redirect(url_for('home'))

        return redirect(url_for('login_page'))
    except Exception as e:
        logging.error(f"[GOOGLE CODE] ❌ {e}")
        return redirect(url_for('login_page'))
