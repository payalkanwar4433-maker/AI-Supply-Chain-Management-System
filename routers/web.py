
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from datetime import datetime, date, timedelta
from sqlalchemy import case
from models import User, Role, Supplier, Product, InventoryBatch, Order, OrderBatchAllocation, Shipment, ProductBundle, BundleItem
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"error": None}
    )


@router.post("/web/register")
def register_user(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.email == email
    ).first()

    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Email already registered"},
            status_code=400
        )

    supplier_role = db.query(Role).filter(
        Role.role_name == "Supplier"
    ).first()

    if supplier_role is None:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Supplier role not found"},
            status_code=500
        )

    new_user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        role_id=supplier_role.id
    )

    db.add(new_user)
    db.commit()

    return RedirectResponse(
        url="/login?registered=1",
        status_code=303
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, registered: int = 0):
    success = (
        "Registration successful. Please login."
        if registered else None
    )

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": None,
            "success": success
        }
    )


@router.post("/web/login")
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.email == email
    ).first()

    if not existing_user or not verify_password(
        password,
        existing_user.password_hash
    ):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Invalid email or password",
                "success": None
            },
            status_code=401
        )

    access_token = create_access_token(
        data={"sub": str(existing_user.id)}
    )

    response = RedirectResponse(
        url="/dashboard",
        status_code=303
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=1800
    )

    return response


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token:
        return RedirectResponse("/login", status_code=303)

    user_id = verify_access_token(token)

    if user_id is None:
        return RedirectResponse("/login", status_code=303)

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if user is None:
        return RedirectResponse("/login", status_code=303)

    role = db.query(Role).filter(
        Role.id == user.role_id
    ).first()

    # Dashboard counts
    total_suppliers = db.query(Supplier).count()
    total_products = db.query(Product).count()
    total_orders = db.query(Order).count()
    total_shipments = db.query(Shipment).count()

    # Low stock alerts
    low_stock_threshold = 10
    low_stock_products = []

    today = date.today()

    products = db.query(Product).all()

    for product in products:

        available_stock = 0

        for batch in product.batches:

            if batch.quantity <= 0:
                continue

            if product.has_expiry:
                if batch.expiry_date is None:
                    continue

                if batch.expiry_date < today:
                    continue

            available_stock += batch.quantity

        if available_stock <= low_stock_threshold:
            low_stock_products.append({
                "product_name": product.product_name,
                "sku": product.sku,
                "quantity": available_stock
            })

    user_data = {
        "full_name": user.full_name,
        "role_name": role.role_name if role else "Unknown"
    }
        # Expiry Alerts (next 30 days)
    today = date.today()
    expiry_limit = today + timedelta(days=30)

    expiry_batches = db.query(InventoryBatch).filter(
        InventoryBatch.expiry_date >= today,
        InventoryBatch.expiry_date <= expiry_limit,
        InventoryBatch.quantity > 0
    ).order_by(InventoryBatch.expiry_date.asc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user_data,
            "total_suppliers": total_suppliers,
            "total_products": total_products,
            "total_orders": total_orders,
            "total_shipments": total_shipments,
            "low_stock_products": low_stock_products,
            "expiry_batches": expiry_batches
        }
    )

