/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PropertyDashboard extends Component {
    static template = "property_management.PropertyDashboard";
    static props = ["*"];

    setup() {
        this.orm    = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true, error: null,
            // properties
            total: 0, available: 0, on_lease: 0, sold: 0, booked: 0, occupancy: 0,
            res_pct: 0, com_pct: 0, land_pct: 0, ind_pct: 0,
            // contracts
            running: 0, draft_c: 0, expired_c: 0, close_c: 0, cancel_c: 0,
            // revenue
            revenue: 0, outstanding: 0, overdueCount: 0,
            // maintenance
            maint_open: 0, maint_done: 0, maint_prog: 0,
            // utility
            util_total: 0, util_paid: 0, util_unpaid: 0, util_amount: 0,
            // charts
            monthly: [], topProps: [], activity: [],
        });

        onWillStart(() => this._loadAll());
    }

    // ── helpers ──────────────────────────────────────────────────────────────

    /**
     * Odoo 18 readGroup signature:
     *   orm.readGroup(model, domain, groupBy[], aggregates[], options?)
     *
     * Aggregate values in results are keyed as "field:func"
     *   e.g.  g["amount:sum"]
     *
     * Odoo 16 was: (model, domain, fields[], groupBy[])  ← WRONG for 18
     */
    async _rg(model, domain, groupBy, aggregates = [], options = {}) {
        try {
            return await this.orm.readGroup(model, domain, groupBy, aggregates, options);
        } catch (e) {
            console.warn(`readGroup ${model}:`, e);
            return [];
        }
    }

    async _sc(model, domain) {
        try { return await this.orm.searchCount(model, domain); }
        catch (e) { console.warn(`searchCount ${model}:`, e); return 0; }
    }

    async _sr(model, domain, fields, opts = {}) {
        try { return await this.orm.searchRead(model, domain, fields, opts); }
        catch (e) { console.warn(`searchRead ${model}:`, e); return []; }
    }

    // ── main loader ───────────────────────────────────────────────────────────

    async _loadAll() {
        await Promise.all([
            this._loadProps(),
            this._loadContracts(),
            this._loadRevenue(),
            this._loadMaint(),
            this._loadUtil(),
            this._loadMonthly(),
            this._loadTop(),
            this._loadActivity(),
        ]);
        this.state.loading = false;
    }

    // ── individual loaders ────────────────────────────────────────────────────

    async _loadProps() {
        const s = this.state;

        // Stage breakdown — groupBy=["stage"], no aggregates needed (__count is automatic)
        const groups = await this._rg("property.details", [], ["stage"]);
        let tot = 0;
        for (const g of groups) {
            const n = g.__count ?? 0;
            tot += n;
            if      (g.stage === "available") s.available = n;
            else if (g.stage === "on_lease")  s.on_lease  = n;
            else if (g.stage === "sold")      s.sold      = n;
            else if (g.stage === "booked")    s.booked    = n;
        }
        s.total = tot;
        const leasable = tot - s.sold;
        s.occupancy = leasable > 0 ? Math.round((s.on_lease / leasable) * 100) : 0;

        // Type breakdown
        const tg = await this._rg("property.details", [], ["type"]);
        let tt = 0;
        const tm = {};
        for (const g of tg) {
            const n = g.__count ?? 0;
            tt += n;
            if (g.type) tm[g.type] = n;
        }
        if (tt > 0) {
            s.res_pct  = Math.round(((tm.residential || 0) / tt) * 100);
            s.com_pct  = Math.round(((tm.commercial  || 0) / tt) * 100);
            s.land_pct = Math.round(((tm.land        || 0) / tt) * 100);
            s.ind_pct  = Math.round(((tm.industrial  || 0) / tt) * 100);
        }
    }

    async _loadContracts() {
        const s = this.state;
        const groups = await this._rg("tenancy.details", [], ["contract_type"]);
        for (const g of groups) {
            const n = g.__count ?? 0;
            switch (g.contract_type) {
                case "running_contract": s.running   = n; break;
                case "new_contract":     s.draft_c   = n; break;
                case "expire_contract":  s.expired_c = n; break;
                case "close_contract":   s.close_c   = n; break;
                case "cancel_contract":  s.cancel_c  = n; break;
            }
        }
    }

    async _loadRevenue() {
        const s = this.state;
        const today = new Date();
        const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1)
            .toISOString().slice(0, 10);

        // No groupBy → single-row aggregate result
        const [pg, og] = await Promise.all([
            this._rg(
                "rent.invoice",
                [["payment_state", "=", "paid"], ["invoice_date", ">=", firstOfMonth]],
                [],               // groupBy
                ["amount:sum"]    // aggregates
            ),
            this._rg(
                "rent.invoice",
                [["payment_state", "=", "not_paid"]],
                [],
                ["amount:sum"]
            ),
        ]);

        // In Odoo 18 the aggregate key IS the string you passed: "amount:sum"
        s.revenue      = Math.round(((pg[0]?.["amount:sum"]) ?? 0) / 1_000_000);
        s.outstanding  = Math.round(((og[0]?.["amount:sum"]) ?? 0) / 1_000_000);
        s.overdueCount = await this._sc("rent.invoice", [["payment_state", "=", "not_paid"]]);
    }

    async _loadMaint() {
        const s = this.state;
        s.maint_open = 0; s.maint_done = 0; s.maint_prog = 0;
        const groups = await this._rg("maintenance.request", [], ["stage_id"]);
        for (const g of groups) {
            const n    = g.__count ?? 0;
            const name = (Array.isArray(g.stage_id) ? g.stage_id[1] : g.stage_id || "").toLowerCase();
            if      (name.includes("done") || name.includes("complet") || name.includes("repair"))       s.maint_done += n;
            else if (name.includes("progress") || name.includes("process") || name.includes("ongoing"))  s.maint_prog += n;
            else                                                                                           s.maint_open += n;
        }
    }

    async _loadUtil() {
        const s = this.state;
        const [tot, paid, unpaid, ag] = await Promise.all([
            this._sc("utility.bill", []),
            this._sc("utility.bill", [["r_payment_state", "=", "Paid"]]),
            this._sc("utility.bill", [["r_payment_state", "=", "Unpaid"], ["state", "=", "posted"]]),
            this._rg("utility.bill", [["state", "=", "posted"]], [], ["total_amount:sum"]),
        ]);
        s.util_total  = tot;
        s.util_paid   = paid;
        s.util_unpaid = unpaid;
        s.util_amount = Math.round(((ag[0]?.["total_amount:sum"]) ?? 0) / 1_000_000);
    }

    async _loadMonthly() {
        const s = this.state;
        const today = new Date();
        const from  = new Date(today.getFullYear(), today.getMonth() - 5, 1)
            .toISOString().slice(0, 10);

        const [pg, og] = await Promise.all([
            this._rg(
                "rent.invoice",
                [["payment_state", "=", "paid"],     ["invoice_date", ">=", from]],
                ["invoice_date:month"],   // groupBy
                ["amount:sum"]            // aggregates
            ),
            this._rg(
                "rent.invoice",
                [["payment_state", "=", "not_paid"], ["invoice_date", ">=", from]],
                ["invoice_date:month"],
                ["amount:sum"]
            ),
        ]);

        const months = [];
        for (let i = 5; i >= 0; i--) {
            const d  = new Date(today.getFullYear(), today.getMonth() - i, 1);
            const yr = d.getFullYear();
            const mo = d.getMonth() + 1;  // 1-based

            /**
             * Odoo 18 returns the groupby key as "invoice_date:month"
             * The VALUE varies by locale/version:
             *   "2025-04"  |  "April 2025"  |  "04/2025"
             * We check all three patterns.
             */
            const isoKey   = `${yr}-${String(mo).padStart(2, "0")}`;
            const locKey   = d.toLocaleString("en", { month: "long" }) + " " + yr;
            const slashKey = `${String(mo).padStart(2, "0")}/${yr}`;

            const match = (arr) => arr.find(g => {
                const raw = String(g["invoice_date:month"] ?? g.invoice_date ?? "");
                return raw.startsWith(isoKey) || raw === locKey || raw === slashKey;
            });

            const pf  = match(pg);
            const of_ = match(og);
            months.push({
                label: d.toLocaleString("default", { month: "short" }),
                c: Math.round(((pf?.["amount:sum"])  ?? 0) / 1_000_000),
                o: Math.round(((of_?.["amount:sum"]) ?? 0) / 1_000_000),
            });
        }
        s.monthly = months;
    }

    async _loadTop() {
        // Top 6 properties by total billed amount
        const groups = await this._rg(
            "rent.invoice",
            [["property_id", "!=", false]],
            ["property_id"],          // groupBy
            ["amount:sum"],           // aggregates
            { orderby: "amount desc", limit: 6 }
        );

        const props = [];
        for (const g of groups) {
            if (!g.property_id) continue;
            const [id, name] = Array.isArray(g.property_id)
                ? g.property_id
                : [g.property_id, String(g.property_id)];

            let type = "", stage = "";
            try {
                const d = await this.orm.read("property.details", [id], ["stage", "type"]);
                if (d.length) { type = d[0].type || ""; stage = d[0].stage || ""; }
            } catch (_) { /* leave blank */ }

            props.push({
                name,
                type,
                stage,
                amt: Math.round(((g["amount:sum"]) ?? 0) / 1_000_000),
            });
        }
        this.state.topProps = props;
    }

    async _loadActivity() {
        const recs = await this._sr(
            "rent.invoice",
            [["property_id", "!=", false]],
            ["description", "invoice_date", "payment_state", "amount", "customer_id"],
            { limit: 6, order: "id desc" }
        );
        this.state.activity = recs.map(r => ({
            text:  r.description || `Invoice — ${Array.isArray(r.customer_id) ? r.customer_id[1] : ""}`,
            date:  r.invoice_date,
            state: r.payment_state,
            amt:   Math.round((r.amount || 0) / 1_000_000),
        }));
    }

    // ── navigation ────────────────────────────────────────────────────────────

    async nav(xmlId) {
        try {
            await this.action.doAction(xmlId);
        } catch (e) {
            console.warn("Navigation failed:", xmlId, e);
        }
    }

    // ── template helpers ──────────────────────────────────────────────────────

    fmt(v) {
        if (!v && v !== 0) return "0";
        if (v >= 1000) return (v / 1000).toFixed(1) + "B";
        return v + "M";
    }

    get maxBar() {
        return Math.max(...this.state.monthly.map(d => d.c + d.o), 1);
    }

    cTot() {
        return (
            this.state.running + this.state.draft_c +
            this.state.expired_c + this.state.close_c + this.state.cancel_c
        ) || 1;
    }
    cPct(v) { return Math.round((v / this.cTot()) * 100); }

    get utilPct() {
        return this.state.util_total > 0
            ? Math.round((this.state.util_paid / this.state.util_total) * 100)
            : 0;
    }

    get typeDonuts() {
        const s = this.state;
        const data = [
            { label: "Residential", color: "#2563EB", pct: s.res_pct  },
            { label: "Commercial",  color: "#7C3AED", pct: s.com_pct  },
            { label: "Land",        color: "#F59E0B", pct: s.land_pct },
            { label: "Industrial",  color: "#06B6D4", pct: s.ind_pct  },
        ];
        let off = 25;
        return data.map(d => {
            const r = { ...d, da: `${d.pct} ${100 - d.pct}`, do_: off };
            off -= d.pct;
            return r;
        });
    }

    get maintDonuts() {
        const s   = this.state;
        const tot = (s.maint_open + s.maint_done + s.maint_prog) || 1;
        const data = [
            { color: "#DC2626", pct: Math.round((s.maint_open / tot) * 100) },
            { color: "#16A34A", pct: Math.round((s.maint_done / tot) * 100) },
            { color: "#F59E0B", pct: Math.round((s.maint_prog / tot) * 100) },
        ];
        let off = 25;
        return data.map(d => {
            const r = { ...d, da: `${d.pct} ${100 - d.pct}`, do_: off };
            off -= d.pct;
            return r;
        });
    }

    stageLabel(s) {
        return { available: "Available", on_lease: "On Lease", sold: "Sold", booked: "Booked", draft: "Draft" }[s] || s || "—";
    }
    stageCls(s) {
        return { available: "bdg-s", on_lease: "bdg-b", sold: "bdg-r", booked: "bdg-a", draft: "bdg-n" }[s] || "bdg-n";
    }
    payCls(s) {
        return { paid: "bdg-s", not_paid: "bdg-r", partial: "bdg-a", in_payment: "bdg-b" }[s] || "bdg-n";
    }
    payLabel(s) {
        return { paid: "Paid", not_paid: "Unpaid", partial: "Partial", in_payment: "In Payment" }[s] || s || "—";
    }
    dotColor(s) {
        return { paid: "#16A34A", not_paid: "#DC2626", partial: "#F59E0B", in_payment: "#2563EB" }[s] || "#9CA3AF";
    }
}

registry.category("actions").add("property_dashboard", PropertyDashboard);
