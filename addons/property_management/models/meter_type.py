# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class MeterType(models.Model):
    _name = 'meter.type'
    _description = 'Meter Type'

    name = fields.Char(string="Name")
    _sql_constraints = [('name', 'unique(name)', 'Name Must be unique')]

    def unlink(self):
        for rec in self:
            meter_type_lines_recs = self.env['meter.type.lines'].sudo().search([('meter_type_id', '=', rec.id)],
                                                                               limit=1)
            utility_bill_records = self.env['utility.bill'].sudo().search([('meter_type', '=', rec.id)],
                                                                          limit=1)
            if meter_type_lines_recs or utility_bill_records:
                raise ValidationError(
                    _('You are not allowed to delete this record because it have some related records'))
        return super(MeterType, self).unlink()
