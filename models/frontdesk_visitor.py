# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class RentalFrontDeskVisitor(models.Model):
    """ Inherit Frontdesk Visitor Model """
    _inherit = 'frontdesk.visitor'

    property_id = fields.Many2one('property.details')
    tenant_id = fields.Many2one('res.partner')