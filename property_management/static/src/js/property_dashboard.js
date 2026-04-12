/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PropertyDashboard extends Component {
    static template = "property_management.PropertyDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true, error: null,
            total: 0, available: 0, on_lease: 0, sold: 0, booked: 0, occupancy: 0,
            running: 0, draft_c: 0, expired_c: 0, close_c: 0, cancel_c: 0,
            revenue: 0, outstanding: 0, overdueCount: 0,
            maint_open: 0, maint_done: 0, maint_prog: 0,
            util_total: 0, util_paid: 0, util_unpaid: 0, util_amount: 0,
            monthly: [], topProps: [], activity: [],
            res_pct: 45, com_pct: 32, land_pct: 14, ind_pct: 9,
        });
        onWillStart(() => this._loadAll());
    }

    async _safeCall(fn) {
        try { return await fn(); } catch(e) { console.warn("Dashboard:", e); return null; }
    }

    async _loadAll() {
        await Promise.all([
            this._safeCall(() => this._loadProps()),
            this._safeCall(() => this._loadContracts()),
            this._safeCall(() => this._loadRevenue()),
            this._safeCall(() => this._loadMaint()),
            this._safeCall(() => this._loadUtil()),
            this._safeCall(() => this._loadMonthly()),
            this._safeCall(() => this._loadTop()),
            this._safeCall(() => this._loadActivity()),
        ]);
        this.state.loading = false;
    }

    async _loadProps() {
        const s = this.state;
        const groups = await this.orm.readGroup("property.details", [], [], ["stage"]);
        let tot = 0;
        for (const g of groups) {
            const n = g.__count || g.property_details_count || 0;
            tot += n;
            if (g.stage === "available") s.available = n;
            else if (g.stage === "on_lease") s.on_lease = n;
            else if (g.stage === "sold") s.sold = n;
            else if (g.stage === "booked") s.booked = n;
        }
        s.total = tot;
        const occ = tot - s.sold - s.booked;
        s.occupancy = occ > 0 ? Math.round((s.on_lease / occ) * 100) : 0;

        const tg = await this.orm.readGroup("property.details", [], [], ["type"]);
        let tt = 0; const tm = {};
        for (const g of tg) {
            const n = g.__count || 0;
            tt += n; tm[g.type] = n;
        }
        if (tt > 0) {
            s.res_pct  = Math.round(((tm.residential||0)/tt)*100);
            s.com_pct  = Math.round(((tm.commercial||0)/tt)*100);
            s.land_pct = Math.round(((tm.land||0)/tt)*100);
            s.ind_pct  = Math.round(((tm.industrial||0)/tt)*100);
        }
    }

    async _loadContracts() {
        const s = this.state;
        const groups = await this.orm.readGroup("tenancy.details", [], [], ["contract_type"]);
        for (const g of groups) {
            const n = g.__count || 0;
            if (g.contract_type === "running_contract") s.running = n;
            else if (g.contract_type === "new_contract") s.draft_c = n;
            else if (g.contract_type === "expire_contract") s.expired_c = n;
            else if (g.contract_type === "close_contract") s.close_c = n;
            else if (g.contract_type === "cancel_contract") s.cancel_c = n;
        }
    }

    async _loadRevenue() {
        const s = this.state;
        const today = new Date();
        const first = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0,10);
        const [pg, og, oc] = await Promise.all([
            this.orm.readGroup("rent.invoice", [["payment_state","=","paid"],["invoice_date",">=",first]], ["amount:sum"], []),
            this.orm.readGroup("rent.invoice", [["payment_state","=","not_paid"]], ["amount:sum"], []),
            this.orm.searchCount("rent.invoice", [["payment_state","=","not_paid"]]),
        ]);
        s.revenue = Math.round((pg[0]?.amount || 0) / 1000000);
        s.outstanding = Math.round((og[0]?.amount || 0) / 1000000);
        s.overdueCount = oc;
    }

    async _loadMaint() {
        const s = this.state;
        const groups = await this.orm.readGroup("maintenance.request", [], [], ["stage_id"]);
        for (const g of groups) {
            const n = g.__count || 0;
            const name = (g.stage_id?.[1] || "").toLowerCase();
            if (name.includes("done") || name.includes("repair") || name.includes("complet")) s.maint_done += n;
            else if (name.includes("progress") || name.includes("process")) s.maint_prog += n;
            else s.maint_open += n;
        }
    }

    async _loadUtil() {
        const s = this.state;
        const [tot, paid, unpaid, ag] = await Promise.all([
            this.orm.searchCount("utility.bill", []),
            this.orm.searchCount("utility.bill", [["r_payment_state","=","Paid"]]),
            this.orm.searchCount("utility.bill", [["r_payment_state","=","Unpaid"],["state","=","posted"]]),
            this.orm.readGroup("utility.bill", [["state","=","posted"]], ["total_amount:sum"], []),
        ]);
        s.util_total = tot; s.util_paid = paid; s.util_unpaid = unpaid;
        s.util_amount = Math.round((ag[0]?.total_amount || 0) / 1000000);
    }

    async _loadMonthly() {
        const s = this.state;
        const today = new Date();
        const from = new Date(today.getFullYear(), today.getMonth()-5, 1).toISOString().slice(0,10);
        const [pg, og] = await Promise.all([
            this.orm.readGroup("rent.invoice",[["payment_state","=","paid"],["invoice_date",">=",from]],["amount:sum"],["invoice_date:month"]),
            this.orm.readGroup("rent.invoice",[["payment_state","=","not_paid"],["invoice_date",">=",from]],["amount:sum"],["invoice_date:month"]),
        ]);
        const months = [];
        for (let i=5; i>=0; i--) {
            const d = new Date(today.getFullYear(), today.getMonth()-i, 1);
            const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
            const pf = pg.find(g => (g.invoice_date || g["invoice_date:month"] || "").toString().includes(key));
            const of_ = og.find(g => (g.invoice_date || g["invoice_date:month"] || "").toString().includes(key));
            months.push({
                label: d.toLocaleString("default", {month:"short"}),
                c: Math.round((pf?.amount || 0) / 1000000),
                o: Math.round((of_?.amount || 0) / 1000000),
            });
        }
        s.monthly = months;
    }

    async _loadTop() {
        const groups = await this.orm.readGroup(
            "rent.invoice", [["rent_invoice_id","!=",false]],
            ["amount:sum"], ["property_id"],
            {orderby: "amount desc", limit: 6}
        );
        const props = [];
        for (const g of groups) {
            if (!g.property_id) continue;
            const [id, name] = g.property_id;
            try {
                const d = await this.orm.read("property.details", [id], ["stage","type"]);
                if (d.length) props.push({name, type: d[0].type||"", stage: d[0].stage||"", amt: Math.round((g.amount||0)/1000000)});
            } catch(e) { props.push({name, type:"", stage:"", amt: Math.round((g.amount||0)/1000000)}); }
        }
        this.state.topProps = props;
    }

    async _loadActivity() {
        const recs = await this.orm.searchRead(
            "rent.invoice", [["rent_invoice_id","!=",false]],
            ["description","invoice_date","payment_state","amount","customer_id"],
            {limit: 6, order: "id desc"}
        );
        this.state.activity = recs.map(r => ({
            text: r.description || `Invoice — ${r.customer_id?.[1] || ""}`,
            date: r.invoice_date, state: r.payment_state,
            amt: Math.round((r.amount||0)/1000000),
        }));
    }

    fmt(v) {
        if (!v && v!==0) return "0";
        if (v >= 1000) return (v/1000).toFixed(1)+"B";
        return v+"M";
    }

    get maxBar() { return Math.max(...(this.state.monthly.map(d=>d.c+d.o)), 1); }

    cTot() { return (this.state.running+this.state.draft_c+this.state.expired_c+this.state.close_c+this.state.cancel_c)||1; }
    cPct(v) { return Math.round((v/this.cTot())*100); }

    get utilPct() { return this.state.util_total > 0 ? Math.round((this.state.util_paid/this.state.util_total)*100) : 0; }

    get typeDonuts() {
        const s = this.state;
        const data = [
            {label:"Residential", color:"#2563EB", pct: s.res_pct},
            {label:"Commercial",  color:"#7C3AED", pct: s.com_pct},
            {label:"Land",        color:"#F59E0B", pct: s.land_pct},
            {label:"Industrial",  color:"#06B6D4", pct: s.ind_pct},
        ];
        let off = 25;
        return data.map(d => { const r={...d,da:`${d.pct} ${100-d.pct}`,do_:off}; off-=d.pct; return r; });
    }

    get maintDonuts() {
        const s = this.state;
        const tot = (s.maint_open+s.maint_done+s.maint_prog)||1;
        const data = [
            {color:"#DC2626", pct: Math.round((s.maint_open/tot)*100)},
            {color:"#16A34A", pct: Math.round((s.maint_done/tot)*100)},
            {color:"#F59E0B", pct: Math.round((s.maint_prog/tot)*100)},
        ];
        let off = 25;
        return data.map(d => { const r={...d,da:`${d.pct} ${100-d.pct}`,do_:off}; off-=d.pct; return r; });
    }

    stageLabel(s){return{available:"Available",on_lease:"On lease",sold:"Sold",booked:"Booked",draft:"Draft"}[s]||s||"—";}
    stageCls(s){return{available:"bdg-s",on_lease:"bdg-b",sold:"bdg-r",booked:"bdg-a",draft:"bdg-n"}[s]||"bdg-n";}
    payCls(s){return{paid:"bdg-s",not_paid:"bdg-r",partial:"bdg-a",in_payment:"bdg-b"}[s]||"bdg-n";}
    payLabel(s){return{paid:"Paid",not_paid:"Unpaid",partial:"Partial",in_payment:"In payment"}[s]||s||"—";}
    dotColor(s){return{paid:"#16A34A",not_paid:"#DC2626",partial:"#F59E0B",in_payment:"#2563EB"}[s]||"#9CA3AF";}
}

registry.category("actions").add("property_dashboard", PropertyDashboard);
