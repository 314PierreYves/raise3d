# HA-Raise3D

Intégration [Home Assistant](https://www.home-assistant.io/) (installable via [HACS](https://hacs.xyz/)) pour suivre une **Raise3D Pro2 Hyper Speed (Klipper)**, en **lecture seule**.

L'ancienne Remote Access API de Raise3D n'est plus disponible. L'intégration s'appuie à la place sur **r3monitor** ([printer/r3monitor.py](printer/r3monitor.py)), un petit serveur qui tourne sur l'imprimante :

```
Klipper (/tmp/klippy_uds) ─┐
                           ├─> r3monitor (HTTP :8090) ──> Home Assistant
MXCCameraServer (:30216) ──┘     /status  /raw  /snapshot.jpg
```

Aucune commande G-code n'est envoyée : ni r3monitor ni l'intégration ne peuvent agir sur l'imprimante.

## Entités

| Type | Entités |
|------|---------|
| Capteurs | État (en attente, impression, pause, terminée, annulée, erreur, Klipper injoignable), message Klipper, fichier, progression, temps d'impression, temps total, temps restant, fin estimée, filament utilisé, ventilateur |
| Températures | Buse gauche, buse droite et plateau : température, consigne, puissance de chauffe |
| Capteurs binaires | Impression en cours, connexion Klipper, détection de filament (F0, F1) |
| Caméra | Image fixe de la caméra de l'imprimante |
| Diagnostic | Activité (idle_timeout), charge système, dernière mise à jour |

Les buses, le plateau et les détecteurs de filament sont ajoutés automatiquement dès que r3monitor les remonte. Si Klipper redémarre, les capteurs passent « indisponible » et la connexion Klipper passe à « off », puis tout revient seul.

Les **diagnostics** téléchargeables depuis l'intégration contiennent la réponse `/status` et les objets Klipper bruts (`/raw`).

## 1. Installer r3monitor sur l'imprimante

r3monitor n'utilise que la bibliothèque standard Python (2.7 ou 3.x). Copiez-le sur l'imprimante puis lancez-le :

```bash
scp printer/r3monitor.py <utilisateur>@<ip-imprimante>:
ssh <utilisateur>@<ip-imprimante> 'nohup python r3monitor.py >/tmp/r3monitor.log 2>&1 &'
```

Pour qu'il survive à un redémarrage, ajoutez ce lancement au mécanisme de démarrage de l'imprimante.

Vérifiez ensuite depuis le réseau de Home Assistant que `http://<ip-imprimante>:8090/status` renvoie du JSON. Le tableau de bord intégré est sur `http://<ip-imprimante>:8090/`.

> r3monitor écoute sur `0.0.0.0` sans authentification. Toute machine du réseau local peut donc lire l'état **et l'image de la caméra**. Gardez l'imprimante sur un réseau de confiance.

## 2. Installer l'intégration

### Via HACS (dépôt personnalisé)

> HACS n'accepte que les dépôts **GitHub**. Publiez (ou mettez en miroir) ce dépôt sur GitHub, puis :

1. HACS → menu ⋮ → **Dépôts personnalisés**.
2. URL du dépôt GitHub, catégorie **Integration**.
3. Installez **Raise3D**, puis redémarrez Home Assistant.

### Manuelle

Copiez `custom_components/raise3d` dans `config/custom_components/` de Home Assistant, puis redémarrez.

## 3. Configurer

**Paramètres → Appareils et services → Ajouter une intégration → Raise3D**, puis renseignez :

- **Hôte** : IP de l'imprimante
- **Port** : `8090`
- **Nom** : nom de l'appareil (« Raise3D Pro2 » par défaut)

L'intervalle d'interrogation (10 s par défaut, de 2 à 300 s) se règle via **Configurer**. r3monitor lit Klipper toutes les 2 s, donc descendre sous 2 s n'apporte rien.

## Alternative MQTT

r3monitor publie aussi `/status` toutes les 10 s sur le topic `raise3d/pro2/status` (retain), si `mosquitto_pub` est présent sur l'imprimante. Le broker par défaut est `127.0.0.1` (`MQTT_HOST` dans le script). Cette intégration n'utilise pas MQTT : elle interroge directement l'API HTTP.

## Dépannage

```yaml
logger:
  logs:
    custom_components.raise3d: debug
```

- `curl http://<ip-imprimante>:8090/status` : résumé vu par Home Assistant.
- `curl http://<ip-imprimante>:8090/raw` : objets Klipper bruts.
- `/tmp/r3monitor.log` sur l'imprimante : erreurs de lecture Klipper ou caméra.

## Développement

```bash
uv venv && uv pip install pytest-homeassistant-custom-component PyTurboJPEG
.venv/bin/pytest
```
