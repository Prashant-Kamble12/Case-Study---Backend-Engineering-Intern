from decimal import Decimal
from sqlalchemy.exc import IntegrityError

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json() or {}

    # ---------- validate required fields ----------
    required = ['name', 'sku', 'price']
    missing = [f for f in required if f not in data]
    if missing:
        return {"error": f"Missing fields: {', '.join(missing)}"}, 400

    warehouse_id = data.get('warehouse_id')
    initial_quantity = data.get('initial_quantity', 0)

    # ---------- price validation ----------
    try:
        price = Decimal(str(data['price']))
    except:
        return {"error": "Invalid price value"}, 400

    # ---------- quantity validation ----------
    try:
        initial_quantity = int(initial_quantity)
    except:
        return {"error": "Invalid quantity"}, 400

    if initial_quantity < 0:
        return {"error": "Quantity cannot be negative"}, 400

    try:
        with db.session.begin():   # atomic transaction

            # ---------- enforce unique SKU ----------
            if Product.query.filter_by(sku=data['sku']).first():
                return {"error": "SKU already exists"}, 409

            # ---------- create product ----------
            product = Product(
                name=data['name'],
                sku=data['sku'],
                price=price
            )
            db.session.add(product)
            db.session.flush()  # get product.id before commit

            # ---------- handle inventory ----------
            if warehouse_id is not None:
                inventory = Inventory.query.filter_by(
                    product_id=product.id,
                    warehouse_id=warehouse_id
                ).first()

                if inventory:
                    inventory.quantity += initial_quantity
                else:
                    inventory = Inventory(
                        product_id=product.id,
                        warehouse_id=warehouse_id,
                        quantity=initial_quantity
                    )
                    db.session.add(inventory)

        return {"message": "Product created", "product_id": product.id}, 201

    except IntegrityError:
        db.session.rollback()
        return {"error": "Database constraint failed"}, 400

    except Exception:
        db.session.rollback()
        return {"error": "Internal server error"}, 500
