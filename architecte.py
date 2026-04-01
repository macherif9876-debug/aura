import os
import requests
import time

# --- CONFIGURATION ---
TOKEN = os.getenv("GH_TOKEN_1") 
USERNAME = "macherif9876-debug" 

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

print(f"⚠️ ATTENTION : Démarrage du GRAND NETTOYAGE sur {USERNAME}...")
print("Toutes les anciennes données vont être supprimées. \n")

# --- PHASE 1 : LE NETTOYAGE (SUPPRESSION) ---
# On récupère la liste de tous les dépôts existants
url_liste = "https://api.github.com/user/repos?per_page=100&type=owner"
reponse_liste = requests.get(url_liste, headers=headers)

if reponse_liste.status_code == 200:
    depots_existants = reponse_liste.json()
    
    if len(depots_existants) == 0:
        print("✅ Aucun ancien dépôt trouvé. Le compte est déjà propre.")
    else:
        print(f"🚨 {len(depots_existants)} anciens dépôts trouvés. Suppression en cours...")
        
        for depot in depots_existants:
            nom_repo = depot['name']
            url_delete = f"https://api.github.com/repos/{USERNAME}/{nom_repo}"
            
            # On supprime
            res = requests.delete(url_delete, headers=headers)
            
            if res.status_code == 204:
                print(f"🗑️ Dépôt '{nom_repo}' supprimé.")
            else:
                print(f"❌ Impossible de supprimer '{nom_repo}'.")
            
            time.sleep(1) # Petite pause pour la sécurité

else:
    print("❌ Erreur impossible de lire la liste des dépôts.")

print("\n--- 🧹 NETTOYAGE TERMINÉ ---\n")
print("--- 🏗️ DÉBUT DE LA CONSTRUCTION (1 à 200) ---\n")

# --- PHASE 2 : LA CONSTRUCTION ---
for i in range(1, 201):
    nom_nouveau = f"aura-vids-{i}"
    
    data = {
        "name": nom_nouveau,
        "private": False, 
        "description": "Aura Pro Storage Unit",
        "auto_init": True
    }
    
    res = requests.post("https://api.github.com/user/repos", json=data, headers=headers)
    
    if res.status_code == 201:
        print(f"✅ Dépôt [{i}/200] : {nom_nouveau} créé !")
    elif res.status_code == 422:
        print(f"⚠️ {nom_nouveau} existe déjà.")
    else:
        print(f"❌ Erreur sur {nom_nouveau} : {res.text}")
        
    time.sleep(2) # Pause obligatoire

print("\n🏆 MISSION ACCOMPLIE ! Ton compte est propre et tes 200 dépôts sont prêts.")
