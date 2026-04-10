# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PropertyTerminateWizard(models.TransientModel):
    _name = "property.terminate.wizard"
    _description = "Wizard To Terminate Property"

    termination_date = fields.Date(string="Termination Date", default=fields.Date.today())

    def terminate_property(self):
        active_id = self._context.get("active_id", False)
        if not active_id:
            return
        tenancy_id = self.env["tenancy.details"].sudo().browse(active_id)
        tenancy_rec = self.env["tenancy.details"].sudo().search(
            [('property_id', '=', tenancy_id.property_id.id), ('contract_type_name', '=', 'lease'),
             ('contract_type', '=', 'running_contract'),
             ('id', '!=', tenancy_id.id)])
        tenancy_id.end_date = self.termination_date
        tenancy_id.close_contract_state = True
        tenancy_id.contract_type = 'close_contract'
        if not tenancy_rec and tenancy_id.property_id.sale_lease == 'for_tenancy':
            tenancy_id.property_id.stage = "available"
        for rec in tenancy_id.rent_invoice_ids:
            if rec.invoice_date >= self.termination_date:
                rec.unlink()
