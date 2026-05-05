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
        this.state  = useState({
            loading: true,
            // KPI row 1
            occupancy: 0, total: 0, on_lease: 0, available: 0,
            collected: 0, collected_count: 0,
            outstanding: 0, outstanding_count: 0,
            expiring: 0,
            // KPI row 2
            units: 0, booked: 0, sold: 0,
            active_contracts: 0, expired_contracts: 0,
            maint_open: 0, maint_high: 0,
            util_unpaid: 0, util_amount: 0,
            // Chart
            monthly: [],
            // Occupancy by building
            buildings: [],
            // Action lists
            expiring_list: [],
            overdue_list: [],
        });
        onWillStart(() => this._load());
    }

    // ── helpers ───────────────────────────────────────────────────────────

    async _rg(model, domain, groupBy, agg = [], opts = {}) {
        try { return await this.orm.readGroup(model, domain, groupBy, agg, opts); }
        catch (e) { console.warn("rg:", model, e); return []; }
    }
    async _sc(model, domain) {
        try { return await this.orm.searchCount(model, domain); }
        catch (e) { return 0; }
    }
    async _sr(model, domain, fields, opts = {}) {
        try { return await this.orm.searchRead(model, domain, fields, opts); }
        catch (e) { return []; }
    }

    // ── loaders ───────────────────────────────────────────────────────────

    async _load() {
        await Promise.all([
            this._loadOccupancy(),
            this._loadRevenue(),
            this._loadExpiring(),
            this._loadContracts(),
            this._loadMaint(),
            this._loadUtil(),
            this._loadMonthly(),
            this._loadBuildings(),
            this._loadActionLists(),
        ]);
        this.state.loading = false;
    }

    async _loadOccupancy() {
        const s = this.state;
        const g = await this._rg("property.details", [], ["stage"]);
        let tot = 0;
        for (const r of g) {
            const n = r.__count ?? 0; tot += n;
            if (r.stage === "on_lease")  s.on_lease  = n;
            if (r.stage === "available") s.available = n;
            if (r.stage === "booked")    s.booked    = n;
            if (r.stage === "sold")      s.sold      = n;
        }
        s.units = tot;
        s.total = tot;
        const leasable = tot - s.sold;
        s.occupancy = leasable > 0 ? Math.round((s.on_lease / leasable) * 100) : 0;
    }

    async _loadRevenue() {
        const s = this.state;
        const today = new Date();
        const first = new Date(today.getFullYear(), today.getMonth(), 1)
            .toISOString().slice(0, 10);
        const [pg, og] = await Promise.all([
            this._rg("rent.invoice",
                [["payment_state","=","paid"],["invoice_date",">=",first]],
                [], ["amount:sum"]),
            this._rg("rent.invoice",
                [["payment_state","=","not_paid"]], [], ["amount:sum"]),
        ]);
        s.collected       = Math.round((pg[0]?.["amount:sum"] ?? 0) / 1_000_000);
        s.collected_count = await this._sc("rent.invoice",
            [["payment_state","=","paid"],["invoice_date",">=",first]]);
        s.outstanding       = Math.round((og[0]?.["amount:sum"] ?? 0) / 1_000_000);
        s.outstanding_count = await this._sc("rent.invoice",
            [["payment_state","=","not_paid"]]);
    }

    async _loadExpiring() {
        const today = new Date();
        const in30  = new Date(today); in30.setDate(today.getDate() + 30);
        const d30   = in30.toISOString().slice(0, 10);
        const tod   = today.toISOString().slice(0, 10);
        this.state.expiring = await this._sc("tenancy.details", [
            ["end_date",">=", tod],
            ["end_date","<=", d30],
            ["contract_type","=","running_contract"],
        ]);
    }

    async _loadContracts() {
        const g = await this._rg("tenancy.details", [], ["contract_type"]);
        for (const r of g) {
            if (r.contract_type === "running_contract") this.state.active_contracts  = r.__count ?? 0;
            if (r.contract_type === "expire_contract")  this.state.expired_contracts = r.__count ?? 0;
        }
    }

    async _loadMaint() {
        const s = this.state;
        const g = await this._rg("maintenance.request", [], ["stage_id"]);
        s.maint_open = 0;
        for (const r of g) {
            const name = (Array.isArray(r.stage_id) ? r.stage_id[1] : r.stage_id || "").toLowerCase();
            if (!name.includes("done") && !name.includes("complet")) s.maint_open += r.__count ?? 0;
        }
        // High priority open requests
        s.maint_high = await this._sc("maintenance.request", [
            ["priority","=","3"],
            ["stage_id.done","=",false],
        ]).catch(() => 0);
    }

    async _loadUtil() {
        const s = this.state;
        const [cnt, ag] = await Promise.all([
            this._sc("utility.bill", [["r_payment_state","=","Unpaid"],["state","=","posted"]]),
            this._rg("utility.bill", [["r_payment_state","=","Unpaid"],["state","=","posted"]],
                [], ["total_amount:sum"]),
        ]);
        s.util_unpaid = cnt;
        s.util_amount = Math.round((ag[0]?.["total_amount:sum"] ?? 0) / 1_000_000);
    }

    async _loadMonthly() {
        const today = new Date();
        const from  = new Date(today.getFullYear(), today.getMonth() - 5, 1)
            .toISOString().slice(0, 10);
        const [pg, og] = await Promise.all([
            this._rg("rent.invoice",
                [["payment_state","=","paid"],["invoice_date",">=",from]],
                ["invoice_date:month"], ["amount:sum"]),
            this._rg("rent.invoice",
                [["payment_state","=","not_paid"],["invoice_date",">=",from]],
                ["invoice_date:month"], ["amount:sum"]),
        ]);
        const months = [];
        for (let i = 5; i >= 0; i--) {
            const d   = new Date(today.getFullYear(), today.getMonth() - i, 1);
            const yr  = d.getFullYear();
            const mo  = String(d.getMonth() + 1).padStart(2, "0");
            const key = `${yr}-${mo}`;
            const match = (arr) => arr.find(r => {
                const v = String(r["invoice_date:month"] ?? r.invoice_date ?? "");
                return v.startsWith(key) || v === d.toLocaleString("en",{month:"long"})+" "+yr;
            });
            months.push({
                label: d.toLocaleString("default", { month: "short" }),
                c: Math.round((match(pg)?.["amount:sum"] ?? 0) / 1_000_000),
                o: Math.round((match(og)?.["amount:sum"] ?? 0) / 1_000_000),
            });
        }
        this.state.monthly = months;
    }

    async _loadBuildings() {
        const buildings = await this._sr("parent.property", [],
            ["name","id"], { limit: 8, order: "name asc" });
        const result = [];
        for (const b of buildings) {
            const [on, avail, tot] = await Promise.all([
                this._sc("property.details",
                    [["parent_property_id","=",b.id],["stage","=","on_lease"]]),
                this._sc("property.details",
                    [["parent_property_id","=",b.id],["stage","=","available"]]),
                this._sc("property.details",
                    [["parent_property_id","=",b.id]]),
            ]);
            result.push({
                name: b.name,
                on, avail, tot,
                pct: tot > 0 ? Math.round((on / tot) * 100) : 0,
            });
        }
        this.state.buildings = result.sort((a, b) => a.pct - b.pct);
    }

    async _loadActionLists() {
        const today = new Date();
        const tod   = today.toISOString().slice(0, 10);
        const in30  = new Date(today); in30.setDate(today.getDate() + 30);
        const d30   = in30.toISOString().slice(0, 10);

        // Expiring contracts
        const exp = await this._sr("tenancy.details",
            [["end_date",">=",tod],["end_date","<=",d30],
             ["contract_type","=","running_contract"]],
            ["tenancy_seq","tenancy_id","property_id","end_date"],
            { limit: 6, order: "end_date asc" });
        this.state.expiring_list = exp.map(r => ({
            ref:      r.tenancy_seq || "",
            tenant:   Array.isArray(r.tenancy_id) ? r.tenancy_id[1] : "",
            property: Array.isArray(r.property_id) ? r.property_id[1] : "",
            end:      r.end_date,
            days:     Math.ceil((new Date(r.end_date) - today) / 86400000),
        }));

        // Overdue invoices
        const ov = await this._sr("rent.invoice",
            [["payment_state","=","not_paid"],["invoice_date","<=",tod]],
            ["customer_id","property_id","amount","invoice_date"],
            { limit: 6, order: "invoice_date asc" });
        this.state.overdue_list = ov.map(r => ({
            tenant:   Array.isArray(r.customer_id) ? r.customer_id[1] : "",
            property: Array.isArray(r.property_id) ? r.property_id[1] : "",
            amount:   Math.round((r.amount || 0) / 1_000_000),
            days:     Math.ceil((today - new Date(r.invoice_date)) / 86400000),
        }));
    }

    // ── actions ───────────────────────────────────────────────────────────

    async go(xmlId) {
        try { await this.action.doAction(xmlId); }
        catch (e) { console.warn("nav:", xmlId, e); }
    }

    // ── helpers ───────────────────────────────────────────────────────────

    fmt(v) {
        if (!v && v !== 0) return "0";
        if (v >= 1000) return (v / 1000).toFixed(1) + "B";
        if (v >= 1)    return v + "M";
        return "< 1M";
    }

    get maxBar() {
        return Math.max(...this.state.monthly.map(d => d.c + d.o), 1);
    }
    barH(v) { return Math.max(Math.round((v / this.maxBar) * 110), 2); }

    urgency(days) {
        if (days <= 7)  return "#DC2626";
        if (days <= 14) return "#F59E0B";
        return "#16A34A";
    }
}

registry.category("actions").add("property_dashboard", PropertyDashboard);
