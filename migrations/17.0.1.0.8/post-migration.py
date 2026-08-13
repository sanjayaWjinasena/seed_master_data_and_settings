# -*- coding: utf-8 -*-
"""v8 upgrade — enforce Clear-DB's signature-only portal setup:

  res.company.portal_confirmation_pay = False on every company
  sale.order.require_payment = False on every existing SO

post_init_hook fires only on fresh install; upgrade path runs the
same hook via this migration. Idempotent.
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
