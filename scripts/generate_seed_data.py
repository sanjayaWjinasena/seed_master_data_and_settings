# -*- coding: utf-8 -*-
"""Generate seed_master_data_and_settings/data/*.xml from Clear-DB RPC dumps.

Input JSON dumps live outside the module (in the Playwright workspace):
  clear-db-warehouses.json
  clear-db-locations.json
  clear-db-users.json  (payload: {users, groups, partners})

Usage:
    python scripts/generate_seed_data.py \
        --input-dir "D:/Odoo Playwright Tests/PlayWrite Testings" \
        --output-dir data

The generator is intentionally standalone (no Odoo runtime needed) so
we can regenerate the seed anytime Clear-DB drifts. Rerun after a fresh
RPC dump to update all XML files in one shot.

xmlid conventions:
  companies:  seed_master_data_and_settings.company_<cid>
  users:      seed_master_data_and_settings.user_<uid>
  partners:   seed_master_data_and_settings.partner_<pid>
  warehouses: seed_master_data_and_settings.warehouse_<code_slug>
"""
import argparse
import json
import os
import re
from xml.sax.saxutils import escape


COMPANY_XMLID_MAP = {
    1: 'company_jinasena_pvt_ltd',
    2: 'company_jinasena_agricultural_machinery',
    3: 'company_jltd',
}


def slugify(text):
    text = re.sub(r'[^a-zA-Z0-9]+', '_', text or '').strip('_').lower()
    return text or 'x'


def xattr(val):
    if val is None or val is False:
        return ''
    return escape(str(val))


def warehouse_xmlid(wh):
    code = slugify(wh['code'])
    company = COMPANY_XMLID_MAP.get(wh['company_id'][0], f"company_{wh['company_id'][0]}")
    return f"warehouse_{code}_c{wh['company_id'][0]}"


def gen_res_partner_companies(companies, out_path):
    """Company partners — the 3 companies' contact records."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<odoo>', '  <data noupdate="0">']
    for co in companies:
        pid = co['partner_id'][0]
        pname = co['partner_id'][1]
        lines.append(f'''    <record id="partner_{pid}" model="res.partner">
      <field name="name">{xattr(pname)}</field>
      <field name="is_company">1</field>
      <field name="company_type">company</field>
    </record>''')
    lines += ['  </data>', '</odoo>', '']
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


def gen_res_company(companies, out_path):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<odoo>', '  <data noupdate="0">']
    for co in companies:
        cid = co['id']
        xmlid = COMPANY_XMLID_MAP.get(cid, f'company_{cid}')
        partner_ref = f"partner_{co['partner_id'][0]}"
        currency = f'ref="base.{co["currency_id"][1]}"' if co.get('currency_id') else ''
        # Odoo country xmlids are ISO alpha-2 (base.lk for Sri Lanka)
        COUNTRY_ISO2 = {'Sri Lanka': 'lk'}
        country = ''
        if co.get('country_id'):
            iso = COUNTRY_ISO2.get(co['country_id'][1])
            if iso:
                country = f'      <field name="country_id" ref="base.{iso}"/>'
        fields = [
            f'      <field name="name">{xattr(co["name"])}</field>',
            f'      <field name="partner_id" ref="{partner_ref}"/>',
        ]
        if co.get('currency_id'):
            # LKR: base.LKR
            fields.append(f'      <field name="currency_id" ref="base.{co["currency_id"][1]}"/>')
        if country:
            fields.append(country)
        if co.get('sequence') is not None:
            fields.append(f'      <field name="sequence">{co["sequence"]}</field>')
        if co.get('email'):
            fields.append(f'      <field name="email">{xattr(co["email"])}</field>')
        if co.get('phone'):
            fields.append(f'      <field name="phone">{xattr(co["phone"])}</field>')
        if co.get('website'):
            fields.append(f'      <field name="website">{xattr(co["website"])}</field>')
        lines.append(f'    <record id="{xmlid}" model="res.company">')
        lines.extend(fields)
        lines.append('    </record>')
    lines += ['  </data>', '</odoo>', '']
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


def gen_res_partner_users(partners, out_path):
    """User partners — one record per user's res.partner_id."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<odoo>', '  <data noupdate="0">']
    for p in partners:
        pid = p['id']
        fields = [f'      <field name="name">{xattr(p["name"])}</field>']
        if p.get('email'):
            fields.append(f'      <field name="email">{xattr(p["email"])}</field>')
        if p.get('phone'):
            fields.append(f'      <field name="phone">{xattr(p["phone"])}</field>')
        if p.get('mobile'):
            fields.append(f'      <field name="mobile">{xattr(p["mobile"])}</field>')
        if p.get('function'):
            fields.append(f'      <field name="function">{xattr(p["function"])}</field>')
        if p.get('city'):
            fields.append(f'      <field name="city">{xattr(p["city"])}</field>')
        if p.get('lang'):
            fields.append(f'      <field name="lang">{xattr(p["lang"])}</field>')
        if p.get('tz'):
            fields.append(f'      <field name="tz">{xattr(p["tz"])}</field>')
        if p.get('company_id'):
            cid = p['company_id'][0]
            xid = COMPANY_XMLID_MAP.get(cid, f'company_{cid}')
            fields.append(f'      <field name="company_id" ref="{xid}"/>')
        lines.append(f'    <record id="partner_{pid}" model="res.partner">')
        lines.extend(fields)
        lines.append('    </record>')
    lines += ['  </data>', '</odoo>', '']
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


