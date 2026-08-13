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
    pw_jm_ref = env.ref(
        f'seed_master_data_and_settings.warehouse_pw_jm_c{company_ref.id}',
        raise_if_not_found=False,
    )
    if not pw_jm_ref or not pw_jm_ref.lot_stock_id:
        return
    Param = env['ir.config_parameter'].sudo()
    key = f'fix_repair.factory_repair_location.{company_ref.id}'
    if Param.get_param(key):
        return
    Param.set_param(key, str(pw_jm_ref.lot_stock_id.id))
    _logger.info(
        'seed_master_data_and_settings: set %s = %s',
        key, pw_jm_ref.lot_stock_id.id,
    )


def post_init_hook(env):
    seed_user_passwords(env)
    seed_studio_location_flags(env)
    seed_factory_repair_config_param(env)
