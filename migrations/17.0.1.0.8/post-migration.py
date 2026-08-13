# -*- coding: utf-8 -*-
"""v8 upgrade — enforce Clear-DB's signature-only portal setup.

PATCHED after v8/v9 both crashed on missing `portal_confirmation_pay`
attribute + `sale.order` model absent from registry. Now delegates to
the current hook which guards both cases (hasattr + 'sale.order' in
env). Safe to re-run on failed installs.
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
