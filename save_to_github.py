import os
import subprocess
import requests

# 1. PARAMÈTRES
# Récupération automatique de ton token avec le bon nom de secret
token = os.environ.get('GH_TOKEN_1')

username = "macherif9876-debug"  # Ton pseudo GitHub
repo_name = "BCBPG_PROJET"        # Le nom du dépôt qui va être créé
email = "ton.email@exemple.com"  # Met ton vrai email GitHub ici

# 2. FONCTION POUR EXÉCUTER LES COMMANDES SANS LE TERMINAL
def executer(commande):
    try:
        subprocess.run(commande, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ Réussi : {commande}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur sur : {commande}\n{e.stderr}")

print("--- ÉTAPE 1 : CRÉATION DU DÉPÔT SUR GITHUB ---")

headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}
data = {
    "name": repo_name,
    "private": False  # Mets True si tu veux que ton projet soit privé
}

# Appel à l'API GitHub pour créer le dépôt
reponse = requests.post("https://api.github.com/user/repos", headers=headers, json=data)

if reponse.status_code == 201:
    print(f"🎉 Super ! Le dépôt '{repo_name}' a été créé avec succès sur ton compte GitHub.")
elif reponse.status_code == 422:
    print(f"ℹ️ Le dépôt '{repo_name}' existe déjà sur ton compte GitHub (ou a déjà été créé).")
else:
    print(f"❌ Échec de la création. Code erreur : {reponse.status_code}")
    print(reponse.text)

print("\n--- ÉTAPE 2 : TRANSFERT DES FICHIERS ---")

# Configuration de ton identité pour éviter l'erreur de l'autre fois
executer(f'git config user.email "{email}"')
executer(f'git config user.name "{username}"')

# Initialisation du dossier Git s'il n'existe pas
if not os.path.exists('.git'):
    executer("git init")

# Nettoyage et configuration de l'adresse de transfert sécurisée
executer("git remote remove origin")
remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
executer(f"git remote add origin {remote_url}")

# On pousse tout le contenu de Replit vers ton nouveau dépôt GitHub
executer("git branch -M main")
executer("git add .")
executer('git commit -m "Premier transfert automatique sans terminal"')
executer("git push -u origin main --force")

print("\n--- FIN DU PROCESSUS ---")
