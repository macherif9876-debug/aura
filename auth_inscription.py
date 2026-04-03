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

inscription_bp = Blueprint('inscription', __name__)
_supabase = None

def init_supabase(client):
    global _supabase
    _supabase = client
    logging.info("[INSCRIPTION] ✅ Client Supabase injecté.")

def valider_donnees_inscription(form_data):
    nom       = form_data.get('nom', '').strip()
    prenom    = form_data.get('prenom', '').strip()
    email     = form_data.get('email', '').strip()
    password  = form_data.get('password', '')
    confirm   = form_data.get('confirm_password', '')
    indicatif = form_data.get('indicatif', '').strip()
    telephone = form_data.get('telephone', '').strip()
    if not nom:        return False, "Le nom est obligatoire."
    if not prenom:     return False, "Le prénom est obligatoire."
    if not email or '@' not in email: return False, "Adresse email invalide."
    if len(password) < 6: return False, "Le mot de passe doit contenir au moins 6 caractères."
    if password != confirm: return False, "Les mots de passe ne correspondent pas."
    if not indicatif:  return False, "Veuillez sélectionner l'indicatif."
    if not telephone:  return False, "Le numéro de téléphone est obligatoire."
    return True, None

@inscription_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if _supabase is None:
        flash("Erreur serveur.", "error")
        return render_template('signup.html', pays=[], form_data={})
    pays_list = []
    try:
        pays_list = _supabase.table('pays').select('id, nom_pays, code_pays, indicatif').order('nom_pays').execute().data or []
    except Exception as e:
        logging.error(f"[INSCRIPTION] Erreur pays : {e}")
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
                flash("Impossible de créer le compte. Email déjà utilisé ?", "error")
                return render_template('signup.html', pays=pays_list, form_data=request.form)
            user_id = auth_res.user.id
            profile_data = {"id": user_id, "nom": nom, "prenom": prenom, "email": email, "telephone": telephone_complet, "role": "client"}
            if pays_id:   profile_data["pays_id"]   = pays_id
            if region_id: profile_data["region_id"] = region_id
            _supabase.table('profil').insert(profile_data).execute()
            session.clear()
            session['user_id'] = user_id
            session.modified = True
            flash(f"Bienvenue {prenom} !", "success")
            return redirect(url_for('home'))
        except Exception as e:
            logging.error(f"[INSCRIPTION] Erreur : {e}")
            err_str = str(e).lower()
            if "already registered" in err_str or "already exists" in err_str:
                flash("Cette adresse email est déjà utilisée.", "error")
            else:
                flash(f"Erreur : {str(e)}", "error")
    return render_template('signup.html', pays=pays_list, form_data={})

