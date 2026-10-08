# -*- coding: utf-8 -*-
"""17.0.1.0.12: the module no longer seeds warehouses (data/stock_warehouse.xml
removed from the manifest; the hook that replicated 45 warehouse codes into
every company is gone).

Databases that already have the 63 seeded warehouses keep them: their
ir.model.data rows are flagged noupdate, so Odoo's end-of-upgrade cleanup does
not try to delete warehouses (and their locations / routes / picking types)
that stock moves may use. Fresh installs simply get no warehouses. ORM only.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    rows = env['ir.model.data'].sudo().search([
        ('module', '=', 'seed_master_data_and_settings'),
        ('model', '=', 'stock.warehouse'),
        ('noupdate', '=', False),
    ])
    rows.write({'noupdate': True})
