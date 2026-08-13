# -*- coding: utf-8 -*-
"""v7 upgrade — apply per-user data (signature/image/groups/Studio
fields) from bundled Clear-DB snapshot.

post_init_hook only fires on fresh install; this migration runs the
same hook on the upgrade path. Idempotent — every write is an
unconditional overwrite.
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
    hooks.apply_user_data(env)
