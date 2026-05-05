# -*- coding: utf-8 -*-
"""
Rent vs Service Charge Accounting Split
========================================
Business model:
  - Tenant pays one invoice covering BOTH rent and GIMCO's service charge
  - Rent (USD/sqm × area) → posts to Rent Payable to Landlord (liability)
  - Service charge (USD/sqm × area) → posts to Management Fee Income (GIMCO revenue)
  - On disbursement, one journal entry clears the liability → bank

All amounts are derived automatically from the contract:
  rent_amount    = contract.total_rent          (rent_smtr × rented_area)
  service_amount = contract.service_charge_month (service_charge_smtr × rented_area)

No manual input required on the invoice.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResCompanySplit(models.Model):
    """Company-level defaults for the accounting split."""
    _inherit = 'res.company'

    rent_suspense_account_id = fields.Many2one(
        'account.account',
        string='Rent Payable to Landlord Account',
        help="Liability account where rent collected on behalf of landlords is posted. "
             "Cleared when disbursement is made to the landlord.",
        domain=[('account_type', 'like', 'liability')]
    )
    service_charge_product_id = fields.Many2one(
        'product.product',
        string='Management Fee Product',
        domain=[('type', '=', 'service')],
        help="Product used for GIMCO's management fee invoice line. "
             "The income account on this product = GIMCO's Management Fee Revenue account."
    )


class ResConfigSettingsSplit(models.TransientModel):
    _inherit = 'res.config.settings'

    rent_suspense_account_id = fields.Many2one(
        related='company_id.rent_suspense_account_id',
        string='Rent Payable to Landlord Account',
        readonly=False,
    )
    service_charge_product_id = fields.Many2one(
        related='company_id.service_charge_product_id',
        string='Management Fee Product',
        readonly=False,
    )


class TenancyAccountingSplit(models.Model):
    """
    Per-contract overrides for the accounting split.
    Falls back to company defaults if not set.
    """
    _inherit = 'tenancy.details'

    service_charge_product_id = fields.Many2one(
        'product.product',
        string='Service Charge Product',
        domain=[('type', '=', 'service')],
        help="Override the company default management fee product for this contract."
    )
    rent_suspense_account_id = fields.Many2one(
        'account.account',
        string='Rent Suspense Account',
        help="Override the company default rent payable account for this contract."
    )

    def _get_split_config(self):
        """
        Return (suspense_account, service_product) for this contract.
        Contract-level fields take priority over company defaults.
        """
        company = self.env.company
        suspense = self.rent_suspense_account_id or company.rent_suspense_account_id
        product  = self.service_charge_product_id or company.service_charge_product_id
        return suspense, product

    def _get_rent_and_service(self):
        """
        Derive rent and service charge amounts directly from contract fields.

        rent_amount    = total_rent  (= rent_smtr × rented_area, already computed)
        service_amount = service_charge_month (= service_charge_smtr × rented_area)
                         OR service_charge_per_month
                         OR percentage of total_rent if service_charge_type = percentage
        """
        rent = self.total_rent or 0.0

        # Service charge — try each field in priority order
        if self.service_charge_type == 'percentage' and self.service_charge_percentage:
            svc = rent * (self.service_charge_percentage / 100.0)
        elif self.service_charge_smtr and self.rented_area:
            svc = self.service_charge_smtr * self.rented_area
        elif self.service_charge_per_month:
            svc = self.service_charge_per_month
        elif self.service_charge_month:
            svc = self.service_charge_month
        else:
            svc = 0.0

        return rent, svc


class RentInvoiceAccountingSplit(models.Model):
    """
    Override invoice creation to split rent vs service charge
    into separate lines with separate accounting accounts.
    """
    _inherit = 'rent.invoice'

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
    landlord_disbursement_move_id = fields.Many2one(
        'account.move',
        string='Disbursement Journal Entry',
        readonly=True,
        copy=False,
    )
    gimco_receivable = fields.Monetary(
        string='GIMCO Receivable',
        compute='_compute_gimco_receivable',
        store=True,
        help="Amount GIMCO retains — service charge only for pass-through contracts."
    )
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

    @api.depends('amount', 'service_amount', 'is_direct_to_landlord')
    def _compute_gimco_receivable(self):
        for rec in self:
            if rec.is_direct_to_landlord:
                rec.gimco_receivable = rec.service_amount or 0.0
            else:
                rec.gimco_receivable = rec.amount

    def action_create_invoice(self):
        """
        Override: for pass-through contracts, split invoice into
        rent line (liability) + service charge line (income).
        For normal contracts, call super() as usual.
        """
        for rec in self:
            if rec.rent_invoice_id:
                continue

            tenancy = rec.tenancy_id

            # Only split for pass-through payment flows
            is_passthrough = tenancy.rent_payment_flow in [
                'direct_landlord', 'gepg_control'
            ]

            if not is_passthrough:
                super(RentInvoiceAccountingSplit, rec).action_create_invoice()
                continue

            # ── Get accounts and product ──────────────────────────────────
            suspense_account, svc_product = tenancy._get_split_config()

            if not svc_product:
                raise UserError(_(
                    "No Management Fee Product configured.\n\n"
                    "Please go to:\n"
                    "Property Management → Configuration → Settings\n"
                    "and set the 'Management Fee Product'."
                ))
            if not suspense_account:
                raise UserError(_(
                    "No Rent Payable to Landlord account configured.\n\n"
                    "Please go to:\n"
                    "Property Management → Configuration → Settings\n"
                    "and set the 'Rent Payable to Landlord Account'."
                ))

            # ── Get amounts from contract ─────────────────────────────────
            rent_amt, svc_amt = tenancy._get_rent_and_service()

            if rent_amt <= 0:
                raise UserError(_(
                    "Contract '%s' has no rent amount. "
                    "Please set Rent/sqm and Rented Area on the contract."
                ) % tenancy.name)

            months = rec.months or 1

            # ── Build invoice lines ───────────────────────────────────────

            # Line 1: Rent — liability account (not GIMCO income)
            rent_line = {
                'product_id':  tenancy.installment_item_id.id if tenancy.installment_item_id else False,
                'name':        _('Rent — %s (%s sqm × %s USD/sqm)') % (
                                    rec.description or tenancy.name,
                                    tenancy.rented_area,
                                    tenancy.rent_smtr,
                               ),
                'quantity':    months,
                'price_unit':  rent_amt,
                'account_id':  suspense_account.id,
            }

            # Line 2: Service charge — GIMCO income account
            svc_line = {
                'product_id':  svc_product.id,
                'name':        _('Management Fee — %s (%s sqm × %s USD/sqm)') % (
                                    rec.description or tenancy.name,
                                    tenancy.rented_area,
                                    tenancy.service_charge_smtr or (svc_amt / tenancy.rented_area if tenancy.rented_area else 0),
                               ),
                'quantity':    months,
                'price_unit':  svc_amt,
                'tax_ids':     [(6, 0, svc_product.taxes_id.ids)],
            }

            invoice_vals = {
                'partner_id':                    rec.customer_id.id,
                'move_type':                     'out_invoice',
                'invoice_date':                  rec.invoice_date,
                'invoice_period_to_date':         rec.invoice_period_to_date,
                'invoice_period_from_date':       rec.invoice_period_from_date,
                'tenancy_id':                    tenancy.id,
                'invoice_line_ids':              [(0, 0, rent_line), (0, 0, svc_line)],
                'currency_id':                   tenancy.currency_id.id,
                'tenancy_property_id':           tenancy.property_id.id,
                'tenancy_parent_property_id':    tenancy.property_id.parent_property_id.id,
                'narration': _(
                    'Payment Flow: %(flow)s\n'
                    'Rented Area: %(area)s sqm\n'
                    'Rent Rate: %(rent_rate)s USD/sqm → %(rent_amt)s (Landlord)\n'
                    'Service Rate: %(svc_rate)s USD/sqm → %(svc_amt)s (GIMCO)\n'
                    'GePG Control No: %(gepg)s'
                ) % {
                    'flow':      dict(tenancy._fields['rent_payment_flow'].selection).get(
                                     tenancy.rent_payment_flow, ''),
                    'area':      tenancy.rented_area,
                    'rent_rate': tenancy.rent_smtr,
                    'rent_amt':  f'{rent_amt:,.2f}',
                    'svc_rate':  tenancy.service_charge_smtr or 0,
                    'svc_amt':   f'{svc_amt:,.2f}',
                    'gepg':      tenancy.gepg_control_number or 'N/A',
                },
            }

            invoice = self.env['account.move'].create(invoice_vals)
            invoice.action_post()
            rec.rent_invoice_id = invoice.id
            rec.rent_amount     = rent_amt * months
            rec.service_amount  = svc_amt  * months

            _logger.info(
                "Split invoice created for contract %s: "
                "Rent=%s (→ suspense), Service=%s (→ GIMCO income)",
                tenancy.name, rent_amt, svc_amt
            )

    def action_disburse_to_landlord(self):
        """
        Post a journal entry to disburse rent to the landlord:
          Debit:  Rent Payable to Landlord  (clears liability)
          Credit: Bank / Cash               (money leaves)
        """
        for rec in self:
            if rec.landlord_disbursed:
                raise UserError(_("This invoice has already been disbursed."))

            tenancy = rec.tenancy_id
            suspense_account, _ = tenancy._get_split_config()

            if not suspense_account:
                raise UserError(_(
                    "No Rent Payable to Landlord account configured. "
                    "Check Property Management → Configuration → Settings."
                ))

            company      = self.env.company
            journal      = self.env['account.journal'].search(
                [('type', 'in', ['bank', 'cash']), ('company_id', '=', company.id)],
                limit=1
            )
            if not journal:
                raise UserError(_("No bank or cash journal found."))

            rent_amt = rec.rent_amount or 0.0
            if rent_amt <= 0:
                raise UserError(_("No rent amount to disburse."))

            landlord = tenancy.property_landlord_id
            move_vals = {
                'journal_id':  journal.id,
                'date':        fields.Date.today(),
                'ref':         _('Landlord Disbursement — %s') % rec.description or tenancy.name,
                'line_ids': [
                    # Debit suspense (clears liability)
                    (0, 0, {
                        'account_id':  suspense_account.id,
                        'partner_id':  landlord.id if landlord else False,
                        'name':        _('Landlord disbursement — %s') % tenancy.name,
                        'debit':       rent_amt,
                        'credit':      0.0,
                    }),
                    # Credit bank (money goes out)
                    (0, 0, {
                        'account_id':  journal.default_account_id.id,
                        'partner_id':  landlord.id if landlord else False,
                        'name':        _('Landlord disbursement — %s') % tenancy.name,
                        'debit':       0.0,
                        'credit':      rent_amt,
                    }),
                ],
            }

            move = self.env['account.move'].create(move_vals)
            move.action_post()

            rec.write({
                'landlord_disbursed':          True,
                'landlord_disbursement_date':  fields.Date.today(),
                'landlord_disbursement_move_id': move.id,
            })
            _logger.info(
                "Disbursement journal entry %s posted for rent invoice %s — Amount: %s",
                move.name, rec.id, rent_amt
            )

        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   _('Disbursement Posted'),
                'message': _('Journal entry created and posted. Landlord payment recorded.'),
                'type':    'success',
            }
        }
