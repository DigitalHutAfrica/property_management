# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class PropertyInquiry(models.Model):
    _inherit = 'crm.lead'

    property_id = fields.Many2one('property.details', string='Property',
                                  domain="['|',('stage','=','available'),('stage','=','sale')]")
    sale_lease = fields.Selection(related='property_id.sale_lease')
    booking_id = fields.Many2one("property.vendor", string="Booking")
    tenancy_inquiry_id = fields.Many2one('tenancy.inquiry', string="Tenancy Inquiry")
    sale_inquiry_id = fields.Many2one('sale.inquiry', string="Sale Inquiry")
