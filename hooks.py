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
            # Savepoint: catch failures at the SQL layer so a bad
            # create() doesn't poison the outer transaction. Without
            # this the next Wh.search() throws InFailedSqlTransaction
            # ("current transaction is aborted, commands ignored").
            try:
                with env.cr.savepoint():
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
                # sequence). Savepoint rolled back — log and continue.
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


# Clear-DB → seed-module company id/name → target xmlid.
# Used by apply_user_data() to translate a snapshot's Clear-DB
# x_studio_company_id[0] (Clear-DB res.company id) to the target env's
# res.company via seed xmlid.
_CLEAR_DB_COMPANY_TO_XMLID = {
    1: 'seed_master_data_and_settings.company_jinasena_pvt_ltd',
    2: 'seed_master_data_and_settings.company_jinasena_agricultural_machinery',
    3: 'seed_master_data_and_settings.company_jltd',
}


def apply_user_data(env):
    """Apply per-user data (signature, image, groups, Studio fields)
    from the bundled Clear-DB snapshot.

    Reads data/user_data.json (RPC dump of every active @jinasena user
    on Clear-DB) and writes the values onto the seeded users, matched
    by login. Every write wrapped in env.cr.savepoint() so one bad
    user doesn't poison the outer transaction.

    Skips users whose login isn't present on the target env — they
    weren't seeded, so there's nothing to migrate.

    Groups: 100% of the snapshotted groups resolved to xmlids on
    Clear-DB (base + module groups); env.ref lookups on the target
    env re-resolve them. Any that fail (e.g. custom Studio groups)
    are logged as WARNING and skipped.

    Locations: resolved by complete_name (e.g. 'Virtual Locations/
    Repair/Ekala'). Since those Studio-created virtual repair locs
    aren't currently seeded on the target env, most location writes
    will log "not found" — that's expected and fine; add virtual
    location seeding in a future chunk if needed.

    Password: NOT migrated — Odoo's ORM shields res.users.password
    from RPC reads, so no hash is available in the snapshot. Users
    keep the temp password from seed_user_passwords().

    Idempotent: every write is an unconditional overwrite so re-runs
    just re-apply the snapshot state.
    """
    import base64 as _b64
    import json as _json
    payload_path = os.path.join(
        os.path.dirname(__file__), 'data', 'user_data.json',
    )
    if not os.path.exists(payload_path):
        _logger.warning(
            'seed_master_data_and_settings: user_data.json missing; '
            'skipping per-user data seed.'
        )
        return
    with open(payload_path, encoding='utf-8') as f:
        snapshot = _json.load(f)

    users_snap = snapshot['users']
    group_id_to_xmlid = snapshot.get('groupIdToXmlid', {})
    loc_id_meta = snapshot.get('locIdMeta', {})
    stage_id_to_name = snapshot.get('stageIdToName', {})

    Users = env['res.users'].sudo()
    Group = env['res.groups'].sudo()
    Loc = env['stock.location'].sudo()
    Stage = env['hr.recruitment.stage'].sudo()

    # Pre-resolve target-env references we'll reuse across users.
    # Groups: xmlid → target group id.
    group_target_ids = {}
    for src_id, xmlid in group_id_to_xmlid.items():
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            group_target_ids[int(src_id)] = rec.id
    _logger.info(
        'seed_master_data_and_settings: resolved %d/%d snapshot group '
        'xmlids on target env.',
        len(group_target_ids), len(group_id_to_xmlid),
    )

    # Locations: complete_name → target loc id. Multiple companies
    # may have the same complete_name (e.g. "WH/Stock") — keep the
    # first match; the location write later re-searches per-company
    # if a preferred company id is provided.
    loc_target_ids_by_name = {}
    for src_id, meta in loc_id_meta.items():
        cn = meta.get('complete_name')
        if not cn:
            continue
        # Loose match: prefer active + first hit.
        target = Loc.search([('complete_name', '=', cn)], limit=1)
        if target:
            loc_target_ids_by_name[cn] = target.id

    # Recruitment stages: name → target id.
    stage_target_ids = {}
    for src_id, name in stage_id_to_name.items():
        rec = Stage.search([('name', '=', name)], limit=1)
        if rec:
            stage_target_ids[int(src_id)] = rec.id

    def _resolve_loc(loc_ref):
        """Given a snapshot m2o loc ref [id, display] or int id,
        return target env loc id or False."""
        if not loc_ref:
            return False
        src_id = loc_ref[0] if isinstance(loc_ref, list) else loc_ref
        meta = loc_id_meta.get(str(src_id))
        if not meta:
            return False
        return loc_target_ids_by_name.get(meta.get('complete_name'))

    updated = 0
    skipped_missing_login = 0
    for u in users_snap:
        login = u['login']
        with env.cr.savepoint():
            target = Users.search([('login', '=', login)], limit=1)
            if not target:
                skipped_missing_login += 1
                continue
            vals = {}
            # Profile-visible fields
            if u.get('signature'):
                vals['signature'] = u['signature']
            if u.get('image_1920'):
                # Stored as base64 string in the snapshot; Odoo accepts
                # the raw base64 for binary fields on write.
                vals['image_1920'] = u['image_1920']
            # Studio company_id — translate Clear-DB co id → seed xmlid
            src_company = u.get('x_studio_company_id')
            if src_company:
                src_cid = src_company[0]
                xmlid = _CLEAR_DB_COMPANY_TO_XMLID.get(src_cid)
                if xmlid:
                    rec = env.ref(xmlid, raise_if_not_found=False)
                    if rec and hasattr(target, 'x_studio_company_id'):
                        vals['x_studio_company_id'] = rec.id
            # Studio boolean flags
            for bfield in ('x_studio_attendance_administrator',
                           'x_studio_super_user_melt_items'):
                if bfield in u and hasattr(target, bfield):
                    vals[bfield] = bool(u[bfield])
            # Fix-repair user-side locations (single m2o)
            for lfield in ('x_studio_source_location',
                           'x_studio_source_location_1',
                           'x_studio_virtual_location',
                           'x_studio_virtual_location_1'):
                lid = _resolve_loc(u.get(lfield))
                if lid and hasattr(target, lfield):
                    vals[lfield] = lid
            # Studio m2m stock.location — resolve list of ids
            for m2m_field in ('x_studio_many2many_field_Q50dg',
                              'x_studio_many2many_field_bQRSA'):
                src_ids = u.get(m2m_field) or []
                target_ids = [
                    loc_target_ids_by_name.get(
                        (loc_id_meta.get(str(sid)) or {}).get('complete_name')
                    )
                    for sid in src_ids
                ]
                target_ids = [tid for tid in target_ids if tid]
                if target_ids and hasattr(target, m2m_field):
                    vals[m2m_field] = [(6, 0, target_ids)]
            # Recruitment stages
            src_stages = u.get('x_studio_recr_stages') or []
            stage_ids = [stage_target_ids.get(sid) for sid in src_stages]
            stage_ids = [s for s in stage_ids if s]
            if stage_ids and hasattr(target, 'x_studio_recr_stages'):
                vals['x_studio_recr_stages'] = [(6, 0, stage_ids)]
            # groups_id — full replace with resolved target ids
            src_groups = u.get('groups_id') or []
            resolved_groups = [
                group_target_ids.get(g) for g in src_groups
            ]
            resolved_groups = [g for g in resolved_groups if g]
            if resolved_groups:
                vals['groups_id'] = [(6, 0, resolved_groups)]

            if vals:
                target.write(vals)
                updated += 1

    _logger.info(
        'seed_master_data_and_settings: applied user data to %d user(s); '
        'skipped %d (login not found on target env).',
        updated, skipped_missing_login,
    )


