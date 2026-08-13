# -*- coding: utf-8 -*-
"""v10 upgrade — re-run seed_portal_signature_only with sale.order
model-existence guard.

v8 and v9 both crashed the migration flow: v8 on
`portal_confirmation_pay` attribute, v9 on `sale.order` KeyError
(seed module doesn't depend on `sale`, so the model isn't in the
registry when this migration runs on installs without sale).

v10's hook now:
  - guards company writes with hasattr()
  - checks 'sale.order' in env before touching existing SOs
  - wraps the search+write in try/except

Rewriting v8's post-migration.py to also be safe so re-running from
scratch doesn't hit the same issue.
"""
import importlib.util
import os

from odoo import api, SUPERUSER_ID
from odoo.modules.module import get_module_path


def migrate(cr, version):
    if not version:
        return
    hooks_path = os.path.join(
        get_module_path('seed_master_data_and_settings'), 'hooks.py'
    )
    spec = importlib.util.spec_from_file_location('seed_hooks', hooks_path)
    hooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hooks)
    env = api.Environment(cr, SUPERUSER_ID, {})
    hooks.seed_portal_signature_only(env)
