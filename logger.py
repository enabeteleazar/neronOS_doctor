# app/logger.py
# Logger centralisé avec rotation de fichiers et sortie console colorée

import logging
import os
from logging.handlers import RotatingFileHandler
from doctor.config import cfg

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MASK_TEXT = "***MASKED***"


class RedactingFilter(logging.Filter):
    """Logging filter that masks known secret values in log messages and args.

    - Masks cfg.API_KEY occurrences in log messages.
    - Masks values in dict-style args whose keys are sensitive using mask_dict.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Mask dict-style args (e.g., logger.info(".. %s", {'api_key': key}))
            if isinstance(record.args, dict):
                try:
                    from doctor.utils import mask_dict
                    record.args = mask_dict(record.args)
                except Exception:
                    # fallback: remove args to avoid leaking secrets
                    record.args = {}

            # Mask direct occurrences of API_KEY in the message
            try:
                secret = getattr(cfg, "API_KEY", None)
                if secret and isinstance(secret, str) and secret:
                    if isinstance(record.msg, str) and secret in record.msg:
                        record.msg = record.msg.replace(secret, MASK_TEXT)
                    # If args is a tuple/list, mask any string occurrences
                    if isinstance(record.args, (list, tuple)):
                        new_args = []
                        for a in record.args:
                            if isinstance(a, str) and secret in a:
                                new_args.append(a.replace(secret, MASK_TEXT))
                            else:
                                new_args.append(a)
                        record.args = tuple(new_args)
            except Exception:
                pass

        except Exception:
            # Don't break logging on filter errors
            return True
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # déjà configuré

    logger.setLevel(logging.DEBUG)

    # --- Console handler ---
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    console.addFilter(RedactingFilter())
    logger.addHandler(console)

    # --- Fichier handler avec rotation ---
    try:
        os.makedirs(cfg.LOG_DIR, exist_ok=True)
        log_file = os.path.join(cfg.LOG_DIR, "doctor.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        file_handler.addFilter(RedactingFilter())
        logger.addHandler(file_handler)
    except Exception as e:
        # Si on ne peut pas créer le dossier de logs (permissions, FS en lecture seule, etc.),
        # on continue avec le handler console uniquement.
        logger.warning("Cannot use file handler for logs (%s): %s", cfg.LOG_DIR, e)

    return logger
