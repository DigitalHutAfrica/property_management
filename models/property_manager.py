# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ParentPropertyManager(models.Model):
    """Extend parent.property to support dedicated property managers."""
    _inherit = 'parent.property'

    property_manager_id = fields.Many2one(
        'res.users', string='Property Manager',
        domain=[('share', '=', False)],
        help="Internal user responsible for managing this building and all its units."
    )
    manager_partner_id = fields.Many2one(
        related='property_manager_id.partner_id',
        string='Manager Contact', store=True
    )


class PropertyDetailsManager(models.Model):
    """Inherit property.details to surface the parent building's manager."""
    _inherit = 'property.details'

    property_manager_id = fields.Many2one(
        related='parent_property_id.property_manager_id',
        string='Property Manager', store=True, readonly=True
    )


class TenancyDetailsManager(models.Model):
    """Surface property manager on contracts."""
    _inherit = 'tenancy.details'

    property_manager_id = fields.Many2one(
        related='property_id.property_manager_id',
        string='Property Manager', store=True, readonly=True
    )


class RentInvoiceManager(models.Model):
    """Surface property manager on rent invoices."""
    _inherit = 'rent.invoice'

    property_manager_id = fields.Many2one(
        related='tenancy_id.property_manager_id',
        string='Property Manager', store=True, readonly=True
    )


class UtilityBillManager(models.Model):
    """Surface property manager on utility bills."""
    _inherit = 'utility.bill'

    property_manager_id = fields.Many2one(
        related='property_id.property_manager_id',
        string='Property Manager', store=True, readonly=True
    )


class HandoverPropertyManager(models.Model):
    """Surface property manager on handover records."""
    _inherit = 'handover.property'

    property_manager_id = fields.Many2one(
        related='property_id.property_manager_id',
        string='Property Manager', store=True, readonly=True
    )
