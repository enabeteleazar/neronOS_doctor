# app/utils.py
# optionnel evolutif

import subprocess
from typing import Union, List, Any


def run_cmd(cmd: Union[str, List[str]], shell: bool = False) -> str:
    """
    Exécute une commande de façon plus sûre.
    - Préfère une liste d'arguments (shell=False).
    - Si une chaîne est fournie et shell=False, utilise shlex.split pour la parser.
    Retourne stdout (str). En cas d'erreur, retourne stdout+stderr ou le message d'exception.
    """
    try:
        if isinstance(cmd, str) and not shell:
            import shlex
            args = shlex.split(cmd)
        else:
            args = cmd
        completed = subprocess.run(
            args, shell=shell, text=True, capture_output=True, check=True
        )
        return completed.stdout
    except subprocess.CalledProcessError as e:
        # Retourne sortie disponible (stdout + stderr) pour faciliter le debug
        out = ""
        if getattr(e, "stdout", None):
            out += e.stdout
        if getattr(e, "stderr", None):
            out += e.stderr
        return out or str(e)
    except Exception as e:
        return str(e)


# --------------------
# Masking helpers
# --------------------
SENSITIVE_KEYS = {"api_key", "apikey", "apiKey", "password", "secret", "token", "authorization"}
MASK_TEXT = "***MASKED***"


def _mask_value(v: Any) -> Any:
    if isinstance(v, str) and v:
        return MASK_TEXT
    return v


def mask_dict(obj: Any) -> Any:
    """Retourne une copie de l'objet avec les clés sensibles masquées.

    Gère dict, list et valeurs scalaires.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
                out[k] = _mask_value(v)
            else:
                out[k] = mask_dict(v)
        return out
    if isinstance(obj, list):
        return [mask_dict(i) for i in obj]
    return obj