def gen_res_users(users, out_path):
    """User records — login/name/company/partner + company_ids m2m.

    Groups are NOT set here (they'd require a full res.groups xmlid
    lookup table). Post-install hook can seed groups from the JSON dump
    or admins can grant per-user via the UI.
    Passwords set in post_init_hook so the plaintext temp password never
    lives in git.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<odoo>', '  <data noupdate="0">']
    for u in users:
        uid = u['id']
        cid = u['company_id'][0]
        company_ref = COMPANY_XMLID_MAP.get(cid, f'company_{cid}')
        partner_ref = f'partner_{u["partner_id"][0]}'
        company_ids = u.get('company_ids') or [cid]
        company_refs_list = ', '.join(
            f"ref('{COMPANY_XMLID_MAP.get(c, f'company_{c}')}')"
            for c in company_ids
        )
        fields = [
            f'      <field name="login">{xattr(u["login"])}</field>',
            f'      <field name="name">{xattr(u["name"])}</field>',
            f'      <field name="partner_id" ref="{partner_ref}"/>',
            f'      <field name="company_id" ref="{company_ref}"/>',
            f'      <field name="company_ids" eval="[(6, 0, [{company_refs_list}])]"/>',
        ]
        if u.get('lang'):
            fields.append(f'      <field name="lang">{xattr(u["lang"])}</field>')
        if u.get('tz'):
            fields.append(f'      <field name="tz">{xattr(u["tz"])}</field>')
        if u.get('notification_type'):
            fields.append(f'      <field name="notification_type">{xattr(u["notification_type"])}</field>')
        lines.append(f'    <record id="user_{uid}" model="res.users">')
        lines.extend(fields)
        lines.append('    </record>')
    lines += ['  </data>', '</odoo>', '']
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


def gen_stock_warehouse(warehouses, out_path):
    """Warehouse records.

    Odoo auto-creates all sub-locations + picking types + routes on
    warehouse.create(). We only need name, code, company, sequence,
    step-config. Post-install hook applies x_studio_ flags on the
    auto-created child locations.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<odoo>', '  <data noupdate="0">']
    seen_codes = {}
    for wh in warehouses:
        xmlid = warehouse_xmlid(wh)
        # Dedup: two companies can share code (e.g. BR-EK on both co 1 and co 2).
        # xmlid includes company id already so no collision.
        cid = wh['company_id'][0]
        company_ref = COMPANY_XMLID_MAP.get(cid, f'company_{cid}')
        # partner_id points at the company partner — reuse partner_<pid>
        partner_pid = wh['partner_id'][0] if wh.get('partner_id') else None
        fields = [
            f'      <field name="name">{xattr(wh["name"])}</field>',
            f'      <field name="code">{xattr(wh["code"])}</field>',
            f'      <field name="company_id" ref="{company_ref}"/>',
        ]
        if partner_pid:
            fields.append(f'      <field name="partner_id" ref="partner_{partner_pid}"/>')
        if wh.get('sequence') is not None:
            fields.append(f'      <field name="sequence">{wh["sequence"]}</field>')
        for k in ('reception_steps', 'delivery_steps', 'manufacture_steps'):
            if wh.get(k):
                fields.append(f'      <field name="{k}">{xattr(wh[k])}</field>')
        # booleans
        for k in ('manufacture_to_resupply', 'buy_to_resupply'):
            if k in wh:
                fields.append(f'      <field name="{k}" eval="{wh[k]}"/>')
        lines.append(f'    <record id="{xmlid}" model="stock.warehouse">')
        lines.extend(fields)
        lines.append('    </record>')
    lines += ['  </data>', '</odoo>', '']
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


