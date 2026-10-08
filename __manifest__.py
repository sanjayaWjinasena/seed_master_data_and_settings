# -*- coding: utf-8 -*-
{
    'name': 'Jinasena : Masterdata : Setup Data',
    'version': '17.0.1.0.12',
    'summary': (
        'Seeds Jinasena companies and users '
        'from Clear-DB into a bare Odoo Enterprise instance.'
    ),
    'description': """
Standalone seed module for bootstrapping a fresh dev / staging / restore
env with the same master-data layout as Clear-DB production:

* 3 companies (Jinasena Pvt Ltd, Jinasena Agricultural Machinery, JLTD)
* 35 active users with a shared temp password (must be rotated post-install)
* No warehouses (removed in 17.0.1.0.12): warehouses are environment data.
  Databases that already had the 63 seeded warehouses keep them.

Additive: existing companies / users on the target DB
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
        'data/res_partner_companies.xml',
        'data/res_company.xml',
        'data/res_partner_users.xml',
        'data/res_users.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
