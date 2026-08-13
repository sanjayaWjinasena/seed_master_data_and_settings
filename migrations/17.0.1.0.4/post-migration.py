# -*- coding: utf-8 -*-
"""v4 upgrade — re-run the factory-repair-location seed with the
warehouse lookup fix.

v3's post_init used env.ref('seed_master_data_and_settings.warehouse_pw_jm_c<X>')
where X was the target env's company id — but the xmlid embeds the
Clear-DB SOURCE company id (c2), so the ref returned None on target
envs where the dev-assigned company id differs from 2.

v4 switches to search-by-(code, company_id) which is authoritative.
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
    hooks.seed_studio_location_flags(env)
    hooks.seed_factory_repair_config_param(env)
