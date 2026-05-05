# -*- coding: utf-8 -*-
"""
Rent Pass-Through & Service Charge Separation
=============================================
Business model: GIMCOAFRICA acts as an AGENT for landlords.
- Rent goes directly to the landlord (often via GePG control number).
- GIMCO only accounts for its SERVICE CHARGE as revenue.
- Rent is tracked for reporting but flows through a SUSPENSE/PASSTHROUGH account,
  NOT through GIMCO's income accounts.

Vendor Utility Bills:
- Utility provider (TANESCO, DAWASCO) sends bill to GIMCO.
- GIMCO pays vendor → creates vendor bill in Odoo.
- GIMCO then bills the tenant via the utility.bill model.
- The two are linked so finance can reconcile.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TenancyPassThrough(models.Model):
    """Extend tenancy to support agent/pass-through accounting model."""
    _inherit = 'tenancy.details'

    # ── Payment flow configuration ─────────────────────────────────────────
    rent_payment_flow = fields.Selection([
        ('through_gimco',   'Collected by us (normal)'),
        ('direct_landlord', 'Direct to landlord — we only charge service fee'),
        ('gepg_control',    'GePG / Government Control Number'),
    ], string='Rent Payment Flow', default='through_gimco', required=False,
        help="How rent is collected.\n"
             "Direct to landlord: Tenant pays landlord directly. We invoice our service charge only.\n"
             "GePG: Government payment gateway — control number issued, payment goes to landlord's account.")

    gepg_control_number = fields.Char(
        string='GePG Control Number',
        help="Government e-Payment Gateway control number for this tenancy."
    )
    gepg_sp_code = fields.Char(
        string='SP Code',
        help="Service Provider code for GePG payment."
    )

    # ── Service charge details ─────────────────────────────────────────────
    service_charge_type = fields.Selection([
        ('fixed',      'Fixed Amount'),
        ('percentage', 'Percentage of Rent'),
    ], string='Service Charge Type', default='fixed')

    service_charge_percentage = fields.Float(
        string='Service Charge %',
        digits=(5, 2),
        help="Percentage of rent charged as management fee."
    )

    # ── Pass-through tracking ──────────────────────────────────────────────
    passthrough_rent_ytd = fields.Monetary(
        string='Rent Tracked YTD (Pass-through)',
        compute='_compute_passthrough_ytd',
        help="Total rent amount tracked this year (reported to landlord, not GIMCO revenue)."
    )
    service_charge_ytd = fields.Monetary(
        string='Service Charge Collected YTD',
        compute='_compute_passthrough_ytd',
    )

    @api.depends('rent_invoice_ids.amount', 'rent_invoice_ids.payment_state',
                 'rent_invoice_ids.service_amount')
    def _compute_passthrough_ytd(self):
        import datetime
        year_start = datetime.date(datetime.date.today().year, 1, 1)
        for rec in self:
            invoices = rec.rent_invoice_ids.filtered(
                lambda i: i.invoice_date and i.invoice_date >= year_start
            )
            rec.passthrough_rent_ytd = sum(invoices.mapped('rent_amount'))
            rec.service_charge_ytd = sum(
                i.service_amount for i in invoices if i.payment_state == 'paid'
            )

    @api.onchange('service_charge_type', 'service_charge_percentage', 'tenancy_price')
    def _onchange_service_charge(self):
        if self.service_charge_type == 'percentage' and self.tenancy_price:
            self.service_charge_month = self.tenancy_price * (self.service_charge_percentage / 100)


class RentInvoicePassThrough(models.Model):
    """Extend rent.invoice to support the agent accounting model."""
    _inherit = 'rent.invoice'

    # ── Pass-through flag (computed Boolean from selection) ───────────────
    is_direct_to_landlord = fields.Boolean(
        string='Direct to Landlord',
        compute='_compute_is_direct',
        store=True,
    )

    @api.depends('tenancy_id.rent_payment_flow')
    def _compute_is_direct(self):
        for rec in self:
            rec.is_direct_to_landlord = rec.tenancy_id.rent_payment_flow in [
                'direct_landlord', 'gepg_control'
            ]

    gepg_control_number = fields.Char(
        string='GePG Control Number',
        related='tenancy_id.gepg_control_number',
        store=True,
    )

    # ── What GIMCO invoices ────────────────────────────────────────────────
    # For direct-to-landlord: only service_amount is GIMCO's revenue
    # rent_amount is tracked for reporting but goes to landlord
    gimco_receivable = fields.Monetary(
        string="GIMCO Receivable",
        compute='_compute_gimco_receivable',
        store=True,
        help="The amount GIMCO will actually collect (service charge only if direct payment)."
    )

    @api.depends('amount', 'service_amount', 'is_direct_to_landlord')
    def _compute_gimco_receivable(self):
        for rec in self:
            if rec.is_direct_to_landlord:
                rec.gimco_receivable = rec.service_amount or 0.0
            else:
                rec.gimco_receivable = rec.amount

    # ── Landlord disbursement tracking ─────────────────────────────────────
    landlord_disbursed = fields.Boolean(
        string='Disbursed to Landlord',
        default=False,
        tracking=True,
    )
    landlord_disbursement_date = fields.Date(
        string='Disbursement Date',
        tracking=True,
    )
    landlord_disbursement_ref = fields.Char(
        string='Disbursement Reference',
    )

    def action_mark_disbursed(self):
        for rec in self:
            rec.write({
                'landlord_disbursed': True,
                'landlord_disbursement_date': fields.Date.today(),
            })


class UtilityBillVendor(models.Model):
    """Link utility bills to their vendor (supplier) bills."""
    _inherit = 'utility.bill'

    # ── Utility supplier (from Odoo purchase vendors) ─────────────────────
    utility_supplier_id = fields.Many2one(
        'res.partner',
        string='Utility Supplier',
        domain=[('supplier_rank', '>', 0)],
        help="The company that supplies this utility (e.g. TANESCO, DAWASCO). "
             "Must be a registered supplier in the Contacts/Purchase module.",
        tracking=True,
    )
    utility_service_type = fields.Selection([
        ('electricity', 'Electricity'),
        ('water',       'Water'),
        ('generator',   'Generator'),
        ('internet',    'Internet'),
        ('gas',         'Gas'),
        ('other',       'Other'),
    ], string='Utility Service Type', default='electricity')

    # ── Vendor bill link ───────────────────────────────────────────────────
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        copy=False,
        help="Link to the Purchase Order raised for this utility service (optional). "
             "When set, the vendor bill is automatically pulled from the PO."
    )
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        domain=[('move_type', '=', 'in_invoice')],
        compute='_compute_vendor_bill_id',
        store=True,
        readonly=False,
        copy=False,
        help="The vendor invoice from TANESCO/DAWASCO. "
             "Auto-populated from the linked Purchase Order, or set manually."
    )

    @api.depends('purchase_order_id')
    def _compute_vendor_bill_id(self):
        for rec in self:
            if not rec.purchase_order_id:
                # No PO — keep whatever is manually set
                continue
            # Try account_move_ids (Odoo 18) then invoice_ids (older)
            moves = getattr(rec.purchase_order_id, 'account_move_ids', None) or \
                    getattr(rec.purchase_order_id, 'invoice_ids', None)
            if moves:
                posted = moves.filtered(
                    lambda m: m.move_type == 'in_invoice' and m.state == 'posted'
                )
                rec.vendor_bill_id = posted[:1] if posted else moves[:1]
    vendor_bill_amount = fields.Monetary(
        related='vendor_bill_id.amount_total',
        string='Vendor Bill Amount',
        store=True,
    )
    vendor_bill_state = fields.Selection(
        related='vendor_bill_id.state',
        string='Vendor Bill Status',
        store=True,
    )
    vendor_bill_payment_state = fields.Selection(
        related='vendor_bill_id.payment_state',
        string='Vendor Bill Payment',
        store=True,
    )

    # ── Markup / margin ────────────────────────────────────────────────────
    apply_markup = fields.Boolean(
        string='Apply Markup',
        default=False,
        help="Charge tenant more than the vendor bill (e.g. admin fee)."
    )
    markup_amount = fields.Monetary(string='Markup Amount')
    markup_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percent', 'Percentage'),
    ], default='fixed')
    markup_percent = fields.Float(string='Markup %')

    # ── Net cost to GIMCO ──────────────────────────────────────────────────
    net_cost_to_gimco = fields.Monetary(
        string='Net Cost to GIMCO',
        compute='_compute_net_cost',
        store=True,
        help="Vendor bill amount minus what tenant pays — GIMCO's margin."
    )

    @api.depends('vendor_bill_amount', 'total_amount')
    def _compute_net_cost(self):
        for rec in self:
            rec.net_cost_to_gimco = (rec.total_amount or 0) - (rec.vendor_bill_amount or 0)

    def action_open_purchase_order(self):
        """Open the linked Purchase Order."""
        if not self.purchase_order_id:
            raise UserError(_("No Purchase Order linked to this utility bill."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
        }

    def action_create_vendor_bill(self):
        """Create a vendor bill pre-filled with the utility supplier."""
        return {
            'name': _('Create Vendor Bill'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_move_type': 'in_invoice',
                'default_partner_id': self.utility_supplier_id.id or False,
                'default_invoice_origin': self.bill_seq,
                'default_ref': self.bill_seq,
                'default_narration': f'Utility bill: {self.bill_seq} | Property: {self.property_id.name or ""} | Tenant: {self.tenant_name.name or ""}',
            }
        }

    def action_create_purchase_order(self):
        """Create a Purchase Order pre-filled with the utility supplier."""
        return {
            'name': _('Create Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.utility_supplier_id.id or False,
                'default_origin': self.bill_seq,
            }
        }

    def action_open_vendor_bill(self):
        if not self.vendor_bill_id:
            raise UserError(_("No vendor bill linked to this utility bill."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.vendor_bill_id.id,
            'view_mode': 'form',
        }
