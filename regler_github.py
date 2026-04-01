import requests
import base64
import os
import time
from dotenv import load_dotenv

load_dotenv()

# On utilise tes secrets Replit que j'ai vus sur ta photo
POOLS = [
    {"user": os.getenv("USER_3"), "token": os.getenv("TOKEN_3")},
    {"user": os.getenv("USER_2"), "token": os.getenv("TOKEN_2")}
]

def reparer_stockage():
    print("🤖 RECHERCHE DES DÉPÔTS EN COURS...")
    for pool in POOLS:
        u = pool["user"]
        t = pool["token"]

        if not t or not u:
            continue

        try:
            # ÉTAPE 1 : Demander à GitHub la liste de tes dépôts pour trouver le bon nom
            repo_res = requests.get(f"https://api.github.com/users/{u}/repos", 
                                    headers={"Authorization": f"token {t}"})

            if repo_res.status_code == 200:
                repos = repo_res.json()
                if not repos:
                    print(f"❌ Aucun dépôt trouvé sur le compte {u}")
                    continue

                # On prend le premier dépôt qui contient "aura" ou le tout premier de la liste
                target_repo = repos[0]['name']
                for r in repos:
                    if "aura" in r['name'].lower():
                        target_repo = r['name']
                        break

                print(f"📦 Dépôt détecté : {target_repo} sur le compte {u}")

                # ÉTAPE 2 : Créer le dossier videos
                url = f"https://api.github.com/repos/{u}/{target_repo}/contents/videos/robot_ok.txt"
                data = {
                    "message": "✅ Activation du stockage",
                    "content": base64.b64encode(b"OK").decode(),
                    "branch": "main"
                }
                headers = {"Authorization": f"token {t}", "User-Agent": "Aura-Bot"}

                res = requests.put(url, json=data, headers=headers)

                if res.status_code in [200, 201]:
                    print(f"✨ SUCCÈS TOTAL sur {u} !")
                else:
                    print(f"⚠️ Note : {res.status_code} (Peut-être déjà prêt)")
            else:
                print(f"❌ Impossible d'accéder au compte {u} (Vérifie ton Token)")

        except Exception as e:
            print(f"💥 Erreur critique : {e}")

if __name__ == "__main__":
    reparer_stockage()
