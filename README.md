# Neron Doctor

Service FastAPI de diagnostic et d'autocorrection pour l'infrastructure Neron.
Il inspecte les modules Core et LLM, teste les endpoints HTTP, lit l'etat
systemd et analyse les journaux des services surveilles.

Version applicative actuelle : `1.1.0`.

## Architecture

```text
doctor/
├── app.py        # Point d'entree FastAPI et routes HTTP
├── config.py     # Configuration depuis /etc/neron/neron.yaml
├── auth.py       # Auth API key via header X-Doctor-Key
├── logger.py     # Logger console + fichier avec rotation
├── runner.py     # Pipeline de diagnostic complet
├── analyzer.py   # Analyse statique Python: structure, entrypoints, syntaxe
├── monitor.py    # Metriques systeme, systemctl, journalctl
├── tester.py     # Tests HTTP des services Neron
├── fixer.py      # Autocorrection simple par restart systemd
└── utils.py      # Helpers systeme
```

## Configuration

Doctor lit la section `doctor:` du fichier global Neron.

Chemin par defaut :

```text
/etc/neron/neron.yaml
```

Il peut etre remplace avec :

```bash
NERON_CONFIG=/chemin/vers/neron.yaml
```

Exemple de section :

```yaml
doctor:
  api_key: "change-me"
  paths:
    core: /etc/neron/core
    llm: /etc/neron/llm
    logs: /var/log/neron
  endpoints:
    server_health: http://localhost:8010/health
    server_status: http://localhost:8010/status
    llm_health: http://localhost:8765/llm/health
    ollama: http://localhost:11434/api/tags
  services:
    - neron-core
    - neron-llm
    - ollama
  timing:
    http_timeout: 5
    fix_retry_count: 3
    fix_retry_delay: 4
    journal_lines: 100
  thresholds:
    cpu: 80
    mem: 85
    disk: 90
```

Si `doctor.api_key` est vide, l'authentification est desactivee.

## Endpoints

Tous les endpoints utilisent le header `X-Doctor-Key` quand `doctor.api_key`
est configure.

| Methode | Endpoint | Description |
|---|---|---|
| `POST` | `/diagnose` | Diagnostic complet: analyse, monitoring, tests, fixes, re-test |
| `GET` | `/health` | Snapshot HTTP rapide des services configures |
| `GET` | `/monitor/system` | CPU, RAM, disque |
| `GET` | `/monitor/services` | Etat des services systemd configures |
| `GET` | `/monitor/journals` | Erreurs et warnings journalctl par service |
| `GET` | `/analyze/core` | Analyse statique du module Core |
| `GET` | `/analyze/llm` | Analyse statique du module LLM |
| `GET` | `/analyze` | Analyse statique Core + LLM |
| `POST` | `/fixes` | Tests HTTP puis autocorrection simple si necessaire |
| `POST` | `/reload` | Recharge la configuration YAML sans redemarrer le service |

## Pipeline De Diagnostic

```text
POST /diagnose
  1. Analyse statique de /etc/neron/core et /etc/neron/llm
  2. Collecte des metriques systeme
  3. Lecture de l'etat systemd des services configures
  4. Analyse des journaux journalctl
  5. Tests HTTP des endpoints Core et LLM
  6. Autocorrection simple
  7. Re-test final des endpoints
```

## Lancement Local

Depuis `/etc/neron` :

```bash
source venv/bin/activate
pip install -r requirements/doctor.txt -c requirements/constraints.txt
uvicorn doctor.app:app --host 0.0.0.0 --port 8020 --workers 1
```

Documentation interactive :

```text
http://localhost:8020/docs
```

## Deploiement systemd

Le service fourni est [deploy/neron-doctor.service](../deploy/neron-doctor.service).

Commande principale :

```ini
WorkingDirectory=/etc/neron
Environment=PYTHONPATH=/etc/neron/doctor
ExecStart=/etc/neron/venv/bin/uvicorn doctor.app:app --host 0.0.0.0 --port 8020 --workers 1
```

Activation :

```bash
sudo cp deploy/neron-doctor.service /etc/systemd/system/neron-doctor.service
sudo systemctl daemon-reload
sudo systemctl enable --now neron-doctor
sudo journalctl -u neron-doctor -f
```

## Exemples curl

Sans cle API :

```bash
curl http://localhost:8020/health
curl http://localhost:8020/monitor/system
curl -X POST http://localhost:8020/diagnose
```

Avec cle API :

```bash
curl -H "X-Doctor-Key: <cle>" http://localhost:8020/health
curl -H "X-Doctor-Key: <cle>" -X POST http://localhost:8020/reload
```

## Limites Actuelles

- Pas de streaming SSE expose dans le code actuel.
- Pas de route `/`, `/status`, `/logs`, `/config` ni `/fix/{service}`.
- `fixer.py` applique seulement des redemarrages systemd simples.
- Les actions systemd dependent des permissions du compte qui execute
  `neron-doctor`.
