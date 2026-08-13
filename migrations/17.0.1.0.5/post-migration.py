# -*- coding: utf-8 -*-
"""v5 upgrade — replicate all 45 distinct Clear-DB warehouse codes
across every active company on the target env.

post_init only fires on fresh install; on upgrade we invoke the same
hook directly. Idempotent: existing (code, company_id) warehouses
are skipped.
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
    hooks.replicate_warehouses_to_all_companies(env)
    # Re-run flags + factory config since new warehouses just landed
    hooks.seed_studio_location_flags(env)
    hooks.seed_factory_repair_config_param(env)
