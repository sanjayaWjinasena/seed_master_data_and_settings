# -*- coding: utf-8 -*-
"""Staging_Migration: let repo Python models win over Studio's manual rows.

On a production copy the custom models the repos now define in Python still
have an ir.model row with state='manual' (created by Studio). Odoo's core
ir.model._add_manual_models(), run on every registry setup, rebuilds every
manual model from that row and REPLACES the Python class of the same name:
the repos' extra fields, computes and methods on those models are silently
dropped, and Odoo's reflection keeps writing state='manual' because the class
in the registry is the custom one. Symptom on upgrade-testing-39209462:
"Field 'x_studio_reason' does not exist in model 'x_task_diagnosis'", and all
122 Studio models still manual after BugFix-Stock / -MRP / -Sales / -HR
installed.

The ORM refuses to change ir.model.state, and direct SQL is not allowed, so
this override keeps Odoo's method verbatim and adds one rule: skip a manual
row when a non-custom (Python) class already defines that model. Odoo's own
_reflect_models then records the model as state='base', owned by the repo.
Manual-only models (nothing in Python) are rebuilt exactly as before, and the
Studio manual FIELDS of a repo model are still added by _add_manual_fields.

This module is installed early and depends only on base/stock/hr/mail, so
the override is active before the repos that define these models load.
"""
import logging

from odoo import models, tools

_logger = logging.getLogger(__name__)


class IrModel(models.Model):
    _inherit = 'ir.model'

    def _add_manual_models(self):
        """ Add extra models to the registry. (Odoo 17 core, plus the skip.) """
        # clean up registry first
        for name, Model in list(self.pool.items()):
            if Model._custom:
                del self.pool.models[name]
                # remove the model's name from its parents' _inherit_children
                for Parent in Model.__bases__:
                    if hasattr(Parent, 'pool'):
                        Parent._inherit_children.discard(name)
        # add manual models
        cr = self.env.cr
        # we cannot use self._fields to determine translated fields, as it has not been set up yet
        cr.execute("SELECT *, name->>'en_US' AS name FROM ir_model WHERE state = 'manual'")
        for model_data in cr.dictfetchall():
            # Staging_Migration: a repo already defines this model in Python.
            existing = self.pool.get(model_data['model'])
            if existing is not None and not existing._custom:
                continue
            model_class = self._instanciate(model_data)
            Model = model_class._build_model(self.pool, cr)
            kind = tools.table_kind(cr, Model._table)
            if kind not in (tools.TableKind.Regular, None):
                _logger.info(
                    "Model %r is backed by table %r which is not a regular table (%r), disabling automatic schema management",
                    Model._name, Model._table, kind,
                )
                Model._auto = False
                cr.execute(
                    '''
                    SELECT a.attname
                      FROM pg_attribute a
                      JOIN pg_class t
                        ON a.attrelid = t.oid
                       AND t.relname = %s
                     WHERE a.attnum > 0 -- skip system columns
                    ''',
                    [Model._table]
                )
                columns = {colinfo[0] for colinfo in cr.fetchall()}
                Model._log_access = set(models.LOG_ACCESS_COLUMNS) <= columns