@router.get("/web/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.get("/suppliers", response_class=HTMLResponse)
def suppliers_page(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    suppliers = db.query(Supplier).order_by(
        Supplier.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="suppliers.html",
        context={
            "suppliers": suppliers,
            "message": None,
            "error": None
        }
    )


@router.post("/web/suppliers/add")
def add_supplier(
    request: Request,
    supplier_name: str = Form(...),
    contact_person: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    existing_supplier = db.query(Supplier).filter(
        Supplier.email == email
    ).first()

    if existing_supplier:
        suppliers = db.query(Supplier).all()

        return templates.TemplateResponse(
            request=request,
            name="suppliers.html",
            context={
                "suppliers": suppliers,
                "message": None,
                "error": "Supplier email already exists"
            },
            status_code=400
        )

    new_supplier = Supplier(
        supplier_name=supplier_name,
        contact_person=contact_person,
        email=email,
        phone=phone,
        address=address
    )

    db.add(new_supplier)
    db.commit()

    return RedirectResponse("/suppliers", status_code=303)


@router.get("/web/suppliers/edit/{supplier_id}", response_class=HTMLResponse)
def edit_supplier_page(
    supplier_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id
    ).first()

    if supplier is None:
        return RedirectResponse("/suppliers", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="edit_supplier.html",
        context={"supplier": supplier}
    )


@router.post("/web/suppliers/edit/{supplier_id}")
def update_supplier(
    supplier_id: int,
    request: Request,
    supplier_name: str = Form(...),
    contact_person: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id
    ).first()

    if supplier is None:
        return RedirectResponse("/suppliers", status_code=303)

    existing_email = db.query(Supplier).filter(
        Supplier.email == email,
        Supplier.id != supplier_id
    ).first()

    if existing_email:
        return templates.TemplateResponse(
            request=request,
            name="edit_supplier.html",
            context={"supplier": supplier},
            status_code=400
        )

    supplier.supplier_name = supplier_name
    supplier.contact_person = contact_person
    supplier.email = email
    supplier.phone = phone
    supplier.address = address

    db.commit()

    return RedirectResponse("/suppliers", status_code=303)


@router.post("/web/suppliers/delete/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id
    ).first()

    if supplier is not None:
        db.delete(supplier)
        db.commit()

    return RedirectResponse("/suppliers", status_code=303)


@router.get("/products", response_class=HTMLResponse)
def products_page(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    products = db.query(Product).order_by(
        Product.id.desc()
    ).all()

    suppliers = db.query(Supplier).all()

    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            "products": products,
            "suppliers": suppliers,
            "error": None
        }
    )


@router.post("/web/products/add")
def add_product(
    request: Request,
    product_name: str = Form(...),
    sku: str = Form(...),
    description: str = Form(""),
    category: str = Form(...),
    unit_price: float = Form(...),
    supplier_id: int = Form(...),
    has_expiry: str = Form("false"),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    existing_product = db.query(Product).filter(
        Product.sku == sku
    ).first()

    if existing_product:
        return templates.TemplateResponse(
            request=request,
            name="products.html",
            context={
                "products": db.query(Product).all(),
                "suppliers": db.query(Supplier).all(),
                "error": "Product SKU already exists"
            },
            status_code=400
        )

    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id
    ).first()

    if supplier is None:
        return RedirectResponse("/products", status_code=303)

    new_product = Product(
        product_name=product_name,
        sku=sku,
        description=description,
        category=category,
        unit_price=unit_price,
        supplier_id=supplier_id,
        has_expiry=has_expiry.strip().lower() == "true"
    )

    db.add(new_product)
    db.commit()

    return RedirectResponse("/products", status_code=303)



@router.get("/web/products/edit/{product_id}", response_class=HTMLResponse)
def edit_product_page(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if product is None:
        return RedirectResponse("/products", status_code=303)

    suppliers = db.query(Supplier).all()

    return templates.TemplateResponse(
        request=request,
        name="edit_product.html",
        context={
            "product": product,
            "suppliers": suppliers
        }
    )


@router.post("/web/products/edit/{product_id}")
def update_product(
    product_id: int,
    request: Request,
    product_name: str = Form(...),
    sku: str = Form(...),
    description: str = Form(""),
    category: str = Form(...),
    unit_price: float = Form(...),
    supplier_id: int = Form(...),
    has_expiry: str = Form("false"),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if product is None:
        return RedirectResponse("/products", status_code=303)

    existing_product = db.query(Product).filter(
        Product.sku == sku,
        Product.id != product_id
    ).first()

    if existing_product:
        return RedirectResponse(
            f"/web/products/edit/{product_id}",
            status_code=303
        )

    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id
    ).first()

    if supplier is None:
        return RedirectResponse(
            f"/web/products/edit/{product_id}",
            status_code=303
        )

    product.product_name = product_name
    product.sku = sku
    product.description = description
    product.category = category
    product.unit_price = unit_price
    product.supplier_id = supplier_id
    product.has_expiry = has_expiry.strip().lower() == "true"

    db.commit()

    return RedirectResponse("/products", status_code=303)


@router.post("/web/products/delete/{product_id}")
def delete_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if product is not None:
        db.delete(product)
        db.commit()

    return RedirectResponse("/products", status_code=303)



def _inventory_template(request, db, error=None):
    products = db.query(Product).order_by(Product.product_name).all()
    batches = db.query(InventoryBatch).order_by(
        InventoryBatch.id.desc()
    ).all()

    stock_totals = {}
    for batch in batches:
        stock_totals[batch.product_id] = (
            stock_totals.get(batch.product_id, 0) + batch.quantity
        )

    today = date.today()
    expiring_soon = today + timedelta(days=30)

    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={
            "products": products,
            "batches": batches,
            "stock_totals": stock_totals,
            "today": today,
            "expiring_soon": expiring_soon,
            "error": error
        }
    )


@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    return _inventory_template(request, db)



@router.post("/web/inventory/add")
def add_inventory_batch(
    request: Request,
    product_id: int = Form(...),
    batch_number: str = Form(...),
    quantity: int = Form(...),
    received_date: str = Form(""),
    expiry_date: str = Form(""),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if product is None:
        return _inventory_template(request, db, "Please select a valid product.")

    batch_number = batch_number.strip()

    if not batch_number:
        return _inventory_template(request, db, "Batch number is required.")

    if quantity <= 0:
        return _inventory_template(request, db, "Quantity must be greater than zero.")

    duplicate = db.query(InventoryBatch).filter(
        InventoryBatch.batch_number == batch_number
    ).first()

    if duplicate:
        return _inventory_template(request, db, "Batch number already exists.")

    try:
        received_day = (
            date.fromisoformat(received_date)
            if received_date else date.today()
        )

        expiry_day = (
            date.fromisoformat(expiry_date)
            if expiry_date else None
        )

    except ValueError:
        return _inventory_template(request, db, "Please enter valid dates.")

    # Expiry date is optional
    if expiry_day is not None and expiry_day < received_day:
        return _inventory_template(
            request, db,
            "Expiry date cannot be earlier than received date."
        )

    batch = InventoryBatch(
        product_id=product_id,
        batch_number=batch_number,
        quantity=quantity,
        received_date=datetime.combine(
            received_day, datetime.min.time()
        ),
        expiry_date=expiry_day
    )

    try:
        db.add(batch)
        db.commit()

    except Exception:
        db.rollback()
        return _inventory_template(
            request, db,
            "Could not save this batch. Check the batch details."
        )

    return RedirectResponse("/inventory", status_code=303)


@router.post("/web/inventory/add")
def add_inventory_batch(
    request: Request,
    product_id: int = Form(...),
    batch_number: str = Form(...),
    quantity: int = Form(...),
    received_date: str = Form(""),
    expiry_date: str = Form(""),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        return _inventory_template(request, db, "Please select a valid product.")

    batch_number = batch_number.strip()

    if not batch_number:
        return _inventory_template(request, db, "Batch number is required.")

    if quantity <= 0:
        return _inventory_template(request, db, "Quantity must be greater than zero.")

    duplicate = db.query(InventoryBatch).filter(
        InventoryBatch.batch_number == batch_number
    ).first()

    if duplicate:
        return _inventory_template(request, db, "Batch number already exists.")

    try:
        received_day = date.fromisoformat(received_date) if received_date else date.today()
        expiry_day = date.fromisoformat(expiry_date) if expiry_date else None
    except ValueError:
        return _inventory_template(request, db, "Please enter valid dates.")

    # Expiry date is optional
    if expiry_day is not None and expiry_day < received_day:
        return _inventory_template(
            request, db, "Expiry date cannot be earlier than received date."
        )

    batch = InventoryBatch(
        product_id=product_id,
        batch_number=batch_number,
        quantity=quantity,
        received_date=datetime.combine(received_day, datetime.min.time()),
        expiry_date=expiry_day
    )

    try:
        db.add(batch)
        db.commit()
    except Exception:
        db.rollback()
        return _inventory_template(
            request, db, "Could not save this batch. Check the batch details."
        )

    return RedirectResponse("/inventory", status_code=303)

@router.post("/web/inventory/delete/{batch_id}")
def delete_inventory_batch(
    batch_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    batch = db.query(InventoryBatch).filter(
        InventoryBatch.id == batch_id
    ).first()

    if batch is None:
        return RedirectResponse("/inventory", status_code=303)

    used_batch = db.query(OrderBatchAllocation).filter(
        OrderBatchAllocation.batch_id == batch_id
    ).first()

    # Keep batch history if it has ever been used by an order.
    if used_batch:
        return RedirectResponse("/inventory?error=Batch+has+order+history", status_code=303)

    db.delete(batch)
    db.commit()
    return RedirectResponse("/inventory", status_code=303)


def _allocate_batches(db: Session, product: Product, order: Order, quantity: int):
    """Deduct eligible stock using FIFO."""

    today = date.today()

    batches = db.query(InventoryBatch).filter(
        InventoryBatch.product_id == product.id,
        InventoryBatch.quantity > 0,
        (
            InventoryBatch.expiry_date.is_(None) |
            (InventoryBatch.expiry_date >= today)
        )
    ).order_by(
        InventoryBatch.received_date.asc(),
        InventoryBatch.id.asc()
    ).with_for_update().all()

    available = sum(batch.quantity for batch in batches)

    if available < quantity:
        return False

    remaining = quantity

    for batch in batches:
        if remaining <= 0:
            break

        take = min(batch.quantity, remaining)
        batch.quantity -= take

        db.add(OrderBatchAllocation(
            order_id=order.id,
            batch_id=batch.id,
            quantity=take
        ))

        remaining -= take

    return remaining == 0
def _restore_order_batches(db: Session, order: Order):
    """Restore quantities to the exact batches previously used by this order."""
    allocations = db.query(OrderBatchAllocation).filter(
        OrderBatchAllocation.order_id == order.id
    ).all()

    if not allocations:
        return False

    for allocation in allocations:
        batch = db.query(InventoryBatch).filter(
            InventoryBatch.id == allocation.batch_id
        ).with_for_update().first()

        if batch is not None:
            batch.quantity += allocation.quantity

        db.delete(allocation)

    db.flush()
    return True



@router.get("/orders")
def orders_page(
    request: Request,
    db: Session = Depends(get_db),
    error: str = None
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    products = db.query(Product).all()

    bundles = db.query(ProductBundle).all()

    orders = db.query(Order).order_by(
        Order.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="orders.html",
        context={
            "products": products,
            "bundles": bundles,
            "orders": orders,
            "error": error
        }
    )


@router.post("/web/orders/add")
def add_order(
    request: Request,
    order_number: str = Form(...),
    customer_name: str = Form(...),
    item_type: str = Form(...),
    quantity: int = Form(...),
    product_id: int = Form(None),
    bundle_id: int = Form(None),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    if quantity <= 0:
        return RedirectResponse(
            "/orders?error=Quantity+must+be+greater+than+zero",
            status_code=303
        )

    existing_order = db.query(Order).filter(
        Order.order_number == order_number
    ).first()

    if existing_order:
        return RedirectResponse(
            "/orders?error=Order+number+already+exists",
            status_code=303
        )

    new_order = None

    try:
        if item_type == "product":

            product = db.query(Product).filter(
                Product.id == product_id
            ).first()

            if product is None:
                return RedirectResponse(
                    "/orders?error=Product+not+found",
                    status_code=303
                )

            new_order = Order(
                order_number=order_number,
                customer_name=customer_name,
                product_id=product.id,
                bundle_id=None,
                quantity=quantity,
                unit_price=product.unit_price,
                total_amount=product.unit_price * quantity,
                status="Pending"
            )

            db.add(new_order)
            db.flush()

            if not _allocate_batches(
                db, product, new_order, quantity
            ):
                db.rollback()
                return RedirectResponse(
                    "/orders?error=Insufficient+product+stock",
                    status_code=303
                )

        elif item_type == "bundle":

            bundle = db.query(ProductBundle).filter(
                ProductBundle.id == bundle_id
            ).first()

            if bundle is None:
                return RedirectResponse(
                    "/orders?error=Combo+not+found",
                    status_code=303
                )

            new_order = Order(
                order_number=order_number,
                customer_name=customer_name,
                product_id=None,
                bundle_id=bundle.id,
                quantity=quantity,
                unit_price=bundle.bundle_price,
                total_amount=bundle.bundle_price * quantity,
                status="Pending"
            )

            db.add(new_order)
            db.flush()

            for item in bundle.items:

                required_quantity = item.quantity * quantity

                product = db.query(Product).filter(
                    Product.id == item.product_id
                ).first()

                if product is None:
                    db.rollback()
                    return RedirectResponse(
                        "/orders?error=Combo+product+not+found",
                        status_code=303
                    )

                if not _allocate_batches(
                    db,
                    product,
                    new_order,
                    required_quantity
                ):
                    db.rollback()
                    return RedirectResponse(
                        "/orders?error=Insufficient+combo+stock",
                        status_code=303
                    )

        else:
            return RedirectResponse(
                "/orders?error=Invalid+item+type",
                status_code=303
            )

        db.commit()

    except Exception:
        db.rollback()
        return RedirectResponse(
            "/orders?error=Could+not+place+order",
            status_code=303
        )

    return RedirectResponse("/orders", status_code=303)
@router.post("/web/orders/update-status/{order_id}")
def update_order_status(
    order_id: int,
    request: Request,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    allowed_statuses = ["Pending", "Confirmed", "Shipped", "Delivered"]
    if status not in allowed_statuses:
        return RedirectResponse("/orders", status_code=303)

    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        return RedirectResponse("/orders", status_code=303)

    order.status = status
    db.commit()
    return RedirectResponse("/orders", status_code=303)


@router.get("/web/orders/edit/{order_id}")
def edit_order_page(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        return RedirectResponse("/orders", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="edit_order.html",
        context={"order": order}
    )


@router.post("/web/orders/edit/{order_id}")
def edit_order(
    order_id: int,
    request: Request,
    customer_name: str = Form(...),
    quantity: int = Form(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None or quantity <= 0:
        return RedirectResponse("/orders", status_code=303)

    try:
        # We must know the exact batches originally used before changing quantity.
        if not _restore_order_batches(db, order):
            db.rollback()
            return RedirectResponse(
                "/orders?error=This+older+order+has+no+batch+allocation+history",
                status_code=303
            )

        product = db.query(Product).filter(Product.id == order.product_id).first()
        if product is None or not _allocate_batches(db, product, order, quantity):
            db.rollback()
            return RedirectResponse(
                "/orders?error=Not+enough+eligible+batch+stock+for+this+quantity",
                status_code=303
            )

        order.customer_name = customer_name
        order.quantity = quantity
        order.total_amount = order.unit_price * quantity
        db.commit()
    except Exception:
        db.rollback()
        return RedirectResponse("/orders?error=Could+not+update+order", status_code=303)

    return RedirectResponse("/orders", status_code=303)


@router.post("/web/orders/delete/{order_id}")
def delete_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        return RedirectResponse("/orders", status_code=303)

    # Do not delete a shipped order with a shipment record.
    shipment = db.query(Shipment).filter(Shipment.order_id == order_id).first()
    if shipment is not None:
        return RedirectResponse(
            "/orders?error=Delete+the+shipment+record+before+deleting+this+order",
            status_code=303
        )

    try:
        if not _restore_order_batches(db, order):
            db.rollback()
            return RedirectResponse(
                "/orders?error=This+older+order+has+no+batch+allocation+history",
                status_code=303
            )

        db.delete(order)
        db.commit()
    except Exception:
        db.rollback()
        return RedirectResponse("/orders?error=Could+not+delete+order", status_code=303)

    return RedirectResponse("/orders", status_code=303)



@router.get("/shipments")
def shipments_page(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    orders = db.query(Order).all()
    shipments = db.query(Shipment).all()

    return templates.TemplateResponse(
        request=request,
        name="shipments.html",
        context={
            "orders": orders,
            "shipments": shipments
        }
    )

@router.post("/web/shipments/add")
def add_shipment(
    request: Request,
    shipment_number: str = Form(...),
    order_id: int = Form(...),
    carrier_name: str = Form(...),
    tracking_number: str = Form(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    order = db.query(Order).filter(
        Order.id == order_id
    ).first()

    if order is None:
        return RedirectResponse("/shipments", status_code=303)

    existing_shipment = db.query(Shipment).filter(
        (Shipment.order_id == order_id) |
        (Shipment.shipment_number == shipment_number) |
        (Shipment.tracking_number == tracking_number)
    ).first()

    if existing_shipment:
        return RedirectResponse("/shipments", status_code=303)

    new_shipment = Shipment(
        shipment_number=shipment_number,
        order_id=order_id,
        carrier_name=carrier_name,
        tracking_number=tracking_number,
        shipment_status="Processing"
    )

    db.add(new_shipment)
    db.commit()

    return RedirectResponse("/shipments", status_code=303)

@router.post("/web/shipments/update-status/{shipment_id}")
def update_shipment_status(
    shipment_id: int,
    request: Request,
    shipment_status: str = Form(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    allowed_statuses = [
        "Processing",
        "Dispatched",
        "In Transit",
        "Delivered"
    ]

    if shipment_status not in allowed_statuses:
        return RedirectResponse("/shipments", status_code=303)

    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        return RedirectResponse("/shipments", status_code=303)

    shipment.shipment_status = shipment_status

    if shipment_status == "Delivered":
        shipment.delivery_date = datetime.utcnow()
    else:
        shipment.delivery_date = None
    db.commit()

    return RedirectResponse("/shipments", status_code=303)

@router.get("/web/shipments/edit/{shipment_id}")
def edit_shipment_page(
    shipment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        return RedirectResponse("/shipments", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="edit_shipment.html",
        context={"shipment": shipment}
    )


@router.post("/web/shipments/edit/{shipment_id}")
def edit_shipment(
    shipment_id: int,
    request: Request,
    carrier_name: str = Form(...),
    tracking_number: str = Form(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id
    ).first()

    if shipment is None:
        return RedirectResponse("/shipments", status_code=303)

    duplicate_tracking = db.query(Shipment).filter(
        Shipment.tracking_number == tracking_number,
        Shipment.id != shipment_id
    ).first()

    if duplicate_tracking:
        return RedirectResponse("/shipments", status_code=303)

    shipment.carrier_name = carrier_name
    shipment.tracking_number = tracking_number

    db.commit()

    return RedirectResponse("/shipments", status_code=303)

@router.get("/bundles", response_class=HTMLResponse)
def bundles_page(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    products = db.query(Product).all()

    bundles = db.query(ProductBundle).order_by(
        ProductBundle.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="bundles.html",
        context={
            "products": products,
            "bundles": bundles,
            "error": None
        }
    )
@router.post("/web/bundles/add")
def add_bundle(
    request: Request,
    bundle_name: str = Form(...),
    bundle_sku: str = Form(...),
    bundle_price: float = Form(...),
    product_ids: List[int] = Form(...),
    quantities: List[int] = Form(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")

    if not token or verify_access_token(token) is None:
        return RedirectResponse("/login", status_code=303)

    products = db.query(Product).all()
    bundles = db.query(ProductBundle).all()

    def show_error(message):
        return templates.TemplateResponse(
            request=request,
            name="bundles.html",
            context={
                "products": products,
                "bundles": bundles,
                "error": message
            },
            status_code=400
        )

    if bundle_price <= 0:
        return show_error("Combo price must be greater than zero.")

    if len(product_ids) != len(quantities):
        return show_error("Please select valid products and quantities.")

    if len(set(product_ids)) != len(product_ids):
        return show_error("Please select each product only once.")

    if len(product_ids) < 2:
        return show_error("A combo must contain at least two products.")

    if any(quantity <= 0 for quantity in quantities):
        return show_error("Product quantities must be greater than zero.")

    existing_bundle = db.query(ProductBundle).filter(
        ProductBundle.bundle_sku == bundle_sku
    ).first()

    if existing_bundle:
        return show_error("Combo SKU already exists.")

    selected_products = db.query(Product).filter(
        Product.id.in_(product_ids)
    ).all()

    if len(selected_products) != len(product_ids):
        return show_error("One or more selected products do not exist.")

    try:
        new_bundle = ProductBundle(
            bundle_name=bundle_name,
            bundle_sku=bundle_sku,
            bundle_price=bundle_price
        )

        db.add(new_bundle)
        db.flush()

        for product_id, quantity in zip(product_ids, quantities):
            bundle_item = BundleItem(
                bundle_id=new_bundle.id,
                product_id=product_id,
                quantity=quantity
            )
            db.add(bundle_item)

        db.commit()

    except Exception:
        db.rollback()
        return show_error("Could not save the combo. Please check the details.")

    return RedirectResponse("/bundles", status_code=303)