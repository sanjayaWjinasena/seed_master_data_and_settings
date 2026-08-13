# -*- coding: utf-8 -*-
"""v2 upgrade — grant existing admins access to the 3 seeded Jinasena
companies so they appear in the company switcher.

post_init_hook only fires on fresh install; on upgrade paths we
need this migration to run the same fix.
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
    spec = importlib.util.spec_from_file_location(
        'seed_hooks', hooks_path,
    )
    hooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hooks)
    env = api.Environment(cr, SUPERUSER_ID, {})
    hooks.grant_admins_access_to_seeded_companies(env)
