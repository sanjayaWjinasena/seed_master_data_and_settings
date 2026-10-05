# -*- coding: utf-8 -*-
{
    'name': 'Jinasena : Masterdata : Setup Data',
    'version': '17.0.1.0.13',
    'summary': (
        'Seeds Jinasena companies, users, warehouses and stock locations '
        'from Clear-DB into a bare Odoo Enterprise instance.'
    ),
    'description': """
Standalone seed module for bootstrapping a fresh dev / staging / restore
env with the same master-data layout as Clear-DB production:

* 3 companies (Jinasena Pvt Ltd, Jinasena Agricultural Machinery, JLTD)
* 35 active users with a shared temp password (must be rotated post-install)
* 63 warehouses across the 3 companies (branch, production, repair, intransit)
* 244 stock locations (internal + transit + repair virtuals + view)
* Studio-owned x_studio_* flags on stock.location (only applied when
  Fix-repair is installed — guarded in post_init_hook)

Additive: existing companies / warehouses / users on the target DB
are untouched. All records use stable xmlids so upgrades are safe.
""",
    'author': 'Jinasena Agricultural Machinery (Pvt) Ltd.',
    'category': 'Tools',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'stock',
        'hr',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        # v17.0.1.0.12: data/res_partner_companies.xml, res_company.xml,
        # res_partner_users.xml, res_users.xml and stock_warehouse.xml are
        # loaded by post_init_hook (adopt.py) so a production copy is
        # adopted without pushing data. Do not list them here.
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
