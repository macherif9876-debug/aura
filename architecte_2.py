import os
import requests
import time

# --- CONFIGURATION ---
TOKEN = os.getenv("TOKEN_2")
USERNAME = os.getenv("USER_2")

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# On commence au 299 (puisque tu en as déjà 98 sur ce compte qui a démarré à 201)
# 201 + 98 = 299
START = 299 
END = 400

print(f"🚀 Sprint Final pour {USERNAME}")
print(f"📦 Objectif : Créer les {END - START + 1} dépôts restants")
print(f"⏱️  Cadence : 25 secondes\n")

for i in range(START, END + 1):
    nom = f"aura-vids-{i}"
    data = {
        "name": nom,
        "private": False,
        "auto_init": True
    }
    
    res = requests.post("https://api.github.com/user/repos", json=data, headers=headers)
    
    if res.status_code == 201:
        print(f"✅ [{i}/{END}] {nom} créé !")
        time.sleep(25) # Ta nouvelle cadence de 25 secondes
        
    elif res.status_code == 422:
        print(f"⏩ {nom} existe déjà, on saute.")
        
    elif res.status_code in [403, 429]:
        print(f"🛑 Blocage GitHub (trop rapide). Pause de 10 min...")
        time.sleep(600)
    else:
        print(f"❌ Erreur {res.status_code} sur {nom}")
        time.sleep(5)

print("\n🏆 TERMINÉ ! Tes dépôts sont au complet.")
