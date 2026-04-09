import datetime
import base64
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager
from odoo import http
from odoo.http import request


class TenantMaintenanceUtility(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        rtn = super(TenantMaintenanceUtility,
                    self)._prepare_home_portal_values(counters)
        rtn['utility_bills_count'] = request.env['utility.bill'].search_count(
            [('tenant_name', '=', request.env.user.partner_id.id),
             ('state', '=', 'posted')])
        return rtn

    @http.route(["/onchange-tenant"], type="json", website=True, auth="user")
    def onchange_contract_tenant(self, **kw):
        if kw.get('data', False):
            temp_id = int(kw.get('data'))
            contract_id = request.env['tenancy.details'].sudo().search(
                [('id', '=', temp_id)])
            tenant_id = contract_id.tenancy_id
            return {
                'tenant_id': tenant_id.id,
                'name': tenant_id.name,
            }

    # Utility Bills
    @http.route(["/my/utility_bills", "/my/utility_bills/page/<int:page>"],
                type="http", website=True,
                auth="user")
    def utility_bill_list(self, page=1, **kwargs):
        total_utility_bills = request.env["utility.bill"].search_count(
            [('tenant_name', '=', request.env.user.partner_id.id),
             ('state', '=', 'posted')])
        page_details = pager(url="/my/utility_bills",
                             total=total_utility_bills, page=page, step=10)
        utility_bills = request.env["utility.bill"].search(
            [('tenant_name', '=', request.env.user.partner_id.id),
             ('state', '=', 'posted')],
            limit=15,
            offset=page_details['offset'])
        paid_amount = 0
        unpaid_amount = 0
        for rec in utility_bills:
            if not rec.payment_id:
                unpaid_amount += rec.total_amount
            if rec.payment_id:
                paid_amount += rec.payment_id.amount
                unpaid_amount += rec.total_amount - rec.payment_id.amount
        currency_symbol = request.env.company.currency_id.symbol
        vals = {
            "utility_bills": utility_bills,
            "page_name": 'utility_bills_list_view',
            "pager": page_details,
            'unpaid_amount': unpaid_amount,
            'paid_amount': paid_amount,
            'currency': currency_symbol,

        }
        return request.render("rental_management.utility_bills_list_template",
                              vals)

    @http.route("/my/utility_bill_details/<model('utility.bill'):bill_id>",
                website=True, auth="user",
                type="http")
    def utility_bill_details(self, bill_id):
        prev_url = None
        next_url = None
        utility_bills = request.env['utility.bill'].search(
            [('tenant_name', '=', request.env.user.partner_id.id),
             ('state', '=', 'posted')])
        bill_ids = utility_bills.ids
        bill_index = bill_ids.index(bill_id.id)
        if bill_index != 0 and bill_ids[bill_index - 1]:
            prev_url = f"/my/utility_bill_details/{bill_ids[bill_index - 1]}"
        if bill_index < len(bill_ids) - 1 and bill_ids[bill_index + 1]:
            next_url = f"/my/utility_bill_details/{bill_ids[bill_index + 1]}"
        return request.render(
            "rental_management.utility_bill_form_view_portal", {
                "bill": bill_id,
                "page_name": 'utility_bill_form_view_portal',
                "prev_record": prev_url,
                "next_record": next_url,
            })