@inscription_bp.route('/api/regions/<string:pays_id>')
def api_get_regions_by_pays(pays_id):
    if _supabase is None:
        return jsonify({"error": "Serveur non initialisé"}), 500
    try:
        res = _supabase.table('region').select('id, nom_region').eq('pays_id', pays_id).order('nom_region').execute()
        return jsonify(res.data or [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@inscription_bp.route('/auth/google')
def auth_google():
    if _supabase is None:
        flash("Erreur serveur.", "error")
        return redirect(url_for('login_page'))
    try:
        base_url = os.getenv("APP_URL", "").rstrip("/")
        redirect_to = f"{base_url}/auth/callback/code" if base_url else None
        options = {"redirect_to": redirect_to} if redirect_to else {}
        res = _supabase.auth.sign_in_with_oauth({"provider": "google", "options": options})
        if res and hasattr(res, 'url') and res.url:
            return redirect(res.url)
        flash("Impossible de lancer la connexion Google.", "error")
        return redirect(url_for('login_page'))
    except Exception as e:
        logging.error(f"[GOOGLE AUTH] Erreur : {e}")
        flash(f"Erreur Google : {str(e)}", "error")
        return redirect(url_for('login_page'))

@inscription_bp.route('/auth/callback/code')
def auth_callback_code():
    if _supabase is None:
        flash("Erreur serveur.", "error")
        return redirect(url_for('login_page'))
    try:
        code = request.args.get('code', '').strip()
        if not code:
            logging.error("[GOOGLE CODE] Aucun code reçu.")
            flash("Connexion Google échouée : aucun code reçu.", "error")
            return redirect(url_for('login_page'))
        logging.info("[GOOGLE CODE] Code reçu, échange en cours...")
        res = _supabase.auth.exchange_code_for_session({"auth_code": code})
        if not res or not res.user:
            logging.error("[GOOGLE CODE] Pas d'utilisateur retourné.")
            flash("Connexion Google échouée. Réessayez.", "error")
            return redirect(url_for('login_page'))
        user    = res.user
        user_id = user.id
        email   = user.email or ""
        meta    = user.user_metadata or {}
        logging.info(f"[GOOGLE CODE] ✅ Utilisateur : {email}")
        try:
            profil_res = _supabase.table('profil').select('id').eq('id', user_id).execute()
            if not profil_res.data:
                full_name = meta.get('full_name', '') or meta.get('name', '')
                parts  = full_name.split() if full_name else []
                prenom = parts[0]  if parts           else meta.get('given_name', '')
                nom    = parts[-1] if len(parts) > 1  else meta.get('family_name', '')
                photo  = meta.get('avatar_url', '') or meta.get('picture', '')
                _supabase.table('profil').insert({"id": user_id, "email": email, "nom": nom, "prenom": prenom, "role": "client", "photo_url": photo}).execute()
                logging.info(f"[GOOGLE CODE] ✅ Nouveau profil créé pour {email}")
        except Exception as ep:
            logging.warning(f"[GOOGLE CODE] Profil (non bloquant) : {ep}")
        session.clear()
        session['user_id'] = user_id
        session.modified = True
        logging.info(f"[GOOGLE CODE] ✅ Session créée → redirection home")
        return redirect(url_for('home'))
    except Exception as e:
        logging.error(f"[GOOGLE CODE] ❌ Erreur : {e}")
        flash("Erreur lors de la connexion Google. Réessayez.", "error")
        return redirect(url_for('login_page'))

@inscription_bp.route('/auth/callback')
def auth_callback():
    code = request.args.get('code', '')
    if code:
        return redirect(url_for('inscription.auth_callback_code', code=code))
    return render_template('auth_callback.html')

@inscription_bp.route('/auth/callback/process', methods=['POST'])
def auth_callback_process():
    if _supabase is None:
        return jsonify({"status": "error", "error": "Serveur non initialisé"}), 500
    try:
        data          = request.json or {}
        access_token  = data.get('access_token', '')
        refresh_token = data.get('refresh_token', '')
        if not access_token:
            return jsonify({"status": "error", "error": "Token manquant"}), 400
        res = _supabase.auth.set_session(access_token, refresh_token)
        if not res or not res.user:
            return jsonify({"status": "error", "error": "Session invalide"}), 401
        user    = res.user
        user_id = user.id
        email   = user.email or ""
        meta    = user.user_metadata or {}
        try:
            profil_res = _supabase.table('profil').select('id').eq('id', user_id).execute()
            if not profil_res.data:
                full_name = meta.get('full_name', '') or meta.get('name', '')
                parts  = full_name.split() if full_name else []
                prenom = parts[0]  if parts           else meta.get('given_name', '')
                nom    = parts[-1] if len(parts) > 1  else meta.get('family_name', '')
                _supabase.table('profil').insert({"id": user_id, "email": email, "nom": nom, "prenom": prenom, "role": "client", "photo_url": meta.get('avatar_url', '') or meta.get('picture', '')}).execute()
        except Exception as ep:
            logging.warning(f"[GOOGLE PROCESS] Profil : {ep}")
        session.clear()
        session['user_id'] = user_id
        session.modified = True
        logging.info(f"[GOOGLE PROCESS] ✅ Session créée pour {email}")
        return jsonify({"status": "ok"})
    except Exception as e:
        logging.error(f"[GOOGLE PROCESS] ❌ {e}")
        return jsonify({"status": "error", "error": str(e)}), 500
