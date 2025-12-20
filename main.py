from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
import os
import threading
from mcp.server.fastmcp import FastMCP

# --- CONFIGURATION INITIALE ---
app = Flask(__name__)

# Charge les clés Supabase depuis les secrets Replit
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Les variables SUPABASE_URL et SUPABASE_KEY ne sont pas configurées !")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURATION DU SERVEUR MCP (Mon accès) ---
mcp = FastMCP("Aura_Engine")

@mcp.tool()
def create_app_template(filename: str, html_content: str):
    """Crée un fichier HTML dans le dossier templates pour Aura"""
    try:
        path = os.path.join("templates", filename)
        os.makedirs("templates", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return f"✅ Template {filename} créé avec succès."
    except Exception as e:
        return f"❌ Erreur : {str(e)}"

@mcp.tool()
def edit_flask_routes(new_code: str):
    """Permet de modifier dynamiquement ce fichier main.py pour ajouter des routes"""
    with open(__file__, "w", encoding="utf-8") as f:
        f.write(new_code)
    return "✅ Routes mises à jour. Redémarrez le serveur."

# --- ROUTES FLASK EXISTANTES ---

@app.route('/api/tables')
def list_tables():
    """Liste toutes les tables Supabase"""
    try:
        # Requête SQL pour récupérer les tables du schéma public
        response = supabase.rpc('get_tables', {}).execute()
        if response.data:
            tables = response.data if isinstance(response.data, list) else [response.data]
            return jsonify({"tables": tables, "count": len(tables), "status": "success"})
        return jsonify({"tables": [], "count": 0, "status": "no_tables"})
    except Exception as e:
        # Essayer une approche alternative: énumérer les tables en les essayant
        tables_found = []
        common_tables = ['users', 'profiles', 'posts', 'comments', 'products', 'orders', 'categories', 'tags']
        
        for table_name in common_tables:
            try:
                response = supabase.table(table_name).select('*', count='exact').limit(0).execute()
                if response:
                    tables_found.append(table_name)
            except:
                pass
        
        if tables_found:
            return jsonify({"tables": tables_found, "count": len(tables_found), "status": "success", "note": "Tables détectées"})
        return jsonify({"error": str(e), "tables": [], "count": 0, "status": "failed"}), 400

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/register-pro')
def register_pro_page():
    return render_template('register-pro.html')

@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')

@app.route('/admin/generate-invite', methods=['POST'])
def generate_invite():
    data = request.json
    email = data.get('email')
    role = data.get('role')
    try:
        supabase.auth.admin.invite_user_by_email(email)
        invite_link = f"http://localhost:3000/register-pro?email={email}&role={role}"
        return jsonify({"link": invite_link, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "failed"}), 400

# --- LANCEMENT SIMULTANÉ ---

def run_mcp():
    # Lance le serveur MCP sur un port différent ou via stdio
    mcp.run()

if __name__ == '__main__':
    # On lance MCP dans un fil séparé pour ne pas bloquer Flask
    # Note : Sur Replit, on utilise souvent le mode stdio pour MCP
    print("🚀 Serveur Aura & Agent MCP en cours de démarrage...")
    app.run(host='0.0.0.0', port=3000)
