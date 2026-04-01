# ==============================================================================
# 📋 AUTH INSCRIPTION — LOGIQUE D'INSCRIPTION UTILISATEUR
# Application : Aura Markeplay
# ==============================================================================
# Structure CONFIRMÉE Supabase :
#
#   table profil  → id, prenom, nom, telephone, email,
#                   pays_id (uuid), region_id (uuid), role, ...
#
#   table region  → id (uuid), nom_region (text), pays_id (uuid)
#   table pays    → id (uuid), nom_pays, code_pays, indicatif
# ==============================================================================

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session

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
# 📄 ROUTE PRINCIPALE : GET /signup  et  POST /signup
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

    # --- TRAITEMENT DU POST ---
    if request.method == 'POST':
        nom       = request.form.get('nom', '').strip()
        prenom    = request.form.get('prenom', '').strip()
        email     = request.form.get('email', '').strip().lower()
        password  = request.form.get('password', '')
        indicatif = request.form.get('indicatif', '').strip()
        telephone = request.form.get('telephone', '').strip()

        # ✅ On reçoit les UUID depuis le formulaire HTML
        pays_id   = request.form.get('id_pays', '').strip()    # vient du select HTML
        region_id = request.form.get('id_region', '').strip()  # vient du select HTML

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

            # ✅ COLONNES CORRECTES : pays_id et region_id (uuid, pas int)
            profile_data = {
                "id":        user_id,
                "nom":       nom,
                "prenom":    prenom,
                "email":     email,
                "telephone": telephone_complet,
                "role":      "client"
            }

            # Ajout pays_id seulement si sélectionné (UUID string)
            if pays_id:
                profile_data["pays_id"] = pays_id      # ✅ "pays_id" pas "id_pays"

            # Ajout region_id seulement si sélectionné (UUID string)
            if region_id:
                profile_data["region_id"] = region_id  # ✅ "region_id" pas "id_region"

            _supabase.table('profil').insert(profile_data).execute()

            # ✅ CONNEXION AUTOMATIQUE après inscription
            # On met l'user_id en session → l'utilisateur est directement connecté
            session.clear()
            session['user_id'] = user_id

            logging.info(f"[INSCRIPTION] ✅ Compte créé et connecté : {email} (ID: {user_id})")
            flash(f"Bienvenue {prenom} ! Votre compte a été créé avec succès.", "success")

            # ✅ Redirection directe vers la page d'accueil (pas le login)
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
# URL : GET /api/regions/<pays_id>
# ✅ Table 'region', colonne liaison = 'pays_id' (uuid)
# ==============================================================================
@inscription_bp.route('/api/regions/<string:pays_id>')
def api_get_regions_by_pays(pays_id):
    if _supabase is None:
        return jsonify({"error": "Serveur non initialisé"}), 500

    try:
        logging.info(f"[API REGIONS] Recherche pour pays_id={pays_id}")

        res = (
            _supabase.table('region')
            .select('id, nom_region')
            .eq('pays_id', pays_id)     # ✅ colonne confirmée
            .order('nom_region')
            .execute()
        )

        regions = res.data or []
        logging.info(f"[API REGIONS] ✅ {len(regions)} régions pour pays_id={pays_id}")
        return jsonify(regions)

    except Exception as e:
        logging.error(f"[API REGIONS] ❌ Erreur : {e}")
        return jsonify({"error": str(e)}), 500
