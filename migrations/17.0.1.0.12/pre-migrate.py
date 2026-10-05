# -*- coding: utf-8 -*-
"""v17.0.1.0.12: protect already-seeded records when the seed XML files
leave the manifest.

From this version the five seed files are loaded by post_init_hook (see
adopt.py) instead of the manifest. On databases where the module is already
installed (e.g. the new-install dev env), the upgrade would no longer load
them, and ir.model.data._process_end would then DELETE every record whose
xmlid was not re-loaded: the companies, users, partners and warehouses.

_process_end skips xmlids flagged noupdate, so flag them all first. The
records themselves are not touched. ORM only; no-op on fresh installs.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MODELS = ('res.partner', 'res.company', 'res.users', 'stock.warehouse')


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    imd = env['ir.model.data'].sudo().search([
        ('module', '=', 'seed_master_data_and_settings'),
        ('model', 'in', MODELS),
        ('noupdate', '=', False),
    ])
    if imd:
        imd.write({'noupdate': True})
    _logger.info("seed_master_data_and_settings v12: flagged %d seed xmlids noupdate "
                 "(files now loaded by post_init_hook)", len(imd))
