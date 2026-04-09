import math
from dateutil.relativedelta import relativedelta
from datetime import date, timedelta, datetime
from odoo import fields, api, models
from odoo.exceptions import ValidationError


class ActiveContract(models.Model):
    _name = "active.contract"
    _description = "Active Contract"
    _rec_name = "type"

    type = fields.Selection(
        [
            ("manual", "List out all rent installment"),
        ],
        default="manual",
    )

    # ("automatic", "Auto create rent installment + Invoice"),
    def action_create_contract(self):
        active_id = self._context.get("active_id")
        tenancy_id = self.env["tenancy.details"].browse(active_id)
        if self.type == "automatic":
            tenancy_id.write(
                {
                    "type": "automatic",
                    "contract_type": "running_contract",
                    "active_contract_state": True,
                }
            )
            tenancy_id.action_active_contract()
            if tenancy_id.contract_type_name == 'lease':
                tenancy_id.property_id.write({
                    "stage": "on_lease"
                })
        if self.type == "manual":
            if tenancy_id.payment_term_id.rent_unit == "Month":
                self.action_monthly_month_active()
            if tenancy_id.payment_term_id.rent_unit == "Quarter":
                self.action_quarterly_month_active()
            if tenancy_id.payment_term_id.rent_unit == "Year":
                self.action_yearly_year()
            if tenancy_id.is_any_broker:
                tenancy_id.action_broker_invoice()
            tenancy_id.write(
                {
                    "type": "manual",
                    "contract_type": "running_contract",
                    "active_contract_state": True,
                }
            )
            if tenancy_id.contract_type_name == 'lease':
                tenancy_id.property_id.write({
                    "stage": "on_lease"
                })

    def action_monthly_month_active(self):
        final_val = 0
        date_diff = 0
        service = 0.0
        active_id = self._context.get("active_id")
        tenancy_id = self.env["tenancy.details"].browse(active_id)
        invoice_lines = []
        if not tenancy_id.start_date < tenancy_id.end_date:
            raise ValidationError("Make valid Start and End date!")
        if tenancy_id.start_date < tenancy_id.end_date:
            date_diff = relativedelta(
                tenancy_id.end_date + timedelta(days=1), tenancy_id.start_date
            )

        total_months = date_diff.years * 12 + date_diff.months
        days = date_diff.days
        if days > 0:
            total_months = abs(total_months) + 1
        else:
            total_months = abs(total_months)

        if tenancy_id.payment_term_id.rent_unit == "Month":
            vals = total_months / tenancy_id.payment_term_id.month

            if vals % 1 == 0:
                final_val = vals
            else:
                final_val = math.ceil(vals)
        total_rent_month = tenancy_id.total_rent
        if tenancy_id.property_type == "commercial" and tenancy_id.contract_type_name == 'lease':
            total_rent_month = tenancy_id.total_rent_month
        if tenancy_id.property_type in ["residential", "commercial"] and tenancy_id.contract_type_name == "service":
            total_rent_month = tenancy_id.service_charge_month

        unit = tenancy_id.payment_term_id.month
        invoice_date = tenancy_id.start_date + relativedelta(months=unit)

        count = int(final_val)

        for i in range(int(final_val)):
            if i == 0:
                record = {
                    "product_id": tenancy_id.installment_item_id.id,
                    "name": "First Invoice of " + tenancy_id.property_id.name,
                    "quantity": tenancy_id.payment_term_id.month,
                    "price_unit": total_rent_month,
                    'tax_ids': tenancy_id.installment_item_id.taxes_id,
                }
                if tenancy_id.contract_type_name == 'lease' and tenancy_id.contract_includes == 'rent_and_service':
                    record['price_unit'] = total_rent_month + tenancy_id.service_charge_per_month

                invoice_lines.append((0, 0, record))
                if tenancy_id.is_any_deposit:
                    deposit_record = {
                        "product_id": tenancy_id.installment_item_id.id,
                        "name": "Deposit of " + tenancy_id.property_id.name,
                        "quantity": tenancy_id.payment_term_id.month,
                        "price_unit": tenancy_id.deposit_amount,
                        'tax_ids': tenancy_id.installment_item_id.taxes_id,
                    }
                    invoice_lines.append((0, 0, deposit_record))

                data = {
                    "partner_id": tenancy_id.tenancy_id.id,
                    "move_type": "out_invoice",
                    "invoice_date": tenancy_id.start_date,
                    "invoice_line_ids": invoice_lines,
                    "currency_id": tenancy_id.currency_id.id,
                }
                invoice_id = self.env["account.move"].sudo().create(data)
                invoice_id.tenancy_id = tenancy_id.id
                invoice_id.tenancy_property_id = tenancy_id.property_id.id
                invoice_id.tenancy_parent_property_id = tenancy_id.property_id.parent_property_id.id
                invoice_id.invoice_period_to_date = tenancy_id.start_date
                invoice_id.invoice_period_from_date = (
                                                              tenancy_id.start_date + relativedelta(months=unit)
                                                      ) - relativedelta(days=1)
                invoice_id.action_post()
                amount_total = invoice_id.amount_total

                rent_invoice = {
                    "tenancy_id": tenancy_id.id,
                    "type": "rent",
                    "invoice_date": tenancy_id.start_date,
                    "description": "First Rent",
                    "rent_invoice_id": invoice_id.id,
                    "amount": total_rent_month * tenancy_id.payment_term_id.month,
                    "rent_amount": total_rent_month * tenancy_id.payment_term_id.month,
                    "rent_month": total_rent_month,
                    "service_amount": service,
                    "invoice_period_to_date": tenancy_id.start_date,
                    "invoice_period_from_date": (tenancy_id.start_date + relativedelta(months=unit)) - relativedelta(
                        days=1),
                    "company_id": tenancy_id.company_id.id,
                    "currency_id": tenancy_id.currency_id.id,
                }
                if tenancy_id.contract_type_name == 'lease' and tenancy_id.contract_includes == 'rent_and_service':
                    rent_invoice['rent_month'] = total_rent_month + tenancy_id.service_charge_per_month
                    rent_invoice['amount'] = (
                                                     total_rent_month + tenancy_id.service_charge_per_month) * tenancy_id.payment_term_id.month
                    rent_invoice['rent_amount'] = (
                                                          total_rent_month + tenancy_id.service_charge_per_month) * tenancy_id.payment_term_id.month

                if tenancy_id.is_any_deposit:
                    rent_invoice["description"] = "First Rent + Deposit"
                else:
                    rent_invoice["description"] = "First Rent"

                self.env["rent.invoice"].create(rent_invoice)

            if not i == 0:
                rent_invoice = {
                    "tenancy_id": tenancy_id.id,
                    "type": "rent",
                    "invoice_date": invoice_date,
                    "rent_month": total_rent_month,
                    "description": "Installment of " + tenancy_id.property_id.name,
                    "amount": total_rent_month * tenancy_id.payment_term_id.month,
                    "rent_amount": total_rent_month * tenancy_id.payment_term_id.month,
                    "invoice_period_to_date": invoice_date,
                    "invoice_period_from_date": (invoice_date + relativedelta(months=unit)) - relativedelta(
                        days=1),
                    "company_id": tenancy_id.company_id.id,
                    "currency_id": tenancy_id.currency_id.id,

                }
                if tenancy_id.contract_type_name == 'lease' and tenancy_id.contract_includes == 'rent_and_service':
                    rent_invoice['rent_month'] = total_rent_month + tenancy_id.service_charge_per_month
                    rent_invoice['amount'] = (
                                                     total_rent_month + tenancy_id.service_charge_per_month) * tenancy_id.payment_term_id.month
                    rent_invoice['rent_amount'] = (
                                                          total_rent_month + tenancy_id.service_charge_per_month) * tenancy_id.payment_term_id.month

                if i == (count - 1):
                    contract_end_date = tenancy_id.end_date
                    invoice_start_date = rent_invoice.get("invoice_date")

                    diff = relativedelta(contract_end_date + timedelta(days=1), invoice_start_date)
                    total_months = (diff.years * 12) + diff.months
                    total_months = abs(total_months)
                    rent_invoice["last_rent_line"] = True
                    rent_invoice["rent_month"] = total_rent_month
                    rent_invoice["amount"] = total_rent_month * total_months
                    rent_invoice["invoice_period_to_date"] = invoice_start_date
                    rent_invoice["invoice_period_from_date"] = contract_end_date
                    rent_invoice["company_id"] = tenancy_id.company_id.id
                    rent_invoice['currency_id'] = tenancy_id.currency_id.id

                    if tenancy_id.contract_type_name == 'lease' and tenancy_id.contract_includes == 'rent_and_service':
                        rent_invoice['rent_month'] = total_rent_month + tenancy_id.service_charge_per_month
                        rent_invoice['amount'] = (total_rent_month + tenancy_id.service_charge_per_month) * total_months

                self.env["rent.invoice"].create(rent_invoice)

                invoice_date = invoice_date + relativedelta(months=unit)

    def action_quarterly_month_active(self):
        service_amount = 0.0
        active_id = self._context.get("active_id")
        tenancy_id = self.env["tenancy.details"].browse(active_id)
        invoice_lines = []

        if tenancy_id.start_date < tenancy_id.end_date:
            date_diff = relativedelta(tenancy_id.end_date, tenancy_id.start_date)
        else:
            date_diff = relativedelta(tenancy_id.start_date, tenancy_id.end_date)

        total_months = date_diff.years * 12 + date_diff.months

        days = date_diff.days

        if days > 0:
            total_months = abs(total_months) + 1
        else:
            total_months = abs(total_months)

        if tenancy_id.payment_term_id.rent_unit == "Quarter":
            vals = total_months / (tenancy_id.payment_term_id.month * 3)

            if vals % 1 == 0:
                final_val = int(vals)

            else:
                final_val = math.ceil(vals)

        unit = tenancy_id.payment_term_id.month
        invoice_date = tenancy_id.start_date + relativedelta(months=unit * 3)

        if tenancy_id.property_type == "commercial":
            total_rent_month = tenancy_id.total_rent_month
        elif (
                tenancy_id.property_type in ["residential", "commercial"]
                and tenancy_id.contract_type_name == "service"
        ):
            total_rent_month = tenancy_id.service_charge_month
        else:
            total_rent_month = tenancy_id.total_rent

        count = final_val

        for i in range(final_val):
            if i == 0:
                record = {
                    "product_id": tenancy_id.installment_item_id.id,
                    "name": "First Quarter Invoice of " + tenancy_id.property_id.name,
                    "quantity": tenancy_id.payment_term_id.month * 3,
                    "price_unit": total_rent_month,
                    'tax_ids': tenancy_id.installment_item_id.taxes_id,
                }
                invoice_lines.append((0, 0, record))
                if tenancy_id.is_any_deposit:
                    deposit_record = {
                        "product_id": tenancy_id.installment_item_id.id,
                        "name": "Deposit of " + tenancy_id.property_id.name,
                        "quantity": tenancy_id.payment_term_id.month * 3,
                        "price_unit": tenancy_id.deposit_amount,
                        'tax_ids': tenancy_id.installment_item_id.taxes_id,
                    }
                    invoice_lines.append((0, 0, deposit_record))

                data = {
                    "partner_id": tenancy_id.tenancy_id.id,
                    "move_type": "out_invoice",
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": invoice_lines,
                    "currency_id": tenancy_id.currency_id.id,
                }
                invoice_id = self.env["account.move"].sudo().create(data)
                invoice_id.tenancy_id = tenancy_id.id
                invoice_id.tenancy_property_id = tenancy_id.property_id.id
                invoice_id.tenancy_parent_property_id = tenancy_id.property_id.parent_property_id.id
                invoice_id.invoice_period_to_date = tenancy_id.start_date
                invoice_id.invoice_period_from_date = (
                                                              tenancy_id.start_date + relativedelta(months=unit * 3)
                                                      ) - relativedelta(days=1)
                invoice_id.action_post()

                rent_invoice = {
                    "tenancy_id": tenancy_id.id,
                    "type": "rent",
                    "invoice_date": tenancy_id.start_date,
                    "description": "First Quarter Rent",
                    "rent_invoice_id": invoice_id.id,
                    "amount": total_rent_month * (tenancy_id.payment_term_id.month * 3),
                    "rent_amount": total_rent_month * (tenancy_id.payment_term_id.month * 3),
                    "service_amount": service_amount,
                    "company_id": tenancy_id.company_id.id,
                    "currency_id": tenancy_id.currency_id.id,
                }
                if tenancy_id.is_any_deposit:
                    rent_invoice["description"] = "First Quarter Rent + Deposit"
                else:
                    rent_invoice["description"] = "First Quarter Rent"
                self.env["rent.invoice"].create(rent_invoice)

            if not i == 0:
                rent_invoice = {
                    "tenancy_id": tenancy_id.id,
                    "type": "rent",
                    "invoice_date": invoice_date,
                    "description": "Installment of " + tenancy_id.property_id.name,
                    "amount": total_rent_month * (tenancy_id.payment_term_id.month * 3),
                    "rent_amount": total_rent_month * (tenancy_id.payment_term_id.month * 3),
                    "company_id": tenancy_id.company_id.id,
                    "currency_id": tenancy_id.currency_id.id,
                }

                if i == (count - 1):
                    rent_invoice["last_rent_line"] = True
                    rent_invoice["amount"] = total_rent_month * (tenancy_id.payment_term_id.month * 3)

                self.env["rent.invoice"].create(rent_invoice)

                invoice_date = invoice_date + relativedelta(months=unit * 3)

    def action_yearly_year(self):
        service_amount = 0
        active_id = self._context.get("active_id")
        tenancy_id = self.env["tenancy.details"].browse(active_id)
        invoice_lines = []

        if tenancy_id.start_date < tenancy_id.end_date:
            date_diff = relativedelta(tenancy_id.end_date, tenancy_id.start_date)
        else:
            date_diff = relativedelta(tenancy_id.start_date, tenancy_id.end_date)

        year = date_diff.years
        months = date_diff.months
        days = date_diff.days

        if tenancy_id.payment_term_id.rent_unit == "Year":
            if months > 0 or days > 0:
                year = year + 1

        if tenancy_id.property_type == "commercial":
            total_rent_month = tenancy_id.total_rent_month
        elif (
                tenancy_id.property_type in ["residential", "commercial"]
                and tenancy_id.contract_type_name == "service"
        ):
            total_rent_month = tenancy_id.service_charge_month
        else:
            total_rent_month = tenancy_id.total_rent

        unit = tenancy_id.payment_term_id.month
        invoice_date = tenancy_id.start_date + relativedelta(years=unit)

        count = year

        for i in range(year):
            if i == 0:
                record = {
                    "product_id": tenancy_id.installment_item_id.id,
                    "name": "First Year Invoice of " + tenancy_id.property_id.name,
                    "quantity": tenancy_id.payment_term_id.month * 12,
                    "price_unit": total_rent_month,
                    'tax_ids': tenancy_id.installment_item_id.taxes_id,
                }
                invoice_lines.append((0, 0, record))
                if tenancy_id.is_any_deposit:
                    deposit_record = {
                        "product_id": tenancy_id.installment_item_id.id,
                        "name": "Deposit of " + tenancy_id.property_id.name,
                        "quantity": tenancy_id.payment_term_id.month,
                        "price_unit": tenancy_id.deposit_amount,
                        'tax_ids': tenancy_id.installment_item_id.taxes_id,
                    }
                    invoice_lines.append((0, 0, deposit_record))

                data = {
                    "partner_id": tenancy_id.tenancy_id.id,
                    "move_type": "out_invoice",
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": invoice_lines,
                    "currency_id": tenancy_id.currency_id.id,
                }
                invoice_id = self.env["account.move"].sudo().create(data)
                invoice_id.tenancy_id = tenancy_id.id
                invoice_id.tenancy_property_id = tenancy_id.property_id.id
                invoice_id.tenancy_parent_property_id = tenancy_id.property_id.parent_property_id.id
                invoice_id.invoice_period_to_date = tenancy_id.start_date
                invoice_id.invoice_period_from_date = tenancy_id.start_date + (
                    relativedelta(years=unit)) - relativedelta(days=1)
                invoice_id.action_post()

                rent_invoice = {
                    "tenancy_id": tenancy_id.id,
                    "type": "rent",
                    "invoice_date": tenancy_id.start_date,
                    "description": "First Rent",
                    "rent_invoice_id": invoice_id.id,
                    "amount": total_rent_month
                              * (tenancy_id.payment_term_id.month * 12),
                    "rent_amount": total_rent_month
                                   * (tenancy_id.payment_term_id.month * 12),
                    "service_amount": service_amount,
                    "company_id": tenancy_id.company_id.id

                }
                if tenancy_id.is_any_deposit:
                    rent_invoice["description"] = "First Rent + Deposit"
                else:
                    rent_invoice["description"] = "First Rent"
                self.env["rent.invoice"].create(rent_invoice)

            if not i == 0:
                rent_invoice = {
                    "tenancy_id": tenancy_id.id,
                    "type": "rent",
                    "invoice_date": invoice_date,
                    "description": "Installment of " + tenancy_id.property_id.name,
                    "amount": total_rent_month * (tenancy_id.payment_term_id.month * 12),
                    "rent_amount": total_rent_month * (tenancy_id.payment_term_id.month * 12),
                    "company_id": tenancy_id.company_id.id
                }

                if i == (count - 1):
                    rent_invoice["last_rent_line"] = True
                    rent_invoice["amount"] = total_rent_month * (tenancy_id.payment_term_id.month * 12)

                self.env["rent.invoice"].create(rent_invoice)

                invoice_date = invoice_date + relativedelta(years=unit)
