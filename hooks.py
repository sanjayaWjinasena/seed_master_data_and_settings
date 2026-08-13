# -*- coding: utf-8 -*-
"""Post-install hook for seed_master_data_and_settings.

Handles the post-XML data-file work that XML can't express cleanly:

1. Set a shared temp password on every seeded res.users record so
   admins can log in and rotate it themselves. Plaintext temp password
   lives here (not in git-committed data XML) and MUST be rotated
   on production imports.

2. Apply Studio x_studio_* flags on stock.location records auto-
   created by the warehouse seed. The stock.location fields
   (x_studio_repair_return_location, _repair_factory_location, etc.)
   are declared by Fix-repair — guarded so this hook is a no-op if
   Fix-repair isn't installed on the target env.

3. Point Fix-repair's ir.config_parameter factory-repair-location
   at PW-JM/Stock for company 2 (Jinasena Agricultural Machinery)
   — same guard.
"""
import json
import logging
import os

_logger = logging.getLogger(__name__)

# Rotate this on every production restore. The password is intentionally
# strong-enough-to-pass-Odoo's default validation but must not survive.
SEED_TEMP_PASSWORD = 'ChangeMe2026!'

# Warehouse code -> role. Drives Studio-flag application on lot_stock_id.
# Extend as new warehouse-to-role conventions emerge.
_WAREHOUSE_ROLES = {
    # (code_prefix, company_id): {flag_field: True}
    'PW-JM': {'x_studio_repair_factory_location': True},
    'RP-JM': {'x_studio_repair_factory_location': True},
    'RP-CM': {'x_studio_repair_factory_location': True},
    'RP-QU': {'x_studio_repair_factory_location': True},
    'RP-SC': {'x_studio_repair_factory_location': True},
    'RP-EK': {'x_studio_repair_factory_location': True},
    # BR-* = branch warehouses that receive customer returns
    'BR-AM': {'x_studio_repair_return_location': True},
    'BR-AN': {'x_studio_repair_return_location': True},
    'BR-AV': {'x_studio_repair_return_location': True},
    'BR-BA': {'x_studio_repair_return_location': True},
    'BR-BE': {'x_studio_repair_return_location': True},
    'BR-BU': {'x_studio_repair_return_location': True},
    'BR-DA': {'x_studio_repair_return_location': True},
    'BR-EK': {'x_studio_repair_return_location': True},
    'BR-EM': {'x_studio_repair_return_location': True},
    'BR-GA': {'x_studio_repair_return_location': True},
    'BR-GK': {'x_studio_repair_return_location': True},
    'BR-JF': {'x_studio_repair_return_location': True},
    'BR-KA': {'x_studio_repair_return_location': True},
    'BR-KD': {'x_studio_repair_return_location': True},
    'BR-KU': {'x_studio_repair_return_location': True},
    'BR-NE': {'x_studio_repair_return_location': True},
    'BR-TH': {'x_studio_repair_return_location': True},
}


def seed_user_passwords(env):
    """Set a shared temp password on every seeded user record.

    Idempotent — writes the password unconditionally so re-running the
    hook restores the temp password (useful for staging refresh).
    Filters to users we own (module='seed_master_data_and_settings' via
    ir.model.data lookup) so we never overwrite admin's real password.
    """
    IMD = env['ir.model.data'].sudo()
    seeded_user_ids = IMD.search([
        ('module', '=', 'seed_master_data_and_settings'),
        ('model', '=', 'res.users'),
    ]).mapped('res_id')
    if not seeded_user_ids:
        return
    users = env['res.users'].sudo().browse(seeded_user_ids).exists()
    for user in users:
        user.password = SEED_TEMP_PASSWORD
    _logger.info(
        'seed_master_data_and_settings: set temp password on %d '
        'seeded user(s). ROTATE ON PRODUCTION.',
        len(users),
    )


