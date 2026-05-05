# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


def _landlord_partner():
    return request.env.user.partner_id


def _check_landlord(partner):
    if not partner.has_landlord_portal:
        return request.redirect('/my')
    return None


class LandlordPortal(CustomerPortal):

    # ── home portal entry ─────────────────────────────────────────────────

    def _prepare_home_portal_values(self, counters):
        vals = super()._prepare_home_portal_values(counters)
        partner = _landlord_partner()
        if partner.has_landlord_portal:
            vals['landlord_property_count'] = request.env['parent.property'].sudo().search_count(
                [('landlord_id', '=', partner.id)])
        return vals

    # ── helpers ───────────────────────────────────────────────────────────

    def _get_property_ids(self, partner):
        return request.env['property.details'].sudo().search(
            [('landlord_id', '=', partner.id)]).ids

    def _get_invoices(self, partner):
        return request.env['rent.invoice'].sudo().search(
            [('landlord_id', '=', partner.id)])

    def _rent(self, inv):
        return inv.rent_amount or inv.amount

    # ── dashboard ─────────────────────────────────────────────────────────

    @http.route(['/my/landlord'], type='http', auth='user', website=True)
    def landlord_dashboard(self, **kwargs):
        partner = _landlord_partner()
        red = _check_landlord(partner)
        if red: return red

        property_ids = self._get_property_ids(partner)
        buildings = request.env['parent.property'].sudo().search(
            [('landlord_id', '=', partner.id)])
        contracts = request.env['tenancy.details'].sudo().search(
            [('property_landlord_id', '=', partner.id)])
        invoices = self._get_invoices(partner)
        maintenance = request.env['maintenance.request'].sudo().search(
            [('property_id', 'in', property_ids)])

        paid    = invoices.filtered(lambda i: i.payment_state == 'paid')
        unpaid  = invoices.filtered(lambda i: i.payment_state in ['not_paid', 'partial'])

        rent_collected   = sum(self._rent(i) for i in paid)
        rent_outstanding = sum(self._rent(i) for i in unpaid)
        gimco_fees_ytd   = sum(i.service_amount or 0 for i in paid)

        disbursed = invoices.filtered(
            lambda i: hasattr(i, 'landlord_disbursed') and i.landlord_disbursed)
        pending_disbursement = invoices.filtered(
            lambda i: i.payment_state == 'paid' and
            hasattr(i, 'is_direct_to_landlord') and i.is_direct_to_landlord and
            not (hasattr(i, 'landlord_disbursed') and i.landlord_disbursed))

        maint_open = maintenance.filtered(
            lambda m: m.stage_id.name and 'done' not in m.stage_id.name.lower() and
            'complet' not in m.stage_id.name.lower())
        maint_done = maintenance.filtered(
            lambda m: m.stage_id.name and (
                'done' in m.stage_id.name.lower() or 'complet' in m.stage_id.name.lower()))

        utility = request.env['utility.bill'].sudo().search(
            [('property_id', 'in', property_ids), ('state', '=', 'posted')])

        return request.render('property_management.landlord_portal_dashboard', {
            'buildings':                  buildings,
            'total_properties':           len(property_ids),
            'total_buildings':            len(buildings),
            'active_contracts':           len(contracts.filtered(lambda c: c.contract_type == 'running_contract')),
            'total_contracts':            len(contracts),
            'rent_collected':             rent_collected,
            'rent_outstanding':           rent_outstanding,
            'gimco_fees_ytd':             gimco_fees_ytd,
            'disbursed_amount':           sum(self._rent(i) for i in disbursed),
            'pending_disbursement_count': len(pending_disbursement),
            'maintenance_open':           len(maint_open),
            'maintenance_done':           len(maint_done),
            'maintenance_total':          len(maintenance),
            'utility_paid':               len(utility.filtered(lambda u: u.payment_id)),
            'utility_unpaid':             len(utility.filtered(lambda u: not u.payment_id)),
            'currency':                   request.env.company.currency_id,
            'page_name':                  'landlord_dashboard',
        })

    # ── properties list ───────────────────────────────────────────────────

    @http.route(['/my/landlord/properties', '/my/landlord/properties/page/<int:page>'],
                type='http', auth='user', website=True)
    def landlord_properties(self, page=1, **kwargs):
        partner = _landlord_partner()
        red = _check_landlord(partner)
        if red: return red

        domain = [('landlord_id', '=', partner.id)]
        total  = request.env['property.details'].sudo().search_count(domain)
        pager  = portal_pager(url='/my/landlord/properties', total=total, page=page, step=20)
        props  = request.env['property.details'].sudo().search(
            domain, limit=20, offset=pager['offset'], order='name asc')

        return request.render('property_management.landlord_properties_page', {
            'properties': props,
            'pager':      pager,
            'currency':   request.env.company.currency_id,
            'page_name':  'landlord_properties',
        })

    # ── contracts list ────────────────────────────────────────────────────

    @http.route(['/my/landlord/contracts', '/my/landlord/contracts/page/<int:page>'],
                type='http', auth='user', website=True)
    def landlord_contracts(self, page=1, status='all', **kwargs):
        partner = _landlord_partner()
        red = _check_landlord(partner)
        if red: return red

        domain = [('property_landlord_id', '=', partner.id)]
        if status == 'active':
            domain.append(('contract_type', '=', 'running_contract'))
        elif status == 'expired':
            domain.append(('contract_type', '=', 'expire_contract'))

        total    = request.env['tenancy.details'].sudo().search_count(domain)
        pager    = portal_pager(url='/my/landlord/contracts', total=total, page=page, step=20,
                                url_args={'status': status})
        contracts = request.env['tenancy.details'].sudo().search(
            domain, limit=20, offset=pager['offset'], order='start_date desc')

        return request.render('property_management.landlord_contracts_page', {
            'contracts':  contracts,
            'pager':      pager,
            'status':     status,
            'currency':   request.env.company.currency_id,
            'page_name':  'landlord_contracts',
        })

    # ── invoices / rent collected & outstanding ───────────────────────────

    @http.route(['/my/landlord/invoices', '/my/landlord/invoices/page/<int:page>'],
                type='http', auth='user', website=True)
    def landlord_invoices(self, page=1, status='all', **kwargs):
        partner = _landlord_partner()
        red = _check_landlord(partner)
        if red: return red

        domain = [('landlord_id', '=', partner.id)]
        if status == 'collected':
            domain.append(('payment_state', '=', 'paid'))
        elif status == 'outstanding':
            domain.append(('payment_state', 'in', ['not_paid', 'partial']))

        total    = request.env['rent.invoice'].sudo().search_count(domain)
        pager    = portal_pager(url='/my/landlord/invoices', total=total, page=page, step=20,
                                url_args={'status': status})
        invoices = request.env['rent.invoice'].sudo().search(
            domain, limit=20, offset=pager['offset'], order='invoice_date desc')

        all_inv          = self._get_invoices(partner)
        paid             = all_inv.filtered(lambda i: i.payment_state == 'paid')
        unpaid           = all_inv.filtered(lambda i: i.payment_state in ['not_paid', 'partial'])
        total_collected  = sum(self._rent(i) for i in paid)
        total_outstanding= sum(self._rent(i) for i in unpaid)

        return request.render('property_management.landlord_invoices_page', {
            'invoices':          invoices,
            'pager':             pager,
            'status':            status,
            'total_collected':   total_collected,
            'total_outstanding': total_outstanding,
            'currency':          request.env.company.currency_id,
            'page_name':         'landlord_invoices',
        })

    # ── maintenance list ──────────────────────────────────────────────────

    @http.route(['/my/landlord/maintenance', '/my/landlord/maintenance/page/<int:page>'],
                type='http', auth='user', website=True)
    def landlord_maintenance(self, page=1, status='all', **kwargs):
        partner = _landlord_partner()
        red = _check_landlord(partner)
        if red: return red

        property_ids = self._get_property_ids(partner)
        all_maint    = request.env['maintenance.request'].sudo().search(
            [('property_id', 'in', property_ids)])

        if status == 'open':
            filtered = all_maint.filtered(
                lambda m: m.stage_id.name and 'done' not in m.stage_id.name.lower() and
                'complet' not in m.stage_id.name.lower())
        elif status == 'done':
            filtered = all_maint.filtered(
                lambda m: m.stage_id.name and (
                    'done' in m.stage_id.name.lower() or 'complet' in m.stage_id.name.lower()))
        else:
            filtered = all_maint

        total  = len(filtered)
        offset = (page - 1) * 20
        pager  = portal_pager(url='/my/landlord/maintenance', total=total, page=page, step=20,
                              url_args={'status': status})
        items  = filtered[offset:offset + 20]

        return request.render('property_management.landlord_maintenance_page', {
            'maintenance':    items,
            'pager':          pager,
            'status':         status,
            'maint_open':     len(all_maint.filtered(
                lambda m: m.stage_id.name and 'done' not in m.stage_id.name.lower() and
                'complet' not in m.stage_id.name.lower())),
            'maint_done':     len(all_maint.filtered(
                lambda m: m.stage_id.name and (
                    'done' in m.stage_id.name.lower() or 'complet' in m.stage_id.name.lower()))),
            'currency':       request.env.company.currency_id,
            'page_name':      'landlord_maintenance',
        })

    # ── tenants list ──────────────────────────────────────────────────────

    @http.route(['/my/landlord/tenants', '/my/landlord/tenants/page/<int:page>'],
                type='http', auth='user', website=True)
    def landlord_tenants(self, page=1, **kwargs):
        partner = _landlord_partner()
        red = _check_landlord(partner)
        if red: return red

        property_ids = self._get_property_ids(partner)
        contracts    = request.env['tenancy.details'].sudo().search(
            [('property_id', 'in', property_ids),
             ('contract_type', '=', 'running_contract')])

        # Build tenant summary with rent info
        tenants = []
        seen    = set()
        for c in contracts:
            tid = c.tenancy_id.id
            if tid in seen:
                continue
            seen.add(tid)
            inv = request.env['rent.invoice'].sudo().search(
                [('tenancy_id', '=', c.id)])
            paid   = sum(self._rent(i) for i in inv.filtered(lambda i: i.payment_state == 'paid'))
            unpaid = sum(self._rent(i) for i in inv.filtered(
                lambda i: i.payment_state in ['not_paid', 'partial']))
            tenants.append({
                'name':        c.tenancy_id.name,
                'email':       c.tenancy_id.email or '—',
                'phone':       c.tenancy_id.phone or '—',
                'property':    c.property_id.name,
                'start':       c.start_date,
                'end':         c.end_date,
                'rent':        c.total_rent or 0,
                'collected':   paid,
                'outstanding': unpaid,
                'status':      c.contract_type,
            })

        total  = len(tenants)
        offset = (page - 1) * 20
        pager  = portal_pager(url='/my/landlord/tenants', total=total, page=page, step=20)
        items  = tenants[offset:offset + 20]

        return request.render('property_management.landlord_tenants_page', {
            'tenants':   items,
            'pager':     pager,
            'currency':  request.env.company.currency_id,
            'page_name': 'landlord_tenants',
        })

    # ── building detail ───────────────────────────────────────────────────

    @http.route('/my/landlord/building/<model("parent.property"):building>',
                type='http', auth='user', website=True)
    def landlord_building_detail(self, building, **kwargs):
        partner = _landlord_partner()
        red = _check_landlord(partner)
        if red: return red
        if building.landlord_id != partner:
            return request.redirect('/my/landlord')

        properties = request.env['property.details'].sudo().search(
            [('parent_property_id', '=', building.id)])
        contracts  = request.env['tenancy.details'].sudo().search(
            [('property_id', 'in', properties.ids)])
        invoices   = request.env['rent.invoice'].sudo().search(
            [('property_id', 'in', properties.ids)])
        utilities  = request.env['utility.bill'].sudo().search(
            [('property_id', 'in', properties.ids), ('state', '=', 'posted')])
        maintenance= request.env['maintenance.request'].sudo().search(
            [('property_id', 'in', properties.ids)])
        handovers  = request.env['handover.property'].sudo().search(
            [('property_id', 'in', properties.ids)])

        paid   = invoices.filtered(lambda i: i.payment_state == 'paid')
        unpaid = invoices.filtered(lambda i: i.payment_state in ['not_paid', 'partial'])

        return request.render('property_management.landlord_building_detail', {
            'building':             building,
            'properties':           properties,
            'contracts':            contracts,
            'invoices':             invoices,
            'utilities':            utilities,
            'maintenance':          maintenance,
            'handovers':            handovers,
            'currency':             request.env.company.currency_id,
            'page_name':            'landlord_building',
            'bldg_rent_collected':  sum(self._rent(i) for i in paid),
            'bldg_rent_outstanding':sum(self._rent(i) for i in unpaid),
            'bldg_gimco_fees':      sum(i.service_amount or 0 for i in paid),
        })
