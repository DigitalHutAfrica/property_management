# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager


class LandlordPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        vals = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        if partner.has_landlord_portal:
            vals['landlord_property_count'] = request.env['parent.property'].sudo().search_count(
                [('landlord_id', '=', partner.id)])
        return vals

    @http.route(['/my/landlord', '/my/landlord/page/<int:page>'],
                type='http', auth='user', website=True)
    def landlord_dashboard(self, page=1, **kwargs):
        partner = request.env.user.partner_id
        if not partner.has_landlord_portal:
            return request.redirect('/my')

        domain = [('landlord_id', '=', partner.id)]
        total = request.env['parent.property'].sudo().search_count(domain)
        page_details = pager(url='/my/landlord', total=total, page=page, step=10)
        buildings = request.env['parent.property'].sudo().search(
            domain, limit=10, offset=page_details['offset'])

        # Aggregate stats across all landlord buildings
        property_ids = request.env['property.details'].sudo().search(
            [('landlord_id', '=', partner.id)]).ids

        contracts = request.env['tenancy.details'].sudo().search(
            [('property_landlord_id', '=', partner.id),
             ('contract_type', '=', 'running_contract')])

        invoices = request.env['rent.invoice'].sudo().search(
            [('landlord_id', '=', partner.id)])

        total_collected = sum(
            inv.amount for inv in invoices if inv.payment_state == 'paid')
        total_outstanding = sum(
            inv.amount for inv in invoices if inv.payment_state == 'not_paid')

        maintenance = request.env['maintenance.request'].sudo().search(
            [('property_id', 'in', property_ids)])

        utility_bills = request.env['utility.bill'].sudo().search(
            [('property_id', 'in', property_ids),
             ('state', '=', 'posted')])

        vals = {
            'buildings': buildings,
            'pager': page_details,
            'page_name': 'landlord_dashboard',
            'active_contracts': len(contracts),
            'total_properties': request.env['property.details'].sudo().search_count(
                [('landlord_id', '=', partner.id)]),
            'total_collected': total_collected,
            'total_outstanding': total_outstanding,
            'maintenance_open': len(maintenance.filtered(
                lambda m: m.stage_id.name and 'done' not in m.stage_id.name.lower())),
            'maintenance_done': len(maintenance.filtered(
                lambda m: m.stage_id.name and 'done' in m.stage_id.name.lower())),
            'utility_paid': len(utility_bills.filtered(
                lambda u: u.r_payment_state == 'Paid')),
            'utility_unpaid': len(utility_bills.filtered(
                lambda u: u.r_payment_state == 'Unpaid')),
            'currency': request.env.company.currency_id,
        }
        return request.render('rental_management.landlord_portal_dashboard', vals)

    @http.route('/my/landlord/building/<model("parent.property"):building>',
                type='http', auth='user', website=True)
    def landlord_building_detail(self, building, **kwargs):
        partner = request.env.user.partner_id
        if not partner.has_landlord_portal or building.landlord_id != partner:
            return request.redirect('/my/landlord')

        properties = request.env['property.details'].sudo().search(
            [('parent_property_id', '=', building.id)])
        contracts = request.env['tenancy.details'].sudo().search(
            [('property_id', 'in', properties.ids),
             ('contract_type', '=', 'running_contract')])
        invoices = request.env['rent.invoice'].sudo().search(
            [('property_id', 'in', properties.ids)])
        utilities = request.env['utility.bill'].sudo().search(
            [('property_id', 'in', properties.ids),
             ('state', '=', 'posted')])
        maintenance = request.env['maintenance.request'].sudo().search(
            [('property_id', 'in', properties.ids)])

        handovers = request.env['handover.property'].sudo().search(
            [('property_id', 'in', properties.ids)])
        sold = request.env['property.vendor'].sudo().search(
            [('property_id', 'in', properties.ids)])

        vals = {
            'building': building,
            'properties': properties,
            'contracts': contracts,
            'invoices': invoices,
            'utilities': utilities,
            'maintenance': maintenance,
            'handovers': handovers,
            'sold': sold,
            'currency': request.env.company.currency_id,
            'page_name': 'landlord_building',
        }
        return request.render('rental_management.landlord_building_detail', vals)