def _has_fix_repair_flags(env):
    """True iff Fix-repair's stock.location x_studio_* fields exist."""
    field_names = env['ir.model.fields'].sudo().search([
        ('model', '=', 'stock.location'),
        ('name', 'in', [
            'x_studio_repair_return_location',
            'x_studio_repair_factory_location',
        ]),
    ]).mapped('name')
    return len(field_names) == 2


def seed_studio_location_flags(env):
    """Apply Studio flags to auto-created warehouse Stock locations.

    Warehouse creation triggers _create() side effects that auto-build
    the view + Stock + Input/Output/... sub-locations. We look them up
    by warehouse code + convention (lot_stock_id) and flag them per
    role.

    No-op if Fix-repair isn't installed (guards on the fields existing).
    """
    if not _has_fix_repair_flags(env):
        _logger.info(
            'seed_master_data_and_settings: Fix-repair not installed; '
            'skipping stock.location Studio-flag seeding.'
        )
        return

    Wh = env['stock.warehouse'].sudo()
    flagged = 0
    for wh_code, flags in _WAREHOUSE_ROLES.items():
        matched = Wh.search([('code', '=', wh_code)])
        for wh in matched:
            loc = wh.lot_stock_id
            if not loc:
                continue
            vals = {k: v for k, v in flags.items()
                    if hasattr(loc, k) and not loc[k]}
            if vals:
                loc.write(vals)
                flagged += 1
    _logger.info(
        'seed_master_data_and_settings: flagged %d warehouse Stock '
        'location(s) with Studio repair roles.',
        flagged,
    )


def seed_factory_repair_config_param(env):
    """Point fix_repair.factory_repair_location.<company_id> at
    PW-JM/Stock for company 2 (Jinasena Agricultural Machinery).

    Fix-repair has its own _seed_factory_repair_locations() that
    checks company.name — but here we control the exact linkage so
    it lands regardless of the check's name-match behaviour.
    Idempotent: skips when the param is already set.
    """
    if not _has_fix_repair_flags(env):
        return
    company_ref = env.ref(
        'seed_master_data_and_settings.company_jinasena_agricultural_machinery',
        raise_if_not_found=False,
    )
    if not company_ref:
        return
    # Look up PW-JM by (code, company_id) rather than by xmlid — the
    # warehouse xmlid embeds the CLEAR-DB source company id (e.g.
    # `warehouse_pw_jm_c2`), not the target env's dev-assigned company
    # id (which may be 7 on standalone). Search is authoritative and
    # avoids the source/target id mismatch.
    pw_jm = env['stock.warehouse'].sudo().search([
        ('code', '=', 'PW-JM'),
        ('company_id', '=', company_ref.id),
    ], limit=1)
    if not pw_jm or not pw_jm.lot_stock_id:
        return
    Param = env['ir.config_parameter'].sudo()
    key = f'fix_repair.factory_repair_location.{company_ref.id}'
    if Param.get_param(key):
        return
    Param.set_param(key, str(pw_jm.lot_stock_id.id))
    _logger.info(
        'seed_master_data_and_settings: set %s = %s',
        key, pw_jm.lot_stock_id.id,
    )


