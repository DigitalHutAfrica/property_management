# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


class Handoverproperty(models.Model):
    _name = 'handover.property'
    _description = 'Information Related To Property'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'handover_seq'

    # property details
    handover_seq = fields.Char(string='Sequence', required=True, readonly=True, copy=False,
                               default=lambda self: ('New'))
    name = fields.Char(string="Name")
    date = fields.Date(string="Date")
    property_id = fields.Many2one('property.details', string="Property")
    main_property_id = fields.Many2one('parent.property', string="Main Property")
    tenant_id = fields.Many2one('res.partner', string="Tenant")
    electric_reading = fields.Float(string="Electric Reading")
    generator_reading = fields.Float(string="Generator Reading")
    inspection_report = fields.Text(string="Inspection Report")
    contract_id = fields.Many2one('tenancy.details', string="Contract")

    # handover details fields
    no_of_key = fields.Text(string="No. of Keys Handover")
    barrier_card = fields.Selection([('Yes', 'Yes'), ('No', 'No')], string="Barrier Card")
    barrier_card_no = fields.Char(string="Barrier Card No.")
    access_card = fields.Selection([('Yes', 'Yes'), ('No', 'No')], string="Access Card")
    access_card_no = fields.Char(string="Access Card No.")
    file_name = fields.Char(string='File Name')
    signed_form = fields.Binary(string="Signed Handover Form")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # property assets fields
    assets_ids = fields.One2many('property.assets', 'handover_property_id')

    def print_handover_detials(self):
        return self.env.ref('rental_management.handover_property_report_action').report_action(self)

    # Sequence Create
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('handover_seq', 'New') == 'New':
                vals['handover_seq'] = self.env['ir.sequence'].next_by_code(
                    'handover.property') or 'New'
            if vals['electric_reading'] == 0 or vals['generator_reading'] == 0:
                raise ValidationError(
                    "Electric Reading and Generator Reading must be different from zero.")
        res = super(Handoverproperty, self).create(vals_list)
        return res

    def write(self, vals):
        res = super(Handoverproperty, self).write(vals)
        if self.electric_reading == 0 or self.generator_reading == 0:
            raise ValidationError(
                "Electric Reading and Generator Reading must be different from zero.")

        return res
