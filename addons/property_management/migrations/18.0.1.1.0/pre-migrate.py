# -*- coding: utf-8 -*-
"""
Migration 18.0.1.1.0 — Add new columns that may not exist yet.
Runs BEFORE the ORM setup to avoid UndefinedColumn errors.
"""
import logging
_log = logging.getLogger(__name__)


def migrate(cr, version):
    """Add any columns that don't yet exist in the database."""

    columns = [
        # (table, column, sql_type, default)
        ("tenancy_details", "rent_payment_flow",    "VARCHAR",  "'through_gimco'"),
        ("tenancy_details", "gepg_control_number",  "VARCHAR",  "NULL"),
        ("tenancy_details", "gepg_sp_code",         "VARCHAR",  "NULL"),
        ("tenancy_details", "service_charge_type",  "VARCHAR",  "'fixed'"),
        ("tenancy_details", "service_charge_percentage", "NUMERIC(5,2)", "0"),
        ("tenancy_details", "rent_suspense_account_id",   "INTEGER", "NULL"),
        ("tenancy_details", "service_charge_product_id",  "INTEGER", "NULL"),
        ("tenancy_details", "property_manager_id",  "INTEGER",  "NULL"),
        ("rent_invoice",    "is_direct_to_landlord","BOOLEAN",  "FALSE"),
        ("rent_invoice",    "gepg_control_number",  "VARCHAR",  "NULL"),
        ("rent_invoice",    "landlord_disbursed",   "BOOLEAN",  "FALSE"),
        ("rent_invoice",    "landlord_disbursement_date", "DATE", "NULL"),
        ("rent_invoice",    "landlord_disbursement_ref",  "VARCHAR", "NULL"),
        ("utility_bill",    "purchase_order_id",    "INTEGER",  "NULL"),
        ("utility_bill",    "vendor_bill_id",       "INTEGER",  "NULL"),
        ("utility_bill",    "utility_supplier_id",  "INTEGER",  "NULL"),
        ("utility_bill",    "utility_service_type", "VARCHAR",  "'electricity'"),
        ("utility_bill",    "apply_markup",         "BOOLEAN",  "FALSE"),
        ("utility_bill",    "markup_amount",        "NUMERIC",  "0"),
        ("utility_bill",    "markup_type",          "VARCHAR",  "'fixed'"),
        ("utility_bill",    "markup_percent",       "NUMERIC",  "0"),
        ("maintenance_request", "approval_state",   "VARCHAR",  "'not_required'"),
        ("maintenance_request", "approver_id",      "INTEGER",  "NULL"),
        ("maintenance_request", "approval_date",    "TIMESTAMP","NULL"),
        ("maintenance_request", "approval_note",    "TEXT",     "NULL"),
        ("maintenance_request", "rejection_reason", "TEXT",     "NULL"),
        ("maintenance_request", "estimated_cost",   "NUMERIC",  "0"),
        ("maintenance_request", "currency_id",      "INTEGER",  "NULL"),
        ("property_details",    "property_manager_id", "INTEGER", "NULL"),
        ("parent_property",     "property_manager_id", "INTEGER", "NULL"),
        ("parent_property",     "manager_partner_id",  "INTEGER", "NULL"),
        # Maintenance approval — company config
        ("res_company", "maint_approval_l1_enabled",   "BOOLEAN", "TRUE"),
        ("res_company", "maint_approval_l1_name",      "VARCHAR", "'Property Manager'"),
        ("res_company", "maint_approval_l1_group_id",  "INTEGER", "NULL"),
        ("res_company", "maint_approval_l1_threshold", "NUMERIC", "0"),
        ("res_company", "maint_approval_l2_enabled",   "BOOLEAN", "FALSE"),
        ("res_company", "maint_approval_l2_name",      "VARCHAR", "'Finance Manager'"),
        ("res_company", "maint_approval_l2_group_id",  "INTEGER", "NULL"),
        ("res_company", "maint_approval_l2_threshold", "NUMERIC", "5000"),
        ("res_company", "maint_approval_l3_enabled",   "BOOLEAN", "FALSE"),
        ("res_company", "maint_approval_l3_name",      "VARCHAR", "'Director'"),
        ("res_company", "maint_approval_l3_group_id",  "INTEGER", "NULL"),
        ("res_company", "maint_approval_l3_threshold", "NUMERIC", "20000"),
        ("res_company", "maint_approval_currency_id",  "INTEGER", "NULL"),
        # Maintenance request approval fields
        ("maintenance_request", "approval_state",        "VARCHAR",   "'draft'"),
        ("maintenance_request", "current_approver_id",   "INTEGER",   "NULL"),
        ("maintenance_request", "final_approved_date",   "TIMESTAMP", "NULL"),
        ("maintenance_request", "rejection_reason",      "TEXT",      "NULL"),
        # Accounting split — company level defaults
        ("res_company",          "rent_suspense_account_id",  "INTEGER", "NULL"),
        ("res_company",          "service_charge_product_id", "INTEGER", "NULL"),
        # Rent invoice disbursement tracking
        ("rent_invoice",         "landlord_disbursed",              "BOOLEAN",   "FALSE"),
        ("rent_invoice",         "landlord_disbursement_date",      "DATE",      "NULL"),
        ("rent_invoice",         "landlord_disbursement_ref",       "VARCHAR",   "NULL"),
        ("rent_invoice",         "landlord_disbursement_move_id",   "INTEGER",   "NULL"),
        ("rent_invoice",         "gimco_receivable",                "NUMERIC",   "0"),
        ("rent_invoice",         "is_direct_to_landlord",           "BOOLEAN",   "FALSE"),
    ]

    for table, col, col_type, default in columns:
        cr.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=%s AND column_name=%s",
            (table, col)
        )
        if not cr.fetchone():
            sql = (
                f'ALTER TABLE "{table}" '
                f'ADD COLUMN "{col}" {col_type} '
                f'DEFAULT {default}'
            )
            try:
                cr.execute(sql)
                _log.info("Migration: Added column %s.%s", table, col)
            except Exception as e:
                _log.warning("Migration: Could not add %s.%s — %s", table, col, e)
        else:
            _log.debug("Migration: Column %s.%s already exists", table, col)
