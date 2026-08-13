# -*- coding: utf-8 -*-
"""v9 upgrade — defensive re-run of seed_portal_signature_only.

v8 crashed on `AttributeError: 'res.company' object has no attribute
'portal_confirmation_pay'` because that field lives on res.company
only in certain Odoo module configurations. Hook now guards with
hasattr() and also writes the sale.* ir.config_parameter fallbacks.
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
