# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import date


class PropertyDashboardController(http.Controller):

    @http.route('/property_management/dashboard_data', type='json', auth='user')
    def dashboard_data(self):
        env = request.env

        # ── Property stages ───────────────────────────────────────────
        prop_groups = env['property.details'].read_group([], ['stage'], ['stage'])
        stages = {g['stage']: g['stage_count'] for g in prop_groups}
        total = sum(stages.values())
        available = stages.get('available', 0)
        on_lease  = stages.get('on_lease', 0)
        sold      = stages.get('sold', 0)
        booked    = stages.get('booked', 0)
        occ_base  = total - sold - booked
        occupancy = round((on_lease / occ_base) * 100) if occ_base > 0 else 0

        type_groups = env['property.details'].read_group([], ['type'], ['type'])
        type_total = sum(g['type_count'] for g in type_groups) or 1
        type_map   = {g['type']: g['type_count'] for g in type_groups}

        # ── Contracts ─────────────────────────────────────────────────
        ct_groups = env['tenancy.details'].read_group(
            [], ['contract_type'], ['contract_type'])
        ct_map = {g['contract_type']: g['contract_type_count'] for g in ct_groups}

        # ── Revenue ───────────────────────────────────────────────────
        today = date.today()
        first_of_month = today.replace(day=1).isoformat()

        paid_data = env['rent.invoice'].read_group(
            [('payment_state', '=', 'paid'), ('invoice_date', '>=', first_of_month)],
            ['amount:sum'], [])
        out_data = env['rent.invoice'].read_group(
            [('payment_state', 'in', ['not_paid', 'partial'])],
            ['amount:sum'], [])
        overdue_count = env['rent.invoice'].search_count(
            [('payment_state', 'in', ['not_paid', 'partial'])])

        # ── Maintenance ───────────────────────────────────────────────
        maint_groups = env['maintenance.request'].read_group(
            [], ['stage_id'], ['stage_id'])
        maint_open = maint_done = maint_prog = 0
        for g in maint_groups:
            name = (g['stage_id'][1] if g.get('stage_id') else '').lower()
            n = g['stage_id_count']
            if any(k in name for k in ('done', 'complet', 'repaired')):
                maint_done += n
            elif any(k in name for k in ('progress', 'process')):
                maint_prog += n
            else:
                maint_open += n

        # ── Utility bills ─────────────────────────────────────────────
        util_total = env['utility.bill'].search_count([])
        util_paid  = env['utility.bill'].search_count(
            [('state', '=', 'posted'), ('payment_id', '!=', False)])
        util_posted = env['utility.bill'].read_group(
            [('state', '=', 'posted')], ['total_amount:sum'], [])
        util_amount = (util_posted[0].get('total_amount') or 0) if util_posted else 0
        util_unpaid = max(0, (util_posted[0].get('utility_bill_count', 0) if util_posted else 0) - util_paid)

        # ── Monthly revenue (last 6 months) ───────────────────────────
        from dateutil.relativedelta import relativedelta
        monthly = []
        for i in range(5, -1, -1):
            d = today.replace(day=1) - relativedelta(months=i)
            d_end = (d + relativedelta(months=1)) - relativedelta(days=1)
            label = d.strftime('%b')
            p = env['rent.invoice'].read_group(
                [('payment_state', '=', 'paid'),
                 ('invoice_date', '>=', d.isoformat()),
                 ('invoice_date', '<=', d_end.isoformat())],
                ['amount:sum'], [])
            o = env['rent.invoice'].read_group(
                [('payment_state', 'in', ['not_paid', 'partial']),
                 ('invoice_date', '>=', d.isoformat()),
                 ('invoice_date', '<=', d_end.isoformat())],
                ['amount:sum'], [])
            monthly.append({
                'label': label,
                'c': round((p[0].get('amount') or 0) / 1_000_000) if p else 0,
                'o': round((o[0].get('amount') or 0) / 1_000_000) if o else 0,
            })

        # ── Top properties by revenue ─────────────────────────────────
        top_groups = env['rent.invoice'].read_group(
            [], ['property_id', 'amount:sum'], ['property_id'],
            orderby='amount desc', limit=6)
        top_props = []
        for g in top_groups:
            if not g.get('property_id'):
                continue
            pid, pname = g['property_id']
            prop = env['property.details'].browse(pid)
            top_props.append({
                'name': pname,
                'type': prop.type or '',
                'stage': prop.stage or '',
                'amt': round((g.get('amount') or 0) / 1_000_000),
            })

        # ── Recent activity ───────────────────────────────────────────
        recent = env['rent.invoice'].search_read(
            [], ['description', 'invoice_date', 'payment_state', 'amount', 'customer_id'],
            order='id desc', limit=6)
        activity = [{
            'text': r['description'] or f"Invoice — {r['customer_id'][1] if r.get('customer_id') else ''}",
            'date': r['invoice_date'].isoformat() if r.get('invoice_date') else '',
            'state': r['payment_state'] or '',
            'amt': round((r['amount'] or 0) / 1_000_000),
        } for r in recent]

        return {
            # Properties
            'total': total, 'available': available, 'on_lease': on_lease,
            'sold': sold, 'booked': booked, 'occupancy': occupancy,
            # Types
            'res_pct':  round((type_map.get('residential', 0) / type_total) * 100),
            'com_pct':  round((type_map.get('commercial',  0) / type_total) * 100),
            'land_pct': round((type_map.get('land',        0) / type_total) * 100),
            'ind_pct':  round((type_map.get('industrial',  0) / type_total) * 100),
            # Contracts
            'running':    ct_map.get('running_contract',  0),
            'draft_c':    ct_map.get('new_contract',      0),
            'expired_c':  ct_map.get('expire_contract',   0),
            'close_c':    ct_map.get('close_contract',    0),
            'cancel_c':   ct_map.get('cancel_contract',   0),
            # Revenue
            'revenue':      round((paid_data[0].get('amount') or 0) / 1_000_000) if paid_data else 0,
            'outstanding':  round((out_data[0].get('amount')  or 0) / 1_000_000) if out_data else 0,
            'overdue_count': overdue_count,
            # Maintenance
            'maint_open': maint_open, 'maint_done': maint_done, 'maint_prog': maint_prog,
            # Utility
            'util_total': util_total, 'util_paid': util_paid,
            'util_unpaid': util_unpaid,
            'util_amount': round(util_amount / 1_000_000),
            # Charts
            'monthly':   monthly,
            'top_props': top_props,
            'activity':  activity,
        }
