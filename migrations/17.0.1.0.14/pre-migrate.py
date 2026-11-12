"""v1.0.14: backfill noupdate=True on the adopted xmlids, so the upgrade stops deleting them.

Why this exists
---------------
Up to v1.0.11 the five adoption files were listed in the manifest's ``data``:

    data/res_partner_companies.xml, data/res_company.xml,
    data/res_partner_users.xml, data/res_users.xml, data/stock_warehouse.xml

v1.0.12 moved them to the post_init_hook (adopt.py) so a production copy is
adopted instead of overwritten. adopt.py creates every one of those xmlids with
``noupdate=True`` on purpose, and says why:

    All xmlids are noupdate=True. The files are no longer loaded on upgrade,
    so noupdate keeps ir.model.data._process_end from deleting the records.

What it could not do is fix the databases that already existed. Their rows were
written while the files were still in ``data``, so they carry ``noupdate=false``,
and the post_init_hook never runs again to correct them -- it only runs on
install.

That combination is destructive. ``_process_end`` collects every ir_model_data
row of an updated module with ``COALESCE(noupdate, false) != true`` whose xmlid
was not loaded during the run, and deletes the record. Because the five files
are no longer loaded on upgrade, *every* adopted record qualifies: on this
database 3 companies, 38 partners, 35 users and 63 warehouses.

The upgrade only failed instead of wiping them because the first warehouse it
tried to delete could not go:

    update or delete on table "stock_picking_type" violates foreign key
    constraint "stock_rule_picking_type_id_fkey" on table "stock_rule"
    DETAIL: Key (id)=(528) is still referenced from table "stock_rule".

A foreign key is not a safety net to rely on. Setting the flag the hook would
have set removes the records from _process_end's reach entirely.

Fix
---
Flag the module's ir_model_data rows for the adopted models. The models are read
from the five files rather than hardcoded, so a file that gains a new model is
covered without editing this script.

``security/ir.model.access.csv`` is still in ``data`` and is deliberately left
updatable -- only the adopted models are flagged.

Idempotent: rows already flagged are not touched.
"""

import logging
import os

from lxml import etree

_logger = logging.getLogger(__name__)

MODULE = "seed_master_data_and_settings"

# Same list as adopt.py's FILES: the data files loaded by post_init_hook only.
ADOPTED_FILES = (
    "data/res_partner_companies.xml",
    "data/res_company.xml",
    "data/res_partner_users.xml",
    "data/res_users.xml",
    "data/stock_warehouse.xml",
)


def _adopted_models():
    """Models declared by the adoption files, read from the files themselves."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    models = set()
    for rel in ADOPTED_FILES:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        for record in etree.parse(path).iter("record"):
            model = record.get("model")
            if model:
                models.add(model)
    return models


def migrate(cr, version):
    if not version:
        return

    models = _adopted_models()
    if not models:
        _logger.warning(
            "No adoption data files found; leaving ir_model_data.noupdate untouched"
        )
        return

    cr.execute(
        """
        UPDATE ir_model_data
           SET noupdate = true
         WHERE module = %s
           AND model IN %s
           AND COALESCE(noupdate, false) IS NOT TRUE
     RETURNING model
        """,
        (MODULE, tuple(sorted(models))),
    )
    rows = [r[0] for r in cr.fetchall()]
    if not rows:
        return

    per_model = {}
    for model in rows:
        per_model[model] = per_model.get(model, 0) + 1
    _logger.info(
        "Flagged %s adopted xmlid(s) as noupdate so _process_end no longer deletes them: %s",
        len(rows),
        ", ".join(f"{m}={n}" for m, n in sorted(per_model.items())),
    )
