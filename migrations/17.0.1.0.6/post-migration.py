# -*- coding: utf-8 -*-
"""v6 upgrade — retry warehouse replication with savepoint isolation.

v5 crashed on migration:
  psycopg2.errors.InFailedSqlTransaction: current transaction is
  aborted, commands ignored until end of transaction block

Cause: one of the Wh.create(vals) calls hit a SQL-level error (e.g.
a company without a required default set), and the Python-level
try/except caught it but the outer Postgres transaction was already
poisoned — every subsequent Wh.search() then failed with the same
error.

Fix: wrap each Wh.create in env.cr.savepoint() so a create failure
only rolls back the savepoint, leaving the outer transaction clean.
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
    hooks.seed_studio_location_flags(env)
    hooks.seed_factory_repair_config_param(env)