def seed_portal_signature_only(env):
    """Match Clear-DB's portal-confirmation setup: signature required,
    payment NOT required. Applied at two layers:

      1. res.company.portal_confirmation_pay = False on every company
         (default for future SOs created via UI / API).
      2. Every existing sale.order with require_payment=True gets set
         to False so tickets already in the pipeline stop asking for
         payment on the portal preview.

    Clear-DB always used signature-only confirmation for Repair (and
    all other) SOs — verified via RPC 2026-08-13 (all sampled repair
    SOs had require_payment=False, res.company.portal_confirmation_pay
    was False on the JAM company).

    Idempotent: only writes when the current value differs.
    """
    Company = env['res.company'].sudo()
    changed_cos = 0
    # These fields live on res.company only when specific Odoo variants
    # / addons are installed. Guard on hasattr so envs where the
    # setting is exposed via ir.config_parameter (or res.config.settings
    # relations to a different model) don't crash the migration.
    for company in Company.search([]):
        if hasattr(company, 'portal_confirmation_pay') and company.portal_confirmation_pay:
            company.portal_confirmation_pay = False
            changed_cos += 1
        if hasattr(company, 'portal_confirmation_sign') and not company.portal_confirmation_sign:
            company.portal_confirmation_sign = True
            changed_cos += 1
    # Also set the ir.config_parameter defaults that some Odoo versions
    # use in place of / alongside the res.company fields.
    Param = env['ir.config_parameter'].sudo()
    Param.set_param('sale.default_require_payment', 'False')
    Param.set_param('sale.default_require_signature', 'True')
    # Existing SOs — batch clear require_payment. Guarded: this module
    # doesn't depend on `sale`, so on installs without sale the model
    # is absent from the registry and env['sale.order'] would raise
    # KeyError.
    stale_count = 0
    if 'sale.order' in env:
        SO = env['sale.order'].sudo()
        try:
            stale = SO.search([('require_payment', '=', True)])
            if stale:
                stale.write({'require_payment': False})
                stale_count = len(stale)
        except (KeyError, ValueError) as e:
            _logger.warning(
                'seed_master_data_and_settings: could not clear '
                'require_payment on existing SOs: %s', e,
            )
    _logger.info(
        'seed_master_data_and_settings: portal signature-only applied. '
        'Companies touched: %d. Existing SOs with require_payment '
        'cleared: %d.',
        changed_cos, stale_count,
    )


def post_init_hook(env):
    seed_user_passwords(env)
    grant_admins_access_to_seeded_companies(env)
    replicate_warehouses_to_all_companies(env)
    seed_studio_location_flags(env)
    seed_factory_repair_config_param(env)
    seed_portal_signature_only(env)
    apply_user_data(env)
