# seed_master_data_and_settings

Standalone Odoo 17 module that seeds a fresh dev / staging / restore
env with the same master-data layout as Clear-DB production:

- **3 companies** — Jinasena (Pvt) Ltd., Jinasena Agricultural
  Machinery (Pvt) Ltd., JLTD
- **34 active users** with a shared temp password (`ChangeMe2026!`)
  — must be rotated on any production import
- **63 warehouses** across the 3 companies (branches, production,
  repair, intransit)
- **Optional Studio flags** on the auto-created warehouse Stock
  locations (`repair_return_location`,
  `repair_factory_location`, etc.) — applied only when
  Fix-repair is installed on the target env (guarded in
  `post_init_hook`)
- **Optional Fix-repair config param** —
  `fix_repair.factory_repair_location.<jam_company_id>` pointed at
  PW-JM/Stock — same guard

## Design notes

- Additive: existing companies, warehouses and users on the target
  DB are untouched.
- All records use stable xmlids (`seed_master_data_and_settings.*`)
  so upgrades are safe.
- Warehouse creation triggers Odoo's built-in auto-provisioning
  (view/Stock/Input/Output/... sub-locations + picking types +
  routes), so the XML records only carry the seedable fields
  (name, code, company, sequence, step config).
- Studio flags are applied post-install via a hook — they read
  Fix-repair's stock.location declarations and no-op if not
  installed.

## How to regenerate the seed data

The data XML files under `data/` are generated from JSON snapshots
pulled from Clear-DB via RPC. To refresh:

1. Pull fresh JSON dumps from Clear-DB (companies, users, warehouses,
   locations) into a working directory.
2. Run the generator:
   ```
   python scripts/generate_seed_data.py \
       --input-dir "<path to json dumps>" \
       --output-dir data
   ```
3. Commit the regenerated XML.

## Passwords

The plaintext temp password (`SEED_TEMP_PASSWORD` in `hooks.py`)
must never survive a production restore. Rotate the file's
constant to a fresh random value before shipping, or replace the
whole seed-passwords hook with an email-invitation flow.

<!-- BEGIN rename-studio-names -->
## Naming

On 2026-11-11 (branch `Rename-All`) the Studio names in the Jinasena modules were replaced (Studio prefix `x_studio_` / `x_` removed, the repo name as prefix where a name was taken; `x_active` -> `active`). This seeding module only had its references to those names updated; it was not refactored otherwise. The database is renamed by the Jinasena modules' own upgrade scripts.
<!-- END rename-studio-names -->
