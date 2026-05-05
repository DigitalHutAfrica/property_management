# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _


class PropertyMaintenance(models.Model):
    _inherit = 'maintenance.request'

    property_id = fields.Many2one('property.details', string='Property')
    actual_cost = fields.Monetary(
        string='Actual Cost',
        currency_field='currency_id',
        help="Actual cost incurred for this maintenance request."
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency',
                                  related='company_id.currency_id',
                                  string='Currency')
    landlord_id = fields.Many2one('res.partner', string='Landlord',
                                  domain=[('is_landlord', '=', True)])
    maintenance_type_id = fields.Many2one('product.template', string='Type',
                                          domain=[
                                              ('is_maintenance', '=', True)])
    price = fields.Float(related='maintenance_type_id.list_price',
                         string='Price')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    invoice_state = fields.Boolean(string='State')
    contract_id = fields.Many2one('tenancy.details', string='Contract',
                                  domain="[('property_id', '=', property_id)]")
    tenant_id = fields.Many2one('res.partner', string='Tenant',
                                domain="[('is_customer', '=', True)]")

    attachment_ids = fields.One2many('maintenance.photos',
                                     'maintenance_request_id', string='Images')
    parent_property_id = fields.Many2one('parent.property', 'Parent Property')
    request_description = fields.Text('Description ')

    @api.model_create_multi
    def create(self, vals_list):
        res = super(PropertyMaintenance, self).create(vals_list)
        for rec in res:
            if rec.property_id and not rec.user_id:
                maintenance_incharge_id = rec.property_id.parent_property_id.maintenance_incharge_id.id
                responsible_id = self.env['res.users'].sudo().search(
                    [('partner_id', '=', maintenance_incharge_id)],
                    limit=1).id
                rec.user_id = responsible_id
        return res

    @api.onchange('contract_id')
    def _onchange_contract(self):
        self.tenant_id = self.contract_id.tenancy_id.id

    @api.onchange('property_id')
    def _onchange_property(self):
        self.landlord_id = self.property_id.landlord_id.id
        self.parent_property_id = self.property_id.parent_property_id.id
        maintenance_incharge_id = self.property_id.parent_property_id.maintenance_incharge_id.id
        if maintenance_incharge_id:
            responsible_id = self.env['res.users'].sudo().search(
                [('partner_id', '=', maintenance_incharge_id)],
                limit=1).id
            self.user_id = responsible_id
        else:
            self.user_id = False

    def action_send_notification_mail(self, id):
        mail_template = self.env.ref(
            'property_management.maintenance_request_notification_mail_template').sudo()
        if mail_template:
            mail_template.send_mail(id, force_send=True)

    def action_crete_invoice(self):
        full_payment_record = {
            'product_id': self.maintenance_type_id.product_variant_id.id,
            'name': 'Maintenance',
            'quantity': 1,
            'price_unit': self.price
        }
        invoice_lines = [(0, 0, full_payment_record)]
        data = {
            'partner_id': self.landlord_id.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': invoice_lines
        }
        invoice_id = self.env['account.move'].sudo().create(data)
        invoice_id.action_post()
        self.invoice_id = invoice_id.id
        self.invoice_state = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'account.move',
            'res_id': invoice_id.id,
            'view_mode': 'form',
            'target': 'current'
        }


class MaintenancePhotos(models.Model):
    _name = 'maintenance.photos'
    _description = 'Photos For Maintenance Request'
    _order = 'id desc'

    image = fields.Binary(string='Image')
    maintenance_request_id = fields.Many2one('maintenance.request')


class MaintenanceProduct(models.Model):
    _inherit = 'product.template'

    is_maintenance = fields.Boolean(string='Maintenance')
    property_id = fields.Many2one('property.details', string="Property")


class PropertyDetailsMaintCost(models.Model):
    """Add maintenance cost visibility to individual property units."""
    _inherit = 'property.details'

    maintenance_cost_total = fields.Monetary(
        string='Total Maintenance Cost',
        compute='_compute_maintenance_cost',
        currency_field='currency_id',
        store=True,
    )
    maintenance_request_count = fields.Integer(
        compute='_compute_maintenance_cost',
        string='Maintenance Requests',
        store=True,
    )

    @api.depends('maintenance_ids.actual_cost', 'maintenance_ids.stage_id')
    def _compute_maintenance_cost(self):
        for rec in self:
            requests = self.env['maintenance.request'].search(
                [('property_id', '=', rec.id)])
            rec.maintenance_request_count = len(requests)
            rec.maintenance_cost_total = sum(
                r.actual_cost or 0 for r in requests)

    def action_maintenance_request(self):
        """Open maintenance requests for this property unit."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Maintenance Requests',
            'res_model': 'maintenance.request',
            'domain': [('property_id', '=', self.id)],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {'default_property_id': self.id},
        }


class ParentPropertyMaintCost(models.Model):
    """Roll up maintenance costs to main property / building level."""
    _inherit = 'parent.property'

    maintenance_cost_total = fields.Float(
        string='Total Maintenance Cost',
        compute='_compute_maintenance_cost',
        digits=(16, 2),
        store=False,
        help="Sum of all maintenance costs across all units in this building."
    )
    maintenance_open_count = fields.Integer(
        compute='_compute_maintenance_cost',
        string='Open Maintenance Requests',
    )
    maintenance_all_count = fields.Integer(
        compute='_compute_maintenance_cost',
        string='All Maintenance Requests',
    )

    def _compute_maintenance_cost(self):
        for rec in self:
            # Get all property units under this building
            unit_ids = self.env['property.details'].search(
                [('parent_property_id', '=', rec.id)]).ids

            all_requests = self.env['maintenance.request'].search(
                [('property_id', 'in', unit_ids)])
            open_requests = all_requests.filtered(
                lambda m: m.stage_id.name and
                'done' not in m.stage_id.name.lower() and
                'complet' not in m.stage_id.name.lower())

            rec.maintenance_cost_total = sum(r.actual_cost or 0 for r in all_requests)
            rec.maintenance_open_count = len(open_requests)
            rec.maintenance_all_count = len(all_requests)


class ParentPropertyMaintAction(models.Model):
    _inherit = 'parent.property'

    def action_parent_maintenance(self):
        unit_ids = self.env['property.details'].search(
            [('parent_property_id', '=', self.id)]).ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Maintenance Requests',
            'res_model': 'maintenance.request',
            'domain': [('property_id', 'in', unit_ids)],
            'view_mode': 'list,form',
            'target': 'current',
        }
