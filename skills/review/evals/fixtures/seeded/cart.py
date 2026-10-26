"""Shopping cart helpers. Seeded defects for the review evals: do not fix."""
import json


# SEEDED: mutable default argument (google-pystyle-2.12, ruff B006). Items leak between calls.
def add_item(item, cart=[]):
    cart.append(item)
    return cart


def load_cart(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    # SEEDED: bare except (google-pystyle-2.4, ruff E722). Swallows KeyboardInterrupt.
    except:
        return []
