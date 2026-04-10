# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.

import datetime
import calendar
from datetime import timedelta
from odoo import fields, models, api
from dateutil.relativedelta import relativedelta


class PropertyPayment(models.TransientModel):
    _name = "property.payment.wizard"
    _description = "Create Invoice For Rent"

    tenancy_id = fields.Many2one("tenancy.details", string="Tenancy No.")
    customer_id = fields.Many2one(related="tenancy_id.tenancy_id", string="Customer")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        "res.currency", related="tenancy_id.currency_id", string="Currency"
    )
    type = fields.Selection(
        [
            ("deposit", "Deposit"),
            ("maintenance", "Maintenance"),
            ("penalty", "Penalty"),
            ("rent", "Rent"),
        ],
        string="Payment",
        default="rent",
    )
    description = fields.Char(string="Description")
    invoice_date = fields.Date(string="Date")
    rent_amount = fields.Monetary(
        string="Rent Amount", related="tenancy_id.total_rent_month"
    )
    amount = fields.Monetary(string="Amount")
    rent_invoice_id = fields.Many2one("account.move", string="Invoice")
    contract_type_name = fields.Selection(related="tenancy_id.contract_type_name")
    invoice_period_to_date = fields.Date(string="Start Date")
    invoice_period_from_date = fields.Date(string="End Date")
    total_rent_amount = fields.Monetary()
    total_rent_month = fields.Monetary()
    total_rent = fields.Monetary(store=True)
    service_charge_month = fields.Monetary()
    property_type = fields.Selection(related="tenancy_id.property_type")

    def property_payment_action(self):
        if self.type == "rent":
            if self.tenancy_id.property_type == "commercial" and self.tenancy_id.contract_type_name == "lease":
                amount = self.tenancy_id.total_rent_month
            elif (
                    self.tenancy_id.property_type in ["residential", "commercial"]
                    and self.tenancy_id.contract_type_name == "service"
            ):
                amount = self.tenancy_id.service_charge_month
            else:
                amount = self.tenancy_id.total_rent
        else:
            amount = self.amount
        unit = self.get_total_months(end_date=self.invoice_period_from_date, start_date=self.invoice_period_to_date)
        record = {
            "product_id": self.tenancy_id.installment_item_id.id,
            "name": self.description,
            "quantity": unit,
            "price_unit": amount,
            'tax_ids': False,
        }
        invoice_lines = [(0, 0, record)]
        data = {
            "partner_id": self.customer_id.id,
            "move_type": "out_invoice",
            "invoice_date": self.invoice_date,
            "invoice_line_ids": invoice_lines,
            "currency_id": self.tenancy_id.currency_id.id,
        }
        invoice_id = self.env["account.move"].sudo().create(data)
        invoice_id.tenancy_id = self.tenancy_id.id
        invoice_id.tenancy_property_id = self.tenancy_id.property_id.id
        invoice_id.tenancy_parent_property_id = self.tenancy_id.property_id.parent_property_id.id
        invoice_id.invoice_period_to_date = self.invoice_period_to_date
        invoice_id.invoice_period_from_date = self.invoice_period_from_date
        invoice_id.action_post()
        self.rent_invoice_id = invoice_id.id

        rent_month = self.total_rent
        if self.contract_type_name == 'lease' and self.property_type == 'commercial':
            rent_month = self.total_rent_month
        if self.contract_type_name == 'service' and self.property_type in ['commercial', 'residential']:
            rent_month = self.service_charge_month

        rent_invoice = {
            "tenancy_id": self.tenancy_id.id,
            "type": self.type,
            "invoice_date": self.invoice_date,
            "rent_amount": self.rent_amount,
            "amount": self.total_rent_amount,
            'rent_month': rent_month,
            "description": self.description,
            "rent_invoice_id": self.rent_invoice_id.id,
            "invoice_period_to_date": self.invoice_period_to_date,
            "invoice_period_from_date": self.invoice_period_from_date,
            "company_id": self.tenancy_id.company_id.id
        }
        self.env["rent.invoice"].create(rent_invoice)

        return True

    @api.onchange("tenancy_id")
    def _onchange_tenancy_id(self):
        self.invoice_period_to_date = self.tenancy_id.start_date
        self.invoice_period_from_date = self.tenancy_id.end_date
        self.total_rent_month = self.tenancy_id.total_rent_month
        self.total_rent = self.tenancy_id.total_rent
        self.service_charge_month = self.tenancy_id.service_charge_month

    @api.onchange("invoice_period_to_date", "invoice_period_from_date", "total_rent", "service_charge_month",
                  "total_rent_month")
    def _onchange_dates(self):
        if self.invoice_period_from_date and self.invoice_period_to_date:
            total_months = self.get_total_months(end_date=self.invoice_period_from_date,
                                                 start_date=self.invoice_period_to_date)
            if self.tenancy_id.property_type == "commercial":
                self.total_rent_amount = total_months * self.tenancy_id.total_rent_month
            elif (
                    self.tenancy_id.property_type in ["residential", "commercial"]
                    and self.tenancy_id.contract_type_name == "service"
            ):
                self.total_rent_amount = total_months * self.tenancy_id.service_charge_month
            else:
                self.total_rent_amount = total_months * self.tenancy_id.total_rent

    def get_total_months(self, end_date, start_date):
        delta = relativedelta(end_date + timedelta(days=1), start_date)
        total_months = (delta.years * 12) + delta.months
        total_months = abs(total_months)
        return total_months
