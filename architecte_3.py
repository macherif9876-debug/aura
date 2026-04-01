import os
import requests
import time

# --- CONFIGURATION DU COMPTE 3 ---
# Ces informations doivent être dans ton cadenas 🔒 Secrets
TOKEN = os.getenv("TOKEN_3")
USERNAME = os.getenv("USER_3")

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def lancer_compte_3():
    # Définition de la plage pour le compte 3
    DEBUT = 401
    FIN = 601 # S'arrêtera à 600

    if not TOKEN or not USERNAME:
        print("❌ ERREUR : TOKEN_3 ou USER_3 introuvable dans les Secrets !")
        return

    print(f"🚀 Lancement du Compte n°3 : {USERNAME}")
    print(f"📦 Création des unités de stockage {DEBUT} à 600")
    print(f"⏱️  Pause de sécurité : 30 secondes\n")

    for i in range(DEBUT, FIN):
        nom_depot = f"aura-vids-{i}"
        
        data = {
            "name": nom_depot,
            "private": False,
            "auto_init": True,
            "description": f"Aura Pro Cloud Storage - Unit {i}"
        }
        
        # Envoi de la requête à GitHub
        res = requests.post("https://api.github.com/user/repos", json=data, headers=headers)
        
        if res.status_code == 201:
            print(f"✅ [{i}/600] {nom_depot} créé avec succès.")
            time.sleep(30) # Ta pause de 30 secondes
            
        elif res.status_code == 422:
            print(f"⏩ {nom_depot} existe déjà. On saute au suivant.")
            # Pas de pause ici pour aller plus vite vers les manquants
            
        elif res.status_code in [403, 429]:
            print("\n🛑 LIMITE ATTEINTE : GitHub demande une pause.")
            print("😴 Sommeil forcé de 10 minutes...")
            time.sleep(600)
            
        else:
            print(f"❌ Erreur {res.status_code} sur {nom_depot}")
            print(f"Détail : {res.text}")
            time.sleep(10)

if __name__ == "__main__":
    lancer_compte_3()