def grant_admins_access_to_seeded_companies(env):
    """Add the 3 seeded Jinasena companies to every pre-existing
    internal user's company_ids m2m.

    Without this, admins on the target env (Mitchell Admin etc.)
    can't see the new companies in the company switcher and can't
    switch to them to view their warehouses / users / data — the
    companies exist in the DB but are effectively invisible.

    Idempotent: uses the (4, id) m2m op which is a no-op when the
    id is already in the set.

    Only touches users that were NOT seeded by this module — the
    seeded users had their company_ids set correctly by the XML
    data file.
    """
    IMD = env['ir.model.data'].sudo()
    company_xmlids = [
        'seed_master_data_and_settings.company_jinasena_pvt_ltd',
        'seed_master_data_and_settings.company_jinasena_agricultural_machinery',
        'seed_master_data_and_settings.company_jltd',
    ]
    seeded_company_ids = [
        env.ref(x, raise_if_not_found=False).id
        for x in company_xmlids
    ]
    seeded_company_ids = [c for c in seeded_company_ids if c]
    if not seeded_company_ids:
        return

    seeded_user_ids = IMD.search([
        ('module', '=', 'seed_master_data_and_settings'),
        ('model', '=', 'res.users'),
    ]).mapped('res_id')

    other_admins = env['res.users'].sudo().search([
        ('share', '=', False),
        ('active', '=', True),
        ('id', 'not in', seeded_user_ids),
    ])
    for user in other_admins:
        user.write({
            'company_ids': [(4, cid) for cid in seeded_company_ids],
        })
    _logger.info(
        'seed_master_data_and_settings: granted %d pre-existing '
        'internal user(s) access to %d seeded company(ies).',
        len(other_admins), len(seeded_company_ids),
    )


def replicate_warehouses_to_all_companies(env):
    """Ensure every distinct Clear-DB warehouse code exists on every
    active company.

    Reads data/warehouse_codes.json (bundled) — 45 distinct codes with
    canonical name/sequence/step-config templates. For each active
    company on the target env, creates any missing (code, company_id)
    warehouse. Existing warehouses (any (code, company_id) already
    present) are skipped — idempotent.

    Result on a fresh dev env: 45 codes × 8 companies (3 Jinasena +
    5 Odoo demo) = 360 warehouses. Any repair-flow ticket can be
    routed through BR-* / PW-* / RP-* / etc. regardless of which
    company the ticket lives on.

    Warehouse.create() side-effects (sub-locations, picking types,
    routes) fire per record — this hook can take ~30-60s on a fresh
    install. Log every 20 to signal progress.
    """
    import json as _json
    payload_path = os.path.join(
        os.path.dirname(__file__), 'data', 'warehouse_codes.json',
    )
    if not os.path.exists(payload_path):
        _logger.warning(
            'seed_master_data_and_settings: warehouse_codes.json missing; '
            'skipping cross-company warehouse replication.'
        )
        return
    with open(payload_path, encoding='utf-8') as f:
        templates = _json.load(f)

    Wh = env['stock.warehouse'].sudo()
    companies = env['res.company'].sudo().search([])
    created = 0
    skipped = 0
    for company in companies:
        for tpl in templates:
            existing = Wh.search([
                ('code', '=', tpl['code']),
                ('company_id', '=', company.id),
            ], limit=1)
            if existing:
                skipped += 1
                continue
            vals = {
                'name': tpl['name'],
                'code': tpl['code'],
                'company_id': company.id,
                'sequence': tpl.get('sequence', 10),
            }
            for step in ('reception_steps', 'delivery_steps',
                         'manufacture_steps'):
                if step in tpl:
                    vals[step] = tpl[step]
            try:
                Wh.create(vals)
                created += 1
                if created % 20 == 0:
                    _logger.info(
                        'seed_master_data_and_settings: created %d '
                        'warehouse(s) so far...', created,
                    )
            except Exception as e:
                # Odoo can refuse warehouse creation on companies with
                # certain module states (e.g. no country + no default
                # sequence). Log and continue — better to seed what we
                # can than abort the whole loop.
                _logger.warning(
                    'seed_master_data_and_settings: failed to create '
                    'warehouse %s on company %s: %s',
                    tpl['code'], company.name, e,
                )
    _logger.info(
        'seed_master_data_and_settings: warehouse replication done — '
        'created %d, skipped %d (already present).',
        created, skipped,
    )


def post_init_hook(env):
    seed_user_passwords(env)
    grant_admins_access_to_seeded_companies(env)
    replicate_warehouses_to_all_companies(env)
    seed_studio_location_flags(env)
    seed_factory_repair_config_param(env)
