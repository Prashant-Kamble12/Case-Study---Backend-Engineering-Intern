from flask import Flask, jsonify
from sqlalchemy import create_engine, text

app = Flask(__name__)

# DB connection (replace credentials in real system)
engine = create_engine("postgresql://user:password@localhost/inventory_db")

@app.get("/api/companies/<int:company_id>/alerts/low-stock")
def get_low_stock_alerts(company_id):
    """
    Returns low-stock alerts across all warehouses of a company.
    Business rules enforced:
    - low-stock threshold depends on product type
    - ignore products without recent sales
    - handle multiple warehouses
    - include supplier info
    """

    # assumption: "recent activity" means last 30 days
    RECENT_DAYS = 30

    # Core query:
    # join products, warehouses, inventory, suppliers and sales
    # filter below threshold and with recent activity
    query = text("""
        SELECT
            p.id AS product_id,
            p.name AS product_name,
            p.sku,
            w.id AS warehouse_id,
            w.name AS warehouse_name,
            i.quantity AS current_stock,
            pt.low_stock_threshold AS threshold,
            s.id AS supplier_id,
            s.name AS supplier_name,
            s.contact_email,
            COALESCE(SUM(sa.quantity), 0) AS recent_sold
        FROM inventory i
        JOIN products p ON p.id = i.product_id
        JOIN warehouses w ON w.id = i.warehouse_id
        JOIN product_types pt ON pt.id = p.type_id
        LEFT JOIN supplier_product sp ON sp.product_id = p.id
        LEFT JOIN suppliers s ON s.id = sp.supplier_id
        LEFT JOIN sales sa ON sa.product_id = p.id
           AND sa.sale_date >= NOW() - INTERVAL :days DAY
        WHERE w.company_id = :company_id
        GROUP BY p.id, w.id, pt.low_stock_threshold, s.id
        HAVING i.quantity < pt.low_stock_threshold
           AND COALESCE(SUM(sa.quantity), 0) > 0;
    """)

    rows = engine.execute(query, {
        "company_id": company_id,
        "days": RECENT_DAYS
    }).fetchall()

    alerts = []

    for r in rows:

        # defensive fallback to avoid divide-by-zero
        avg_daily_sales = max(r.recent_sold / RECENT_DAYS, 0.01)

        # estimated days until stockout
        days_until_stockout = round(r.current_stock / avg_daily_sales)

        alerts.append({
            "product_id": r.product_id,
            "product_name": r.product_name,
            "sku": r.sku,
            "warehouse_id": r.warehouse_id,
            "warehouse_name": r.warehouse_name,
            "current_stock": r.current_stock,
            "threshold": r.threshold,
            "days_until_stockout": days_until_stockout,
            "supplier": {
                "id": r.supplier_id,
                "name": r.supplier_name,
                "contact_email": r.contact_email
            }
        })

    return jsonify({
        "alerts": alerts,
        "total_alerts": len(alerts)
    })
