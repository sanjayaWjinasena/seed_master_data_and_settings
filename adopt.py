# -*- coding: utf-8 -*-
"""Seed-or-adopt loader for this module's master data (v17.0.1.0.12).

Two kinds of target database:

* FRESH (empty Odoo, e.g. an Odoo.sh dev branch): load the five seed XML
  files exactly as before: 3 companies, 35 users, 63 warehouses, then the
  rest of post_init_hook (temp passwords, company access, warehouse
  replication, Studio flags, ...).

* REAL DATA (a production copy, e.g. an Odoo.sh staging branch, still
  carrying studio_customization and the real companies/users): push NO
  data. Each seed record that already exists is only bound to this
  module's xmlid, so other repos' refs (company_jinasena_pvt_ltd,
  user_146, ...) resolve to the real record. Nothing is written to it,
  nothing missing is created, no password or setting is touched.
  Developer decision 2026-10-05: on real data the modules are installed
  for functionality, not to push data.

Why not in the manifest's 'data' any more: Odoo writes every data-file
record on install, even when it already exists, which would overwrite
production values (user companies, partner contact fields, ...). Loading
from the hook is the only way to choose per database.

All xmlids are noupdate=True. The files are no longer loaded on upgrade,
so noupdate keeps ir.model.data._process_end from deleting the records.
ORM only.
"""
import ast
import logging
import os

from lxml import etree

from odoo.tools import convert_file

_logger = logging.getLogger(__name__)

MODULE = 'seed_master_data_and_settings'
FILES = [                                   # same order as the old manifest
    'data/res_partner_companies.xml',
    'data/res_company.xml',
    'data/res_partner_users.xml',
    'data/res_users.xml',
    'data/stock_warehouse.xml',
]
_HERE = os.path.dirname(os.path.abspath(__file__))
_COMPANY_NAMES = ('Jinasena (Pvt) Ltd.', 'Jinasena Agricultural Machinery (Pvt) Ltd.')


def is_real_data_env(env):
    """True on a production-like database: Studio customizations installed,
    or the real Jinasena companies already present before this module loads."""
    studio = env['ir.module.module'].sudo().search_count([
        ('name', '=', 'studio_customization'), ('state', '=', 'installed')])
    companies = env['res.company'].sudo().search_count([('name', 'in', list(_COMPANY_NAMES))])
    return bool(studio or companies)


def _records(rel):
    return list(etree.parse(os.path.join(_HERE, rel)).iter('record'))


def _field(rec, name):
    return rec.find(f"field[@name='{name}']")


def _bind(env, xmlid, model, res_id):
    IMD = env['ir.model.data'].sudo()
    if IMD.search_count([('module', '=', MODULE), ('name', '=', xmlid)]):
        return False
    IMD.create({'module': MODULE, 'name': xmlid, 'model': model, 'res_id': res_id, 'noupdate': True})
    return True


def adopt_existing(env):
    """Bind seed xmlids to the matching real records. Writes nothing else."""
    sudo = env.sudo()
    counts = dict(companies=0, company_partners=0, users=0, user_partners=0, warehouses=0)
    skipped = dict(users=[], warehouses=[], companies=[])

    # companies by name; their partner comes with them
    company_by_xmlid = {}
    for rec in _records('data/res_company.xml'):
        name = _field(rec, 'name').text
        company = sudo['res.company'].search([('name', '=', name)], limit=2)
        if len(company) != 1:
            skipped['companies'].append(name); continue
        company_by_xmlid[rec.get('id')] = company
        counts['companies'] += _bind(env, rec.get('id'), 'res.company', company.id)
        pref = _field(rec, 'partner_id')
        if pref is not None and company.partner_id:
            counts['company_partners'] += _bind(env, pref.get('ref'), 'res.partner', company.partner_id.id)

    # users by login; their partner comes with them
    Users = sudo['res.users'].with_context(active_test=False)
    for rec in _records('data/res_users.xml'):
        login = _field(rec, 'login').text
        user = Users.search([('login', '=', login)], limit=2)
        if len(user) != 1:
            skipped['users'].append(login); continue
        counts['users'] += _bind(env, rec.get('id'), 'res.users', user.id)
        pref = _field(rec, 'partner_id')
        if pref is not None and user.partner_id:
            counts['user_partners'] += _bind(env, pref.get('ref'), 'res.partner', user.partner_id.id)

    # warehouses by (code, company)
    Wh = sudo['stock.warehouse'].with_context(active_test=False)
    for rec in _records('data/stock_warehouse.xml'):
        code = _field(rec, 'code').text
        cref = _field(rec, 'company_id').get('ref')
        company = company_by_xmlid.get(cref)
        wh = Wh.search([('code', '=', code), ('company_id', '=', company.id)], limit=2) if company else Wh.browse()
        if len(wh) != 1:
            skipped['warehouses'].append(code); continue
        counts['warehouses'] += _bind(env, rec.get('id'), 'stock.warehouse', wh.id)

    _logger.info("%s: REAL-DATA database, adopted existing records only (no data pushed): %s; "
                 "not present, not created: %s", MODULE, counts, {k: len(v) for k, v in skipped.items()})
    if skipped['users']:
        _logger.info("%s: seed users not on this database (not created): %s", MODULE, skipped['users'])
    return counts, skipped


def load_seed_files(env):
    """Fresh database: load the seed files as the manifest used to."""
    idref = {}
    for rel in FILES:
        convert_file(env, MODULE, rel, idref, mode='init', noupdate=True, kind='data',
                     pathname=os.path.join(_HERE, rel))
    _logger.info("%s: FRESH database, seeded %d data files", MODULE, len(FILES))