def gen_studio_location_flags_json(locations, out_path):
    """Dump just the (warehouse_code, complete_name, x_studio_*) tuples that
    the post_init_hook needs to lookup and re-apply on the target env.

    Studio flags CAN'T be seeded via XML data files here because our
    module is standalone — Fix-repair may or may not be installed.
    The hook guards on the fields existing before writing.
    """
    payload = []
    for loc in locations:
        wh = loc.get('warehouse_id')
        if not wh:
            # unassociated virtual/repair-only locations — skip in v1
            continue
        studio_fields = {
            k: loc.get(k)
            for k in (
                'x_studio_finished_good_location',
                'x_studio_repair_factory_location',
                'x_studio_repair_return_location',
                'x_studio_temp_location',
                'x_studio_return_receipt_location',
            )
            if loc.get(k)  # only include truthy values
        }
        if not studio_fields:
            continue
        payload.append({
            'warehouse_code': None,   # will fill below by joining
            'warehouse_display': wh[1],
            'complete_name': loc['complete_name'],
            'usage': loc['usage'],
            'flags': studio_fields,
        })
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--output-dir', default='data')
    args = parser.parse_args()

    with open(os.path.join(args.input_dir, 'clear-db-warehouses.json'), encoding='utf-8') as f:
        warehouses = json.load(f)
    with open(os.path.join(args.input_dir, 'clear-db-locations.json'), encoding='utf-8') as f:
        locations = json.load(f)
    with open(os.path.join(args.input_dir, 'clear-db-users.json'), encoding='utf-8') as f:
        users_payload = json.load(f)

    users = users_payload['users']
    partners = users_payload['partners']

    # We need the companies list too — synthesise from the wh company_ids
    # (only 3 companies on Clear-DB, but let's build from a hardcoded slice
    #  since res.company wasn't in the users payload).
    # Instead, extract from the first RPC we ran (embedded here):
    companies = [
        {
            'id': 1, 'name': 'Jinasena (Pvt) Ltd.',
            'partner_id': [1, 'Jinasena (Pvt) Ltd.'],
            'currency_id': [145, 'LKR'],
            'country_id': [129, 'Sri Lanka'],
            'sequence': 0,
            'email': 'rohana.b@jinasena.com.lk',
            'phone': '0112 687 916',
            'website': 'http://www.jinasena.com',
        },
        {
            'id': 2, 'name': 'Jinasena Agricultural Machinery (Pvt) Ltd.',
            'partner_id': [87, 'Jinasena Agricultural Machinery (Pvt) Ltd.'],
            'currency_id': [145, 'LKR'],
            'country_id': [129, 'Sri Lanka'],
            'sequence': 1,
        },
        {
            'id': 3, 'name': 'JLTD',
            'partner_id': [511, 'JLTD'],
            'currency_id': [145, 'LKR'],
            'sequence': 10,
        },
    ]

    os.makedirs(args.output_dir, exist_ok=True)
    gen_res_partner_companies(companies, os.path.join(args.output_dir, 'res_partner_companies.xml'))
    gen_res_company(companies, os.path.join(args.output_dir, 'res_company.xml'))
    gen_res_partner_users(partners, os.path.join(args.output_dir, 'res_partner_users.xml'))
    gen_res_users(users, os.path.join(args.output_dir, 'res_users.xml'))
    gen_stock_warehouse(warehouses, os.path.join(args.output_dir, 'stock_warehouse.xml'))
    gen_studio_location_flags_json(
        locations, os.path.join(args.output_dir, 'studio_location_flags.json')
    )
    print('OK — generated:')
    for f in sorted(os.listdir(args.output_dir)):
        p = os.path.join(args.output_dir, f)
        print(f'  {p}  ({os.path.getsize(p)} bytes)')


if __name__ == '__main__':
    main()
